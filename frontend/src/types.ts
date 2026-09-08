export type Truth = 'Observed' | 'Calculated' | 'Estimated' | 'User input' | 'Unavailable' | 'Demo';
export type Decision = 'GO' | 'WATCH' | 'NO-GO' | 'INSUFFICIENT EVIDENCE';
export interface Observation {
  id: string; metric: string; value: number | null; unit: string; source: string; source_url: string;
  market: string; observed_at: string; fetched_at: string; truth_state: Truth; confidence: number;
  snapshot_id: string; collector_version: string; parser_version: string; usage_rights: string;
  series?: { date: string; value: number | null }[];
}
export interface Product {
  id: string; name: string; category: string; asin: string; source_url: string; market: string;
  confirmed: boolean; truth_state: Truth; decision: Decision; confidence: number; stage: string;
  blocker: string; observations: Observation[]; created_at: string;
  illustration?: 'steamer' | 'lamp' | 'blender'; signals?: string[];
}
export interface User { id: string; name: string; email: string; workspace_id: string; role: 'owner' | 'analyst' | 'viewer' }
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
export interface Assessment {
  id?: string; created_at?: string; product_id?: string; product_name?: string; formula_version: string;
  truth_state: Truth; currency: string; market: string; decision: Decision; confidence: number;
  observation_ids: string[]; blockers: string[]; scenarios: Scenario[]; inputs: Inputs; input_truth_state: Truth;
}
export interface Watch { id: string; product_id: string; product_name?: string | null; threshold_pct: number; status: string; scheduled: boolean; created_at: string }
export interface Quote { id: string; product_id: string; product_name?: string | null; supplier: string; source_url: string; unit_price_usd: number; moq: number; lead_days: number; quote_date: string; incoterm: string; notes: string; truth_state: Truth; verification: string }
