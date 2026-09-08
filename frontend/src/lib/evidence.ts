import type { ComplianceGate, ComplianceReview, EvidenceQuality, Observation } from '@/types';

/** The evidence-quality method, mirroring `backend/app/evidence.py` (action plan E07).
 *
 *  A real workspace never calls this: the server computes the reading from the records it
 *  holds, and the browser displays what it is given. It exists so the **demo** runs the
 *  same rules rather than a friendlier copy of them — the demo GO example has to pass the
 *  production method, not a relaxed one.
 *
 *  `contracts/evidence_cases.json` holds the two implementations together. */

export const METHOD_VERSION = 'evidence-quality/1.0.0';
export const MANUAL_TRUTH_STATE = 'User input';
export const COLLECTED_TRUTH_STATES = new Set(['Observed', 'Demo']);
export const DEMAND_METRICS = new Set(['Search interest', 'Review velocity', 'Marketplace rank', 'Social mentions']);
export const LOCAL_METRICS = new Set(['Local listing price', 'Local listing count', 'Local seller count', 'Local demand signal']);
export const WINDOW_DAYS = 90;
export const FRESH_DAYS = 30;
/** Self-reported evidence cannot reach the confidence a GO needs. */
export const MANUAL_ONLY_CAP = 60;
const WEIGHTS = {
  demand_metrics: [15, 45], distinct_sources: [10, 30], destination_coverage: [15, 15], freshness: [10, 10],
} as const;

export function ageDays(observedAt: string, now: Date): number {
  const observed = new Date(`${observedAt.slice(0, 10)}T00:00:00Z`);
  return Math.floor((now.getTime() - observed.getTime()) / 86_400_000);
}

export function quality(records: Observation[], complianceResolved: boolean, now = new Date()): EvidenceQuality {
  const inWindow = records.filter(record => ageDays(record.observed_at, now) <= WINDOW_DAYS);
  const demand = new Set(inWindow.filter(record => DEMAND_METRICS.has(record.metric)).map(record => record.metric));
  const local = inWindow.filter(record => record.market === 'NG' && LOCAL_METRICS.has(record.metric));
  const sources = new Set(inWindow.map(record => (record.source_name ?? record.source ?? '').trim().toLowerCase()).filter(Boolean));
  const ages = inWindow.map(record => ageDays(record.observed_at, now));
  const freshest = ages.length ? Math.min(...ages) : null;
  const collected = inWindow.some(record => COLLECTED_TRUTH_STATES.has(record.truth_state));

  const components = [
    { name: 'Independent demand metrics', detail: `${demand.size} distinct demand metric(s) dated within ${WINDOW_DAYS} days`,
      points: Math.min(demand.size * WEIGHTS.demand_metrics[0], WEIGHTS.demand_metrics[1]), max: WEIGHTS.demand_metrics[1] },
    { name: 'Distinct sources', detail: `${sources.size} distinct source(s)`,
      points: Math.min(sources.size * WEIGHTS.distinct_sources[0], WEIGHTS.distinct_sources[1]), max: WEIGHTS.distinct_sources[1] },
    { name: 'Destination coverage', detail: local.length ? `${local.length} Nigeria market record(s)` : 'No Nigeria market evidence',
      points: local.length ? WEIGHTS.destination_coverage[0] : 0, max: WEIGHTS.destination_coverage[1] },
    { name: 'Freshness', detail: freshest === null ? 'No evidence in window' : `Newest record is ${freshest} day(s) old`,
      points: freshest === null ? 0 : (freshest <= FRESH_DAYS ? 10 : 5), max: WEIGHTS.freshness[1] },
  ];
  const raw = components.reduce((total, component) => total + component.points, 0);
  const capped = collected ? raw : Math.min(raw, MANUAL_ONLY_CAP);

  const limitations: string[] = [];
  if (!inWindow.length) limitations.push(`No evidence dated within the last ${WINDOW_DAYS} days.`);
  if (!collected && inWindow.length) limitations.push(`All evidence is self-reported, so the score is capped at ${MANUAL_ONLY_CAP}. Only a connected, authorised collector can raise it further.`);
  if (!demand.size) limitations.push('No recognised demand metric has been recorded.');
  if (!local.length) limitations.push('No Nigeria market evidence. Missing local listings are not low competition.');
  if (!complianceResolved) limitations.push('Import readiness has not been resolved by a reviewer.');

  return {
    confidence: capped, coverage: demand.size > 0 && local.length > 0, compliance_resolved: complianceResolved,
    overall: capped, observation_ids: inWindow.map(record => record.id).sort(),
    method_version: METHOD_VERSION,
    score_meaning: 'Evidence coverage for this product and market. Not a probability of success.',
    components, raw_points: raw, capped_at: collected ? null : MANUAL_ONLY_CAP,
    records_in_window: inWindow.length, records_total: records.length, limitations,
  };
}

/** Mirrors `gate_state()` in `backend/app/compliance.py`. */
export function gateState(review: ComplianceReview | null | undefined, now = new Date()): ComplianceGate {
  if (!review) return { resolved: false, status: 'none', reason: 'No import-readiness review has been requested for this product.' };
  if (review.status === 'approved' && !review.superseded_by && review.expires_at && review.expires_at > now.toISOString())
    return { resolved: true, status: 'approved', review_id: review.id, expires_at: review.expires_at,
      hs_code: review.hs_code, requirements: review.requirements ?? [],
      reason: `Approved by a reviewer on ${(review.decided_at ?? '').slice(0, 10)}, valid to ${review.expires_at.slice(0, 10)}.` };
  if (review.status === 'approved')
    return { resolved: false, status: 'expired', review_id: review.id, reason: `The approval expired on ${String(review.expires_at).slice(0, 10)}. Request a fresh review.` };
  if (review.status === 'rejected')
    return { resolved: false, status: 'rejected', review_id: review.id, reason: 'A reviewer rejected this product for import. Do not proceed.' };
  if (review.status === 'more_information')
    return { resolved: false, status: 'more_information', review_id: review.id, reason: 'The reviewer asked for more information before deciding.' };
  return { resolved: false, status: 'requested', review_id: review.id, reason: 'A review has been requested and is waiting for a reviewer.' };
}
