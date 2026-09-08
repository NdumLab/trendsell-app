/** Explicit opt-in examples. Never sent to, or loaded by, the production API.
 *
 *  These fixtures exist to teach the workflow, including one example that reaches GO
 *  (action plan U02). The GO is earned, not granted: the demo runs the same
 *  `evidence.quality()`, the same `compliance.gateState()` and the same `calculate()` the
 *  server uses, and the fixture supplies enough dated, independent, current evidence and a
 *  completed reviewer approval to clear them. No gate is relaxed for it.
 *
 *  Every record here carries truth state `Demo`, is labelled as an example in the app and
 *  in every download, and lives only in this browser. */
import { gateState, quality } from '@/lib/evidence';
import type { ComplianceReview, EvidenceQuality, Inputs, Observation, Product } from './types';

const day = 86_400_000;
const daysAgo = (count: number) => new Date(Date.now() - count * day).toISOString().slice(0, 10);
const daysAhead = (count: number) => new Date(Date.now() + count * day).toISOString();

/** A rising series with two collection gaps, so the chart shows what missing data looks like. */
const risingSeries = [24, 28, 26, 34, 31, 37, 42, null, 41, 48, 45, 55, 58, 54, 61, 67, 63, 70, 74, 69, 75, 78, null, 81, 83, 78, 85, 89, 86, 91];
const flatSeries = [51, 48, 53, 49, 52, 47, 55, 50, 46, 54, 51, 49, 53, null, 48, 52, 50, 47, 54, 49, 51, 53, 48, 50, 52, 47, 51, 49, 53, 50];
const fadingSeries = [72, 70, 68, 71, 66, 64, 67, 61, 59, 62, 57, 55, 58, 52, 50, 53, null, 47, 45, 48, 42, 40, 43, 38, 36, 39, 34, 32, 35, 31];

const series = (values: (number | null)[]) =>
  values.map((value, index) => ({ date: daysAgo(values.length - index), value }));

let sequence = 0;
function example(product: string, metric: string, value: number | null, unit: string,
                 source: string, market: string, observed: number, trend?: (number | null)[]): Observation {
  sequence += 1;
  return {
    id: `demo-${product}-${sequence}`, metric, value, unit,
    source_name: source, source: source, source_url: 'https://example-demo-source.test/report',
    method: 'Synthetic demonstration fixture. No source was contacted and no page was fetched.',
    market, observed_at: daysAgo(observed), recorded_at: new Date(Date.now() - observed * day).toISOString(),
    truth_state: 'Demo', usage_rights: 'Synthetic example only — not source evidence',
    series: trend ? series(trend) : undefined,
  };
}

function approval(product: string, hsCode: string): ComplianceReview {
  return {
    id: `demo-review-${product}`, product_id: `demo-${product}`, status: 'approved',
    specifications: 'Synthetic specification for the demonstration fixture.',
    intended_use: 'Retail sale to consumers in Lagos',
    question: 'Which classification applies and what certification is required before import?',
    hs_code_candidate: hsCode, hs_code: hsCode,
    rationale: 'DEMO FIXTURE — not a regulatory opinion. Recorded so the example can show a resolved gate.',
    requirements: ['Product certificate before shipment (demo requirement)', 'Import registration prior to arrival (demo requirement)'],
    sources: [{ title: 'Demonstration import guideline', url: 'https://example-demo-source.test/guideline',
      publisher: 'Example demonstration regulator', effective_from: daysAgo(240) }],
    reviewer_id: 'demo-reviewer', requested_at: new Date(Date.now() - 21 * day).toISOString(),
    decided_at: new Date(Date.now() - 14 * day).toISOString(), expires_at: daysAhead(160),
    superseded_by: null, created_at: new Date(Date.now() - 21 * day).toISOString(),
  };
}

/** Reviews keyed by product id, so the demo can show resolved, pending and absent gates. */
export const demoReviews: Record<string, ComplianceReview> = {
  'demo-steamer': approval('steamer', '8451.30.00'),
  'demo-lamp': { ...approval('lamp', '9405.42.00'), id: 'demo-review-lamp', product_id: 'demo-lamp',
    status: 'requested', hs_code: '', rationale: undefined, requirements: [], sources: [],
    reviewer_id: undefined, decided_at: undefined, expires_at: null },
};

