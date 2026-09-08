import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { MANUAL_ONLY_CAP, METHOD_VERSION, gateState, quality } from '@/lib/evidence';
import { calculate } from '@/lib/economics';
import type { ComplianceReview, EvidenceQuality, Observation } from '@/types';

interface Case { name: string; records: Observation[]; compliance_resolved: boolean; expected: EvidenceQuality }
const contract = JSON.parse(readFileSync(new URL('../../../contracts/evidence_cases.json', import.meta.url), 'utf8')) as
  { method_version: string; evaluated_at: string; cases: Case[] };
const evaluatedAt = new Date(contract.evaluated_at);

describe('shared evidence-quality contract', () => {
  it('pins the method version the backend generated it with', () => {
    expect(contract.method_version).toBe(METHOD_VERSION);
  });

  it.each(contract.cases.map(c => [c.name, c] as const))('%s matches the server result exactly', (_name, testCase) => {
    expect(quality(testCase.records, testCase.compliance_resolved, evaluatedAt)).toEqual(testCase.expected);
  });

  it('caps self-reported evidence below the confidence a GO needs', () => {
    const [capped] = contract.cases.filter(c => c.name === 'manual-rich-but-capped');
    const reading = quality(capped.records, capped.compliance_resolved, evaluatedAt);
    expect(reading.raw_points).toBeGreaterThan(MANUAL_ONLY_CAP);
    expect(reading.confidence).toBe(MANUAL_ONLY_CAP);
    expect(reading.confidence).toBeLessThan(70);
  });

  it('never lets missing evidence look favourable', () => {
    const empty = quality([], false, evaluatedAt);
    expect(empty.confidence).toBe(0);
    expect(empty.coverage).toBe(false);
    expect(empty.overall).toBe(0);
  });
});

describe('the compliance gate', () => {
  const approved: ComplianceReview = {
    id: 'r1', product_id: 'p1', status: 'approved', specifications: 'x', intended_use: 'y', question: 'z',
    hs_code: '8451.30.00', requirements: ['A certificate'], decided_at: '2026-08-01T00:00:00+00:00',
    expires_at: '2027-01-01T00:00:00+00:00', superseded_by: null, created_at: '2026-07-25T00:00:00+00:00',
  };

  it('is unresolved when no review exists', () => {
    expect(gateState(null).resolved).toBe(false);
    expect(gateState(null).status).toBe('none');
  });

  it('is resolved only by a current approval', () => {
    expect(gateState(approved, evaluatedAt).resolved).toBe(true);
    expect(gateState({ ...approved, expires_at: '2026-01-01T00:00:00+00:00' }, evaluatedAt).status).toBe('expired');
    expect(gateState({ ...approved, superseded_by: 'r2' }, evaluatedAt).resolved).toBe(false);
    expect(gateState({ ...approved, status: 'rejected' }, evaluatedAt).status).toBe('rejected');
    expect(gateState({ ...approved, status: 'requested' }, evaluatedAt).status).toBe('requested');
  });
});

/** Action plan U02: the demo GO must pass the production gates on synthetic evidence,
 *  not on a relaxed rule. This asserts the fixtures earn it. */
describe('the demo examples', () => {
  it('reaches GO on the steamer through the real method and the real gates', async () => {
    const { demoProducts, demoInputsByProduct, demoQuality } = await import('@/demo');
    const steamer = demoProducts.find(product => product.id === 'demo-steamer')!;
    const reading = demoQuality('demo-steamer');

    expect(reading.compliance_resolved).toBe(true);
    expect(reading.coverage).toBe(true);
    expect(reading.confidence).toBeGreaterThanOrEqual(70);
    expect(reading.capped_at).toBeNull();

    const result = calculate(demoInputsByProduct['demo-steamer'], {
      confidence: reading.confidence, coverage: reading.coverage,
      compliance_resolved: reading.compliance_resolved, overall: reading.overall,
      observation_ids: reading.observation_ids,
    });
    expect(result.decision).toBe('GO');
    expect(result.blockers).toEqual([]);
    expect(result.scenarios[1].margin_pct).toBeGreaterThanOrEqual(25);
    expect(result.scenarios[0].margin_pct).toBeGreaterThanOrEqual(10);
    // Every record it rests on is labelled synthetic.
    expect(steamer.observations.every(record => record.truth_state === 'Demo')).toBe(true);
  });

  it('leaves the lamp at insufficient evidence because the evidence really is thin', async () => {
    const { demoInputsByProduct, demoQuality } = await import('@/demo');
    const reading = demoQuality('demo-lamp');
    expect(reading.coverage).toBe(false);
    expect(reading.compliance_resolved).toBe(false);
    const result = calculate(demoInputsByProduct['demo-lamp'], {
      confidence: reading.confidence, coverage: reading.coverage,
      compliance_resolved: reading.compliance_resolved, overall: reading.overall,
      observation_ids: reading.observation_ids,
    });
    expect(result.decision).toBe('INSUFFICIENT EVIDENCE');
  });

  it('fails the blender on economics, with its evidence intact', async () => {
    const { demoInputsByProduct, demoQuality } = await import('@/demo');
    const reading = demoQuality('demo-blender');
    expect(reading.coverage).toBe(true);
    const result = calculate(demoInputsByProduct['demo-blender'], {
      confidence: reading.confidence, coverage: reading.coverage,
      compliance_resolved: reading.compliance_resolved, overall: reading.overall,
      observation_ids: reading.observation_ids,
    });
    expect(result.scenarios[1].margin_pct).toBeLessThan(15);
    expect(result.decision).toBe('NO-GO');
  });

  it('gives each product a headline that matches its own fixture history', async () => {
    const { demoProducts } = await import('@/demo');
    const [steamer, lamp, blender] = demoProducts;
    const trend = (product: typeof steamer) => product.observations.find(record => record.series)?.series ?? [];
    const direction = (points: { value: number | null }[]) => {
      const values = points.map(point => point.value).filter((value): value is number => value !== null);
      return values[values.length - 1] - values[0];
    };
    expect(direction(trend(steamer))).toBeGreaterThan(0);
    expect(Math.abs(direction(trend(lamp)))).toBeLessThan(15);
    expect(direction(trend(blender))).toBeLessThan(0);
    // And the three series are genuinely different, not one trajectory reused.
    const series = [steamer, lamp, blender].map(product => JSON.stringify(trend(product).map(point => point.value)));
    expect(new Set(series).size).toBe(3);
  });

  it('marks every demo record as synthetic wherever it appears', async () => {
    const { demoProducts, demoReviews } = await import('@/demo');
    for (const product of demoProducts) {
      expect(product.truth_state).toBe('Demo');
      for (const record of product.observations) {
        expect(record.truth_state).toBe('Demo');
        expect(record.usage_rights).toContain('Synthetic');
        expect(record.method).toContain('Synthetic');
      }
    }
    expect(demoReviews['demo-steamer'].rationale).toContain('DEMO FIXTURE');
  });
});
