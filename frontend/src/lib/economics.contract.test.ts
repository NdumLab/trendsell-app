import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { calculate, FORMULA_VERSION, type EvidenceGate } from '@/lib/economics';
import type { Inputs } from '@/types';

interface Case { name: string; inputs: Inputs; evidence: EvidenceGate; expected: ReturnType<typeof calculate> }
const contract = JSON.parse(readFileSync(new URL('../../../contracts/economics_cases.json', import.meta.url), 'utf8')) as
  { formula_version: string; cases: Case[] };

describe('shared decision contract', () => {
  it('pins the formula version the backend generated it with', () => {
    expect(contract.formula_version).toBe(FORMULA_VERSION);
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
          if (typeof value === 'number') expect(Math.round(value * 100) / 100, `${testCase.name}.${scenario.name}.${key}`).toBe(value);
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
});
