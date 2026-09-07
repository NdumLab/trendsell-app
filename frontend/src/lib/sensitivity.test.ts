import { describe, expect, it } from 'vitest';
import { calculate, sensitivity, targets } from '@/lib/economics';
import type { Inputs } from '@/types';

const INPUTS: Inputs = {
  quantity: 300, unit_cost_usd: 8.4, fx_ngn: 1500, freight_ngn: 900000, duty_pct: 5, import_tax_pct: 7.5,
  selling_price_ngn: 32000, channel_fee_pct: 5, returns_pct: 3, marketing_ngn: 300000, fixed_cost_ngn: 150000,
  stress_pct: 10, compliance: 'unresolved', channel: 'Direct sales', shipping: 'Air',
};
const margin = (inputs: Inputs) => calculate(inputs).scenarios[1].margin_pct;

describe('sensitivity', () => {
  it('returns at most the three most influential inputs, ranked', () => {
    const swings = sensitivity(INPUTS);
    expect(swings.length).toBeLessThanOrEqual(3);
    expect(swings.map(s => s.swing)).toEqual([...swings.map(s => s.swing)].sort((a, b) => b - a));
  });

  it('reports the margin each variation actually produces', () => {
    for (const swing of sensitivity(INPUTS)) {
      const value = INPUTS[swing.key] as number;
      const shift = (factor: number) => ({ ...INPUTS, [swing.key]: swing.key === 'quantity' ? Math.max(1, Math.round(value * factor)) : value * factor });
      expect(swing.low).toBe(margin(shift(0.9)));
      expect(swing.high).toBe(margin(shift(1.1)));
      expect(swing.swing).toBeCloseTo(Math.abs(swing.high - swing.low), 10);
    }
  });

  it('names the selling price as the strongest lever for this scenario', () => {
    expect(sensitivity(INPUTS)[0].key).toBe('selling_price_ngn');
  });

  it('ignores inputs that cannot move the margin', () => {
    const keys = sensitivity({ ...INPUTS, duty_pct: 0, import_tax_pct: 0, returns_pct: 0 }).map(s => s.key);
    expect(keys).not.toContain('duty_pct');
    expect(keys).not.toContain('import_tax_pct');
    expect(keys).not.toContain('returns_pct');
  });

  it('changes nothing about the assessment it measures', () => {
    const before = calculate(INPUTS);
    sensitivity(INPUTS);
    expect(calculate(INPUTS)).toEqual(before);
  });
});

describe('targets', () => {
  it('gives a price that reaches the target margin', () => {
    const goal = targets(INPUTS, 25);
    expect(goal.price).not.toBeNull();
    expect(margin({ ...INPUTS, selling_price_ngn: goal.price! })).toBeCloseTo(25, 1);
  });

  it('gives a supplier quote that reaches the target margin at the current price', () => {
    const goal = targets(INPUTS, 25);
    expect(goal.max_unit_cost_usd).not.toBeNull();
    expect(margin({ ...INPUTS, unit_cost_usd: goal.max_unit_cost_usd! })).toBeCloseTo(25, 1);
  });

  it('reports the landed cost the current inputs actually produce', () => {
    expect(targets(INPUTS).landed).toBeCloseTo(calculate(INPUTS).scenarios[1].landed_cost, 2);
  });

  it('returns no price when fees and returns already exceed what is left', () => {
    const goal = targets({ ...INPUTS, channel_fee_pct: 60, returns_pct: 20 }, 25);
    expect(goal.price).toBeNull();
    expect(goal.max_landed).toBeNull();
    expect(goal.max_unit_cost_usd).toBeNull();
  });
});
