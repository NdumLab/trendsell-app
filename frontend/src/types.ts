export type Truth = 'Observed' | 'Calculated' | 'Estimated' | 'User input' | 'Unavailable' | 'Demo';
export type Decision = 'GO' | 'WATCH' | 'NO-GO' | 'INSUFFICIENT EVIDENCE';
/** One dated record about a product. Today every one is entered by a person and carries
 *  truth state 'User input'; a connected collector would produce 'Observed' (E06). */
export interface Observation {
  id: string; metric: string; value: number | null; unit: string; source?: string; source_url: string;
  source_name?: string; method?: string; notes?: string; input_author?: string; recorded_at?: string;
  market: string; observed_at: string; fetched_at?: string; truth_state: Truth; confidence?: number;
  snapshot_id?: string; collector_version?: string; parser_version?: string; usage_rights?: string;
  series?: { date: string; value: number | null }[];
}
/** The versioned evidence-quality reading. A coverage score, not a probability (E07). */
export interface EvidenceQuality {
  confidence: number; coverage: boolean; compliance_resolved: boolean; overall: number | null;
  observation_ids: string[]; method_version: string; score_meaning: string;
  components: { name: string; detail: string; points: number; max: number }[];
  raw_points: number; capped_at: number | null; records_in_window: number; records_total: number;
  limitations: string[];
}
export interface ComplianceGate {
  resolved: boolean; status: 'none'|'requested'|'approved'|'rejected'|'expired'|'support_expired'|'review_incomplete'|'superseded'|'more_information';
  re_review_pending?: boolean;
  reason: string; review_id?: string; expires_at?: string; hs_code?: string; requirements?: string[];
}
export interface ComplianceReview {
  id: string; product_id: string; product_name?: string; status: string; specifications: string;
  intended_use: string; question: string; hs_code_candidate?: string; hs_code?: string;
  rationale?: string; requirements?: string[]; reviewer_id?: string; requested_by?: string;
  requested_at?: string; decided_at?: string; expires_at?: string | null;
  superseded_by?: string | null; created_at: string;
  sources?: { title: string; url: string; publisher: string; effective_from: string; effective_to?: string | null }[];
}
/** A product's evidence status and the user's latest saved assessment are different facts
 *  and are stored, returned and displayed separately (action plan T07). */
export interface LatestAssessment {
  id: string; decision: Decision; saved_at: string; compliance: Inputs['compliance'];
  channel: string; shipping: Inputs['shipping']; truth_state: Truth;
  formula_version: string; threshold_version?: string | null;
  economics: { base_margin_pct: number; downside_margin_pct: number; contribution: number; break_even_units: number | null; viable: boolean; failures: string[]; threshold_version: string };
}
export interface Product {
  id: string; name: string; category: string; asin: string; source_url: string; market: string;
  confirmed: boolean; truth_state: Truth; decision: Decision; confidence: number; stage: string;
  blocker: string; observations: Observation[]; created_at: string; latest_assessment?: LatestAssessment | null;
  evidence_quality?: EvidenceQuality; compliance?: ComplianceGate;
  illustration?: 'steamer' | 'lamp' | 'blender'; signals?: string[];
}
export interface User { id: string; name: string; email: string; workspace_id: string;
  role: 'owner' | 'analyst' | 'reviewer' | 'viewer';
  /** Null until this installation has proved control of the address. */
  email_verified?: boolean; email_verified_at?: string | null }
export interface JobEvent { id: number; step: string; status: string; detail: string; at: string }
export interface Job { id: string; product_id: string; status: string; events: JobEvent[] }
export interface Source { id: string; name: string; category: string; markets: string[]; reason: string; rights: string; status: string; last_success: string | null; last_attempt: string | null; next_retry: string; freshness_hours: number }
export interface Inputs {
  quantity: number; unit_cost_usd: number; fx_ngn: number; freight_ngn: number; duty_pct: number;
  import_tax_pct: number; selling_price_ngn: number; channel_fee_pct: number; returns_pct: number;
  marketing_ngn: number; fixed_cost_ngn: number; stress_pct: number;
  compliance: 'unresolved' | 'prohibited'; channel: string; shipping: 'Air' | 'Sea';
}
export interface Scenario {
  name: string; supplier: number; freight: number; duty: number; import_tax: number; landed_cost: number;
  price: number; fees: number; returns: number; marketing: number; overhead: number;
  contribution: number; margin_pct: number; cash_required: number; break_even_cac: number; break_even_units: number | null;
}
/** A saved assessment is immutable and self-contained: it carries the evidence it was
 *  calculated from and the versions it must be replayed under, so an export never has to
 *  reconstruct provenance from whatever product a screen currently has open (T03). */
export interface Assessment {
  id?: string; created_at?: string; product_id?: string; product_name?: string; product_asin?: string;
  formula_version: string; threshold_version?: string; evidence_version?: string; input_author?: string;
  truth_state: Truth; currency: string; market: string; decision: Decision; confidence: number;
  observation_ids: string[]; evidence?: Observation[]; blockers: string[]; scenarios: Scenario[];
  inputs: Inputs; input_truth_state: Truth;
  evidence_quality?: EvidenceQuality; compliance?: ComplianceGate; compliance_review_id?: string | null;
  economics?: { base_margin_pct: number; downside_margin_pct: number; contribution: number; break_even_units: number | null; viable: boolean; failures: string[]; threshold_version: string };
}
export interface Watch { id: string; product_id: string; product_name?: string | null; product_decision?: Decision; latest_assessment?: LatestAssessment | null; threshold_pct: number; status: string; scheduled: boolean; created_at: string }
export interface Quote { id: string; product_id: string; product_name?: string | null; supplier: string; source_url: string; unit_price_usd: number; moq: number; lead_days: number; quote_date: string; incoterm: string; notes: string; truth_state: Truth; verification: string }

/** One sign-in session on this account. `id` is a one-way handle, never a token. */
export interface AccountSession {
  id: string; started_at: string; expires_at: string; client: string | null; current: boolean;
}