const evidence: Record<string, Observation[]> = {
  // Enough dated, independent, current evidence to clear the coverage and confidence
  // gates on the real method — three demand metrics, four sources, destination coverage.
  'demo-steamer': [
    example('steamer', 'Search interest', 91, 'index / 100', 'Demo search index', 'US', 3, risingSeries),
    example('steamer', 'Review velocity', 18, 'reviews / week', 'Demo marketplace listing', 'US', 5),
    example('steamer', 'Marketplace rank', 640, 'rank in category', 'Demo marketplace category', 'US', 6),
    example('steamer', 'Local listing price', 31500, 'NGN', 'Demo Lagos market survey', 'NG', 9),
    example('steamer', 'Local seller count', 7, 'sellers', 'Demo Lagos market survey', 'NG', 9),
  ],
  // One demand metric, no destination evidence: the honest result is insufficient evidence.
  'demo-lamp': [
    example('lamp', 'Search interest', 57, 'index / 100', 'Demo search index', 'US', 4, flatSeries),
  ],
  // Well evidenced, but the economics do not work — a NO-GO that is not about evidence.
  'demo-blender': [
    example('blender', 'Search interest', 43, 'index / 100', 'Demo search index', 'US', 4, fadingSeries),
    example('blender', 'Review velocity', 4, 'reviews / week', 'Demo marketplace listing', 'US', 7),
    example('blender', 'Local listing price', 18500, 'NGN', 'Demo Lagos market survey', 'NG', 11),
  ],
};

/** The reading for a demo product, computed with the production method. */
export function demoQuality(productId: string): EvidenceQuality {
  return quality(evidence[productId] ?? [], gateState(demoReviews[productId]).resolved);
}

function build(id: string, name: string, category: string, asin: string, stage: string,
               illustration: Product['illustration'], signals: string[]): Product {
  const records = evidence[id] ?? [];
  const compliance = gateState(demoReviews[id]);
  const reading = quality(records, compliance.resolved);
  return {
    id, name, category, asin, source_url: '', market: 'NG', confirmed: true, truth_state: 'Demo',
    // The product's evidence status is derived, exactly as the server derives it.
    decision: reading.coverage ? 'WATCH' : 'INSUFFICIENT EVIDENCE',
    confidence: reading.confidence, stage,
    blocker: reading.limitations[0] ?? 'Evidence coverage is complete for this example.',
    observations: records, created_at: new Date(Date.now() - 30 * day).toISOString(),
    illustration, signals, evidence_quality: reading, compliance,
  };
}

export const demoProducts: Product[] = [
  build('demo-steamer', 'Portable garment steamer', 'Home & living', 'DEMO000001',
    'Evidence complete', 'steamer',
    ['Three independent demand metrics, all within 30 days', 'Destination listings and seller count recorded',
     'Import readiness approved by a reviewer']),
  build('demo-lamp', 'Sunset projection lamp', 'Home & living', 'DEMO000002',
    'Early signal', 'lamp',
    ['One demand metric and one source', 'No destination evidence recorded', 'Import review requested, not yet decided']),
  build('demo-blender', 'Portable USB blender', 'Kitchen', 'DEMO000003',
    'Economics do not work', 'blender',
    ['Demand is recorded and fading', 'Destination price is below the landed cost', 'Evidence is not the problem here']),
];

/** Commercial inputs per demo product. The steamer's clear the margin gates; the
 *  blender's deliberately do not, so the example shows a NO-GO on economics alone. */
export const demoInputsByProduct: Record<string, Inputs> = {
  'demo-steamer': { quantity: 300, unit_cost_usd: 8.4, fx_ngn: 1500, freight_ngn: 900000, duty_pct: 5,
    import_tax_pct: 7.5, selling_price_ngn: 32000, channel_fee_pct: 5, returns_pct: 3,
    marketing_ngn: 300000, fixed_cost_ngn: 150000, stress_pct: 10,
    compliance: 'unresolved', channel: 'Direct sales', shipping: 'Air' },
  'demo-lamp': { quantity: 250, unit_cost_usd: 6.2, fx_ngn: 1500, freight_ngn: 700000, duty_pct: 5,
    import_tax_pct: 7.5, selling_price_ngn: 24000, channel_fee_pct: 5, returns_pct: 3,
    marketing_ngn: 250000, fixed_cost_ngn: 120000, stress_pct: 10,
    compliance: 'unresolved', channel: 'Direct sales', shipping: 'Air' },
  'demo-blender': { quantity: 300, unit_cost_usd: 8.4, fx_ngn: 1500, freight_ngn: 900000, duty_pct: 5,
    import_tax_pct: 7.5, selling_price_ngn: 20000, channel_fee_pct: 5, returns_pct: 3,
    marketing_ngn: 300000, fixed_cost_ngn: 150000, stress_pct: 10,
    compliance: 'unresolved', channel: 'Direct sales', shipping: 'Air' },
};

export const demoInputs: Inputs = demoInputsByProduct['demo-steamer'];
