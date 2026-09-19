export type Truth = 'Observed' | 'Calculated' | 'Estimated' | 'User input' | 'Unavailable' | 'Demo';
export type Decision = 'GO' | 'WATCH' | 'NO-GO' | 'INSUFFICIENT EVIDENCE';
export interface PublicConfig {
  allow_registration: boolean;
  release_tier: 'development' | 'controlled_pilot';
  invitation_only: boolean;
  billing_enabled: boolean;
  destination: string;
  demo: boolean;
  research_daily_limit: number;
  mail_delivery_configured: boolean;
  account_recovery: 'email' | 'operator_required';
  audit_retention_days: number;
  features: {
    billing: boolean; public_registration: boolean; recurring_monitoring: boolean;
    alert_delivery: boolean; import_review: boolean; attachments: boolean;
    additional_markets: boolean;
  };
}
/** One dated record about a product. Manual records are 'User input'; records from a
 *  connected, authorised collector are 'Observed' (E06). */
export interface Observation {
  id: string; metric: string; value: number | null; unit: string; source?: string; source_url: string | null;
  source_name?: string; method?: string; notes?: string; input_author?: string; recorded_at?: string;
  market: string; observed_at: string; fetched_at?: string; truth_state: Truth; confidence?: number;
  snapshot_id?: string; collector_version?: string; parser_version?: string; usage_rights?: string;
  source_id?: string; expires_at?: string;
  retention_state?: 'expired';
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
  identity_source?: string; identity_source_id?: string; identity_observed_at?: string;
  identity_collected_at?: string; identity_snapshot_id?: string;
  discovery_context?: { discovery_id: string; snapshot_id?: string; query?: string;
    selected_asin: string; selected_title?: string; selected_position?: number;
    selected_at: string; match_state: 'candidate_selected'; limitations: string };
  catalog?: Record<string, unknown>;
  local_candidates?: LocalCandidate[]; local_candidates_observed_at?: string;
  fx_reference?: { usd_ngn: number; usd_cny: number; cny_ngn_calculated: number;
    observed_at: string; snapshot_id: string; truth_state: Truth; calculation: string };
  illustration?: 'steamer' | 'lamp' | 'blender'; signals?: string[];
}
export interface LocalCandidate {
  title: string; url: string; brand?: string; price?: number; currency?: string;
  rating?: number; rating_count?: number; availability?: string | boolean; seller?: string;
  sku?: string; match_score: number; match_status: 'candidate'; match_method: string;
}
export interface DiscoveryCandidate {
  asin: string; title: string; url: string; position?: number; absolute_position?: number;
  price_from?: number; price_to?: number; currency?: string; rating?: number;
  rating_votes?: number; bought_past_month_indicator?: number;
  is_amazon_choice?: boolean; is_best_seller?: boolean; result_type: 'organic';
}
export interface DiscoveryRun {
  id: string; status: 'queued'|'running'|'succeeded'|'unavailable'; query: string;
  limit: number; source_id: string; source_name?: string; truth_state: Truth;
  candidates: DiscoveryCandidate[]; detail: string; error_code?: string;
  observed_at?: string; collected_at?: string; expires_at?: string;
  source_url?: string; provider_request_id?: string; snapshot_id?: string;
}
export interface User { id: string; name: string; email: string; workspace_id: string;
  role: 'owner' | 'analyst' | 'reviewer' | 'viewer';
  /** Null until this installation has proved control of the address. */
  email_verified?: boolean; email_verified_at?: string | null }
export interface WorkspaceInvitation {
  id: string; email: string; role: 'analyst' | 'reviewer' | 'viewer'; created_at: string;
  expires_at: string; sent_at: string | null; accepted_at: string | null; revoked_at: string | null;
}
export interface JobEvent { id: number; step: string; status: string; detail: string; at: string }
export interface Job { id: string; product_id: string; status: string; events: JobEvent[] }
export interface Source { id: string; name: string; category: string; markets: string[]; reason: string; rights: string;
  last_success: string | null; last_attempt: string | null; next_retry: string; freshness_hours: number;
  adapter_state: 'implemented'|'not_implemented';
  configuration_state: 'disabled'|'missing_requirements'|'configured'|'not_applicable';
  collection_state: 'never_attempted'|'in_progress'|'succeeded'|'failed';
  freshness_state: 'never_succeeded'|'current'|'stale'|'invalid';
  observation_state: 'none'|'stored_current'; stored_observation_count: number;
  api_availability_state: 'unavailable'|'available';
  retention_days: number | null }
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
/** Saved economics inputs/calculations are immutable and self-contained. Provider evidence
 * copies may later become explicit retention tombstones, so expired data cannot remain usable. */
export interface Assessment {
  id?: string; created_at?: string; product_id?: string; product_name?: string; product_asin?: string;
  formula_version: string; threshold_version?: string; evidence_version?: string; input_author?: string;
  truth_state: Truth; currency: string; market: string; decision: Decision; confidence: number;
  observation_ids: string[]; evidence?: Observation[]; blockers: string[]; scenarios: Scenario[];
  inputs: Inputs; input_truth_state: Truth;
  evidence_quality?: EvidenceQuality; compliance?: ComplianceGate; compliance_review_id?: string | null;
  quote_id?: string | null; supplier_quote?: Quote | null;
  quote_conversion?: { source_currency: string; rate_to_usd: number; effective_unit_cost_usd: number; truth_state: Truth } | null;
  economics?: { base_margin_pct: number; downside_margin_pct: number; contribution: number; break_even_units: number | null; viable: boolean; failures: string[]; threshold_version: string };
  evidence_retention_applied_at?: string; expired_evidence_count?: number;
}
export interface Watch { id: string; product_id: string; product_name?: string | null; product_decision?: Decision; latest_assessment?: LatestAssessment | null; threshold_pct: number; status: string; scheduled: boolean; created_at: string }
export interface Quote { id: string; product_id: string; product_name?: string | null; supplier: string; source_url: string;
  unit_price?: number; unit_price_usd?: number; currency: string; moq: number; lead_days: number; quote_date: string; incoterm: string;
  notes: string; truth_state: Truth; verification: string; input_author?: string; recorded_at?: string }

/** One sign-in session on this account. `id` is a one-way handle, never a token. */
export interface AccountSession {
  id: string; started_at: string; expires_at: string; client: string | null; current: boolean;
}
