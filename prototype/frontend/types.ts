export interface SalesDriver {
  name: string;
  type: string;
  description: string;
  impact_score: number;
}

export interface Supplier {
  name: string;
  platform: string;
  moq: number;
  unit_price: string;
  lead_time_days: number;
  rating: number;
  url: string;
}

export interface AggregatedSupplier extends Supplier {
  products: string[];
  categories: string[];
  product_count: number;
}

export interface Competitor {
  name: string;
  platform: string;
  monthly_revenue: string;
  strength: number;
}

export interface ChannelRecommendation {
  platform: string;
  score: number;
  reason: string;
  est_margin_pct: number;
}

export interface AdSpendEstimate {
  platform: string;
  monthly_budget: string;
  expected_roas: string;
  difficulty: string;
}

export interface BundleSuggestion {
  items: string[];
  bundle_price: string;
  margin_uplift_pct: number;
  reason: string;
}

export interface Region {
  code: string;
  flag: string;
  name: string;
  intensity: number;
}

export interface Niche {
  name: string;
  competition: string;
}

export interface MarketBrief {
  executive_summary: string;
  market_opportunity: string;
  competition_level: string;
  recommended_platforms: string[];
  estimated_roi: string;
  key_risks: string[];
  action_items: string[];
  generated_at: string;
  model: string;
}

export interface OpportunityBreakdown {
  trend: number;
  velocity: number;
  saturation_inverse: number;
  margin_potential: number;
  first_mover: number;
}

export interface Product extends Partial<ProductLocaleFields> {
  id: string;
  name: string;
  category: string;
  description: string;
  trend_score: number;
  demand_level: string;
  image_url: string;
  trending_platforms: string[];
  price_range: string;
  estimated_monthly_revenue: string;
  growth_rate: number;
  sales_drivers: SalesDriver[];
  market_opportunity_score: number;
  why_trending: string;
  date_added: string;
  trend_history: number[];
  suppliers: Supplier[];
  saturation_score: number;
  saturation_label: string;
  is_early_opportunity: boolean;
  velocity_pct: number;
  velocity_label: string;
  opportunity_score: number;
  opportunity_breakdown: OpportunityBreakdown;
  seasonal_demand: number[];
  competitors: Competitor[];
  channel_recommendations: ChannelRecommendation[];
  ad_spend_estimates: AdSpendEstimate[];
  bundle_suggestions: BundleSuggestion[];
  regions: Region[];
  niches: Niche[];
  market_brief: MarketBrief | null;
}

export interface TrendsResponse {
  total_products: number;
  avg_opportunity: number;
  top_velocity_platform: string;
  active_drivers: number;
  early_opportunities: number;
  categories: { category: string; count: number; avg_score: number }[];
  platforms: { platform: string; count: number }[];
  trend_series: Record<string, number | string>[];
  top_products: { name: string; trend_score: number; growth_rate: number }[];
}

export interface PlatformFee {
  platform: string;
  referral_fee_pct: number;
  fulfillment_fee: string;
  monthly_subscription: string;
  payment_processing_pct: number;
  notes: string;
}

export interface Country {
  code: string;
  flag: string;
  name: string;
  region: string;
  currency: string;
  symbol: string;
  ppp: number;
  fx: number;
  platforms: string[];
  tariff_pct: number;
  shipping_air: number;
  shipping_sea: number;
  lead_air: number;
  lead_sea: number;
}

export interface LandedCost {
  mode: string;
  unit_cost_usd: number;
  unit_cost_local: string;
  shipping_usd: number;
  shipping_local: string;
  tariff_pct: number;
  tariff_usd: number;
  tariff_local: string;
  customs_fee_usd: number;
  customs_fee_local: string;
  total_usd: number;
  total_local: string;
  lead_time_days: number;
}

// Location-aware fields added to Product responses server-side
export interface ProductLocaleFields {
  country_code: string;
  country_name: string;
  country_flag: string;
  local_currency: string;
  local_symbol: string;
  global_score: number;
  local_score: number;
  is_local_hidden_gem: boolean;
  is_untapped_local: boolean;
  local_platforms: string[];
  local_price_range: string;
  local_estimated_monthly_revenue: string;
  usd_price_range: string;
  local_competitors: Competitor[];
  regulation_flag: "clear" | "certification" | "restricted";
  regulation_note: string;
  landed_cost_air: LandedCost;
  landed_cost_sea: LandedCost;
}
