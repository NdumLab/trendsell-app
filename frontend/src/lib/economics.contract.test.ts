import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { calculate, FORMULA_VERSION, THRESHOLD_VERSION, type EvidenceGate } from '@/lib/economics';
import { ceilUnits, divRound, fromDecimalString, money, parse, quantize, toNumber, UNIT } from '@/lib/money';
import type { Inputs } from '@/types';

interface Case { name: string; inputs: Inputs; evidence: EvidenceGate; expected: ReturnType<typeof calculate> }
const read = (file: string) => JSON.parse(readFileSync(new URL(`../../../contracts/${file}`, import.meta.url), 'utf8')) as
  { formula_version: string; threshold_version: string; cases: Case[] };
const contract = read('economics_cases.json');
const legacy = read('economics_legacy_cases.json');
/** Two decimal places need value*100 to stay an exact integer double. */
const EXACT_MONEY_LIMIT = Number.MAX_SAFE_INTEGER / 100;

describe('shared decision contract', () => {
  it('pins the formula and threshold versions the backend generated it with', () => {
    expect(contract.formula_version).toBe(FORMULA_VERSION);
    expect(contract.threshold_version).toBe(THRESHOLD_VERSION);
  });

  it.each(contract.cases.map(c => [c.name, c] as const))('%s matches the server result exactly', (_name, testCase) => {
    expect(calculate(testCase.inputs, testCase.evidence)).toEqual(testCase.expected);
  });

  it.each(contract.cases.map(c => [c.name, c] as const))('%s is deterministic across runs', (_name, testCase) => {
    expect(calculate(testCase.inputs, testCase.evidence)).toEqual(calculate(testCase.inputs, testCase.evidence));
  });

  it('rounds every money value to two places, as the contract states', () => {
    for (const testCase of contract.cases)
      for (const scenario of calculate(testCase.inputs, testCase.evidence).scenarios)
        for (const [key, value] of Object.entries(scenario))
          // Above EXACT_MONEY_LIMIT a JSON number cannot carry two decimal places at all;
          // the case below states that limit explicitly instead of pretending otherwise.
          if (typeof value === 'number' && Math.abs(value) <= EXACT_MONEY_LIMIT)
            expect(Number(value.toFixed(2)), `${testCase.name}.${scenario.name}.${key}`).toBe(value);
  });

  it('states the magnitude beyond which a JSON number cannot hold two decimal places', () => {
    // Both sides still agree exactly (the parity case above covers it) — but callers must
    // not read cents off a figure this large, so the contract records the boundary.
    expect(EXACT_MONEY_LIMIT).toBe(Number.MAX_SAFE_INTEGER / 100);
    const [extreme] = contract.cases.filter(c => c.name === 'accepted-range-maximums');
    expect(calculate(extreme.inputs, extreme.evidence).scenarios[1].cash_required).toBeGreaterThan(EXACT_MONEY_LIMIT);
  });

  it('never returns GO while compliance is unresolved and confidence is low', () => {
    const [thin] = contract.cases.filter(c => c.name === 'worked-example-no-evidence');
    expect(calculate(thin.inputs, thin.evidence).decision).toBe('INSUFFICIENT EVIDENCE');
  });

  it('keeps the user inputs and their truth state on the assessment', () => {
    for (const testCase of contract.cases) {
      const result = calculate(testCase.inputs, testCase.evidence);
      expect(result.inputs).toEqual(testCase.inputs);
      expect(result.input_truth_state).toBe('User input');
      expect(result.truth_state).toBe('Calculated');
    }
  });

  it('reproduces the rounding disagreement the review found, on the server’s side', () => {
    // Review finding 5: quantity 1, supplier cost 10.075, everything else neutral.
    // Python reported 10.08 and this file's implementation used to report 10.07.
    const [repro] = contract.cases.filter(c => c.name === 'review-repro-half-cent-supplier-cost');
    expect(repro.inputs.unit_cost_usd).toBe(10.075);
    expect(calculate(repro.inputs, repro.evidence).scenarios[1].supplier).toBe(10.08);
  });
});

describe('superseded formula versions still replay', () => {
  it('is frozen at a version that is no longer the current one', () => {
    expect(legacy.formula_version).toBe('unit-economics/1.0.0');
    expect(legacy.formula_version).not.toBe(FORMULA_VERSION);
  });

  it.each(legacy.cases.map(c => [c.name, c] as const))('%s replays to its saved values', (_name, testCase) => {
    // Replayed under the versions it was saved with: arithmetic and decision rules are
    // versioned independently, so both come from the frozen contract (R04, R06).
    expect(calculate(testCase.inputs, testCase.evidence, legacy.formula_version, legacy.threshold_version)).toEqual(testCase.expected);
  });

  it('refuses an unknown version rather than silently using the current one', () => {
    expect(() => calculate(contract.cases[0].inputs, contract.cases[0].evidence, 'unit-economics/9.9.9')).toThrow();
  });

  it('uses the current version by default', () => {
    expect(calculate(contract.cases[0].inputs, contract.cases[0].evidence).formula_version).toBe(FORMULA_VERSION);
  });
});

describe('shared decimal primitives', () => {
  it.each([
    ['0', 0n], ['1', UNIT], ['-1', -UNIT], ['0.5', UNIT / 2n], ['-0.5', -UNIT / 2n],
    ['1e-12', 1n], ['1E+3', 1000n * UNIT], ['  2.5  ', (UNIT * 5n) / 2n],
    ['0.0000000000005', 1n], ['-0.0000000000005', -1n], ['0.0000000000004', 0n],
  ] as const)('scales %s as documented', (text, expected) => {
    expect(fromDecimalString(text)).toBe(expected);
  });

  it.each([
    [5n, 10n, 1n], [-5n, 10n, -1n], [4n, 10n, 0n], [-4n, 10n, 0n],
    [15n, 10n, 2n], [-15n, 10n, -2n], [5n, -10n, -1n], [0n, 7n, 0n],
  ] as const)('divides %s/%s half away from zero', (n, d, expected) => {
    expect(divRound(n, d)).toBe(expected);
  });

  it.each([0, 0.01, -0.01, 8.4, 10.075, -10.075, 1e12, 1e-6, 123456.789])('round-trips %s', value => {
    expect(toNumber(quantize(parse(value), 12n))).toBe(value);
  });

  it('quantises to two places in both directions', () => {
    expect(money(parse('10.075'))).toBe(10.08);
    expect(money(parse('-10.075'))).toBe(-10.08);
    expect(money(parse('10.074'))).toBe(10.07);
    expect(money(parse('10.085'))).toBe(10.09);
  });

  it('takes the mathematical ceiling', () => {
    expect(ceilUnits(parse('2'))).toBe(2);
    expect(ceilUnits(parse('2.0000000001'))).toBe(3);
    expect(ceilUnits(parse('-1.5'))).toBe(-1);
    expect(ceilUnits(parse('0'))).toBe(0);
  });

  it('refuses a non-finite number rather than producing a wrong scale', () => {
    expect(() => parse(Number.NaN)).toThrow();
    expect(() => parse(Number.POSITIVE_INFINITY)).toThrow();
  });
});
