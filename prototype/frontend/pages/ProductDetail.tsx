import React from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchProduct, generateBrief, generateNiches } from "@/lib/api";
import { useLocation } from "@/context/LocationContext";
import { toast } from "sonner";
import {
  ArrowLeft, TrendingUp, Zap, Users, DollarSign, Factory, Star, Clock, Package, ExternalLink,
  Sparkles, Search, Rocket, Target, Store, Megaphone, Layers, Globe, Calendar as CalendarIcon,
  Info, Trophy, ShieldCheck, ShieldAlert, ShieldX, Plane, Ship, Compass,
} from "lucide-react";
import { PlatformBadge } from "@/components/PlatformBadge";
import { SaturationPill } from "@/components/SaturationPill";
import { OpportunityGauge } from "@/components/OpportunityGauge";
import { ProfitCalculator } from "@/components/ProfitCalculator";
import { SeasonalCalendar } from "@/components/SeasonalCalendar";
import { MarketBriefView } from "@/components/MarketBriefView";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/SimpleTabs";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";

const driverTypeColor: Record<string, string> = {
  marketplace: "bg-pink-500/10 text-pink-400 border-pink-500/30",
  ads: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  influencer: "bg-purple-500/10 text-purple-400 border-purple-500/30",
  shopify_app: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  analytics: "bg-indigo-500/10 text-indigo-400 border-indigo-500/30",
  email: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  loyalty: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
};

const compColor: Record<string, string> = {
  "Very Low": "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  "Low": "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  "Medium": "text-amber-400 bg-amber-500/10 border-amber-500/30",
  "High": "text-orange-400 bg-orange-500/10 border-orange-500/30",
  "Very High": "text-rose-400 bg-rose-500/10 border-rose-500/30",
};

const difficultyColor: Record<string, string> = {
  Low: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  Medium: "text-amber-400 bg-amber-500/10 border-amber-500/30",
  High: "text-rose-400 bg-rose-500/10 border-rose-500/30",
};

const ProductDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { country } = useLocation();

  const { data: product, isLoading } = useQuery({
    queryKey: ["product", id, country.code],
    queryFn: () => fetchProduct(id!, country.code),
    enabled: !!id,
  });

  const briefMutation = useMutation({
    mutationFn: (force: boolean) => generateBrief(id!, force),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["product", id] });
      toast.success("Market brief ready");
    },
    onError: () => toast.error("Brief generation failed"),
  });

  const nichesMutation = useMutation({
    mutationFn: () => generateNiches(id!, true),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["product", id] });
      toast.success("AI niches generated");
    },
    onError: () => toast.error("Niche generation failed"),
  });

  if (isLoading || !product) {
    return (
      <div className="space-y-6" data-testid="product-detail-modal">
        <div className="h-8 w-40 rounded bg-slate-900 animate-pulse" />
        <div className="h-96 rounded-2xl bg-slate-900 animate-pulse" />
      </div>
    );
  }

  const chartData = (product.trend_history || []).map((v, i) => ({ week: `W${i + 1}`, score: v }));
  const salesDrivers = product.sales_drivers || [];
  const channels = product.channel_recommendations || [];
  const adSpend = product.ad_spend_estimates || [];
  const bundles = product.bundle_suggestions || [];
  const suppliers = product.suppliers || [];
  const niches = product.niches || [];
  const competitors = (product.local_competitors && product.local_competitors.length > 0)
    ? product.local_competitors
    : (product.competitors || []);
  const platformsToShow = product.local_platforms || product.trending_platforms || [];

  return (
    <div className="space-y-8" data-testid="product-detail-modal">
      <Link
        to="/"
        data-testid="product-detail-back-button"
        className="inline-flex items-center gap-1.5 text-xs font-semibold tracking-wider uppercase text-slate-400 hover:text-emerald-400 transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to dashboard
      </Link>

      {/* Hero banner */}
      <section className="rounded-2xl overflow-hidden bg-slate-900/80 border border-slate-800">
        <div className="relative h-64 sm:h-80 bg-slate-950">
          <img src={product.image_url} alt={product.name} className="h-full w-full object-cover opacity-95" />
          <div className="absolute inset-0 bg-gradient-to-t from-slate-950/95 via-slate-950/30 to-transparent" />
          <div className="absolute bottom-0 left-0 right-0 p-6 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <span className="text-[11px] font-semibold tracking-[0.2em] uppercase text-emerald-400">{product.category}</span>
                {product.is_local_hidden_gem && (
                  <span className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-gradient-to-r from-violet-500 to-pink-500 text-slate-950 text-[10px] font-bold tracking-wider uppercase">
                    <Sparkles className="h-3 w-3" /> 🌍 Local Hidden Gem
                  </span>
                )}
                {product.is_untapped_local && (
                  <span className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-gradient-to-r from-amber-400 to-rose-500 text-slate-950 text-[10px] font-bold tracking-wider uppercase">
                    <Compass className="h-3 w-3" /> 🚀 Untapped in {country.name}
                  </span>
                )}
                {product.is_early_opportunity && !product.is_local_hidden_gem && !product.is_untapped_local && (
                  <span className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-gradient-to-r from-emerald-500 to-indigo-500 text-slate-950 text-[10px] font-bold tracking-wider uppercase">
                    <Rocket className="h-3 w-3" /> Early Opportunity
                  </span>
                )}
              </div>
              <h1
                className="text-3xl sm:text-4xl font-extrabold text-slate-50 leading-tight"
                style={{ fontFamily: "'Plus Jakarta Sans', sans-serif" }}
              >
                {product.name}
              </h1>
              <p className="mt-2 text-sm text-slate-300 max-w-2xl line-clamp-2">{product.description}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {(product.local_platforms || product.trending_platforms).map((p) => <PlatformBadge key={p} platform={p} />)}
              </div>
            </div>
            {/* Country/Regions */}
            <div className="flex flex-col gap-2 items-end shrink-0">
              <div className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-950/80 backdrop-blur-md border border-slate-800">
                <span className="text-lg leading-none">{country.flag}</span>
                <div className="leading-tight">
                  <div className="text-[9px] font-bold tracking-wider uppercase text-emerald-400">Market</div>
                  <div className="text-xs font-bold text-slate-100">{country.name}</div>
                </div>
              </div>
              {product.regions && product.regions.length > 0 && (
                <div className="flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-950/80 backdrop-blur-md border border-slate-800">
                  <Globe className="h-3 w-3 text-slate-500" />
                  {product.regions.map((r) => (
                    <span key={r.code} title={`${r.name} · ${r.intensity}/100`} className="text-sm leading-none" style={{ opacity: 0.4 + (r.intensity / 100) * 0.6 }}>
                      {r.flag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Local vs Global score comparison + Regulation */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-8 rounded-2xl bg-slate-900/80 border border-slate-800 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-semibold tracking-[0.2em] uppercase text-slate-500">Local vs Global demand</h2>
            <div className="text-[10px] text-slate-500">Score differential</div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-xl bg-slate-950/60 border border-slate-800 p-4">
              <div className="flex items-center gap-2 text-[10px] font-bold tracking-wider uppercase text-emerald-400 mb-1">
                <span>{country.flag}</span> {country.name}
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-extrabold text-emerald-400 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{product.local_score ?? product.trend_score}</span>
                <span className="text-xs font-bold text-slate-500">/100</span>
              </div>
              <div className="mt-2 h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-emerald-400 to-indigo-500" style={{ width: `${product.local_score ?? product.trend_score}%` }} />
              </div>
            </div>
            <div className="rounded-xl bg-slate-950/60 border border-slate-800 p-4">
              <div className="text-[10px] font-bold tracking-wider uppercase text-slate-400 mb-1">🌐 Global</div>
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-extrabold text-slate-100 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{product.global_score ?? product.trend_score}</span>
                <span className="text-xs font-bold text-slate-500">/100</span>
              </div>
              <div className="mt-2 h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-slate-500" style={{ width: `${product.global_score ?? product.trend_score}%` }} />
              </div>
            </div>
          </div>
        </div>

        <div className="lg:col-span-4 rounded-2xl bg-slate-900/80 border border-slate-800 p-6" data-testid="regulation-panel">
          <div className="flex items-center gap-2 mb-3">
            {product.regulation_flag === "clear" && <ShieldCheck className="h-4 w-4 text-emerald-400" />}
            {product.regulation_flag === "certification" && <ShieldAlert className="h-4 w-4 text-amber-400" />}
            {product.regulation_flag === "restricted" && <ShieldX className="h-4 w-4 text-rose-400" />}
            <h2 className="text-xs font-semibold tracking-[0.2em] uppercase text-slate-500">Regulation · {country.flag}</h2>
          </div>
          <div className={`inline-block px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wider uppercase border ${
            product.regulation_flag === "clear" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" :
            product.regulation_flag === "certification" ? "bg-amber-500/10 text-amber-400 border-amber-500/30" :
            "bg-rose-500/10 text-rose-400 border-rose-500/30"
          }`}>
            {product.regulation_flag === "clear" ? "🟢 Clear to sell" : product.regulation_flag === "certification" ? "🟡 Cert Required" : "🔴 Restricted"}
          </div>
          <p className="mt-3 text-xs text-slate-300 leading-relaxed">{product.regulation_note}</p>
        </div>
      </section>

      {/* Top row: Opportunity gauge + Why trending + Snapshot */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-4 rounded-2xl bg-slate-900/80 border border-slate-800 p-6">
          <h2 className="text-xs font-semibold tracking-[0.2em] uppercase text-slate-500 mb-4 text-center">
            Overall Opportunity
          </h2>
          <OpportunityGauge score={product.opportunity_score} breakdown={product.opportunity_breakdown} />
        </div>

        <div className="lg:col-span-5 rounded-2xl bg-slate-900/80 border border-slate-800 p-6">
          <div className="flex items-center gap-2 mb-3">
            <Info className="h-4 w-4 text-emerald-400" />
            <h2 className="text-xs font-semibold tracking-[0.2em] uppercase text-slate-500">Why it's trending</h2>
          </div>
          <p className="text-sm text-slate-200 leading-relaxed">{product.why_trending}</p>
          <div className="mt-5 grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-slate-950/60 border border-slate-800 p-3">
              <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500">Trend</div>
              <div className="text-xl font-extrabold text-slate-50 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{product.trend_score}</div>
            </div>
            <div className="rounded-lg bg-slate-950/60 border border-slate-800 p-3">
              <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500">Velocity</div>
              <div className={`text-xl font-extrabold tabular-nums ${product.velocity_pct >= 10 ? "text-emerald-400" : product.velocity_pct >= -5 ? "text-amber-400" : "text-rose-400"}`} style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {product.velocity_pct >= 0 ? "+" : ""}{product.velocity_pct}%
              </div>
            </div>
          </div>
          <div className="mt-3">
            <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500 mb-2">Market saturation</div>
            <SaturationPill score={product.saturation_score} label={product.saturation_label} size="md" />
          </div>
        </div>

        <div className="lg:col-span-3 rounded-2xl bg-slate-900/80 border border-slate-800 p-6">
          <h2 className="text-xs font-semibold tracking-[0.2em] uppercase text-slate-500 mb-4">Snapshot</h2>
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center"><DollarSign className="h-4 w-4 text-emerald-400" /></div>
              <div className="min-w-0">
                <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500">Monthly Rev · {country.flag}</div>
                <div className="text-sm font-bold text-slate-50 truncate">{product.local_estimated_monthly_revenue || product.estimated_monthly_revenue}</div>
                <div className="text-[10px] text-slate-500">≈ {product.estimated_monthly_revenue}</div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center"><Users className="h-4 w-4 text-indigo-400" /></div>
              <div className="min-w-0">
                <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500">Local Price</div>
                <div className="text-sm font-bold text-slate-50 truncate">{product.local_price_range || product.price_range}</div>
                <div className="text-[10px] text-slate-500">≈ {product.usd_price_range || product.price_range}</div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-violet-500/10 border border-violet-500/20 flex items-center justify-center"><TrendingUp className="h-4 w-4 text-violet-400" /></div>
              <div>
                <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500">Growth</div>
                <div className="text-sm font-bold text-slate-50">{product.growth_rate >= 0 ? "+" : ""}{product.growth_rate}%</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Landed cost calculator */}
      <section className="rounded-2xl bg-slate-900/80 border border-slate-800 p-6" data-testid="landed-cost-section">
        <div className="flex items-center gap-2 mb-6">
          <Plane className="h-4 w-4 text-indigo-400" />
          <h2 className="text-lg font-bold text-slate-50">Landed cost to {country.flag} {country.name}</h2>
          <span className="text-[10px] text-slate-500 ml-2">Per unit · from China supplier</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {(["air", "sea"] as const).map((mode) => {
            const lc = mode === "air" ? product.landed_cost_air : product.landed_cost_sea;
            if (!lc) return null;
            const Icon = mode === "air" ? Plane : Ship;
            return (
              <div key={mode} className={`rounded-xl bg-slate-950/40 border p-4 ${mode === "air" ? "border-indigo-500/30" : "border-slate-800"}`}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Icon className={`h-3.5 w-3.5 ${mode === "air" ? "text-indigo-400" : "text-slate-400"}`} />
                    <span className="text-xs font-bold tracking-wider uppercase text-slate-100">{mode === "air" ? "Air Freight" : "Sea Freight"}</span>
                  </div>
                  <span className="text-[10px] font-bold text-emerald-400">{lc.lead_time_days} days</span>
                </div>
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-500">Unit cost</span>
                    <span className="tabular-nums font-semibold text-slate-100" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{lc.unit_cost_local}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-500">Shipping</span>
                    <span className="tabular-nums font-semibold text-slate-100" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{lc.shipping_local}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-500">Import duty ({lc.tariff_pct}%)</span>
                    <span className="tabular-nums font-semibold text-slate-100" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{lc.tariff_local}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-500">Customs fee</span>
                    <span className="tabular-nums font-semibold text-slate-100" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{lc.customs_fee_local}</span>
                  </div>
                </div>
                <div className="mt-3 pt-3 border-t border-slate-800 flex justify-between items-baseline">
                  <span className="text-[10px] font-bold tracking-wider uppercase text-emerald-400">Total landed</span>
                  <span className="text-xl font-extrabold text-emerald-400 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{lc.total_local}</span>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Tabbed content */}
      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="bg-slate-900 border border-slate-800 p-1 h-auto flex flex-wrap gap-1">
          <TabsTrigger value="overview" data-testid="tab-overview" className="text-xs sm:text-sm font-semibold data-[state=active]:bg-slate-800 data-[state=active]:text-slate-50">Overview</TabsTrigger>
          <TabsTrigger value="sales" data-testid="tab-sales" className="text-xs sm:text-sm font-semibold data-[state=active]:bg-slate-800 data-[state=active]:text-slate-50">Sales & Ads</TabsTrigger>
          <TabsTrigger value="sourcing" data-testid="tab-sourcing" className="text-xs sm:text-sm font-semibold data-[state=active]:bg-slate-800 data-[state=active]:text-slate-50">Sourcing & Profit</TabsTrigger>
          <TabsTrigger value="intel" data-testid="tab-intel" className="text-xs sm:text-sm font-semibold data-[state=active]:bg-slate-800 data-[state=active]:text-slate-50">Intelligence</TabsTrigger>
        </TabsList>

        {/* ============ OVERVIEW TAB ============ */}
        <TabsContent value="overview" className="mt-6 space-y-6">
          {/* Trend chart */}
          <section className="rounded-2xl bg-slate-900/80 border border-slate-800 p-6" data-testid="trend-recharts-container">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-bold text-slate-50">Trend trajectory</h2>
              <div className={`flex items-center gap-1 text-sm font-bold ${product.growth_rate >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                <TrendingUp className={`h-4 w-4 ${product.growth_rate >= 0 ? "" : "rotate-180"}`} />
                {product.growth_rate >= 0 ? "+" : ""}{product.growth_rate}%
              </div>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#10b981" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgb(30 41 59)" />
                  <XAxis dataKey="week" stroke="#64748b" fontSize={11} />
                  <YAxis stroke="#64748b" fontSize={11} domain={[0, 100]} />
                  <Tooltip contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, fontSize: 12 }} labelStyle={{ color: "#f8fafc", fontWeight: 700 }} />
                  <Area type="monotone" dataKey="score" stroke="#10b981" strokeWidth={2.5} fill="url(#scoreGradient)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </section>

          {/* Seasonal calendar */}
          <section className="rounded-2xl bg-slate-900/80 border border-slate-800 p-6" data-testid="seasonal-calendar">
            <div className="flex items-center gap-2 mb-6">
              <CalendarIcon className="h-4 w-4 text-indigo-400" />
              <h2 className="text-lg font-bold text-slate-50">Seasonal demand calendar</h2>
            </div>
            <SeasonalCalendar monthly={product.seasonal_demand} />
          </section>

          {/* Sales drivers */}
          <section className="rounded-2xl bg-slate-900/80 border border-slate-800 p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-bold text-slate-50 flex items-center gap-2">
                <Zap className="h-4 w-4 text-amber-400" />
                Sales drivers
              </h2>
              <span className="text-xs text-slate-500">{product.sales_drivers.length} tracked</span>
            </div>
            <div className="space-y-3">
              {product.sales_drivers.map((d) => (
                <div key={d.name} data-testid="sales-driver-item" className="rounded-xl bg-slate-950/40 border border-slate-800 p-4 hover:border-emerald-500/40 transition-all">
                  <div className="flex items-start justify-between gap-4 mb-2">
                    <div className="flex items-center gap-3 min-w-0">
                      <h3 className="font-bold text-sm text-slate-100 truncate">{d.name}</h3>
                      <span className={`text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-md border ${driverTypeColor[d.type] || "text-slate-400 bg-slate-500/10 border-slate-500/30"}`}>
                        {d.type.replace("_", " ")}
                      </span>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500">Impact</div>
                      <div className="text-xl font-extrabold text-emerald-400 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{d.impact_score}</div>
                    </div>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed">{d.description}</p>
                  <div className="mt-3 h-1 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-indigo-500" style={{ width: `${d.impact_score}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </section>
        </TabsContent>

        {/* ============ SALES & ADS TAB ============ */}
        <TabsContent value="sales" className="mt-6 space-y-6">
          {/* Channel recommendations */}
          <section className="rounded-2xl bg-slate-900/80 border border-slate-800 p-6" data-testid="channel-recommender">
            <div className="flex items-center gap-2 mb-6">
              <Store className="h-4 w-4 text-emerald-400" />
              <h2 className="text-lg font-bold text-slate-50">Best channels to sell on</h2>
            </div>
            <div className="space-y-3">
              {product.channel_recommendations.map((c, i) => (
                <div key={c.platform} data-testid="channel-recommendation" className="rounded-xl bg-slate-950/40 border border-slate-800 p-4 hover:border-emerald-500/40 transition-all">
                  <div className="flex items-start gap-4">
                    <div className="h-10 w-10 shrink-0 rounded-lg bg-gradient-to-br from-emerald-400 to-indigo-500 flex items-center justify-center text-slate-950 font-black text-sm">
                      #{i + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-3 flex-wrap">
                        <h3 className="font-bold text-sm text-slate-100">{c.platform}</h3>
                        <div className="flex items-center gap-3">
                          <div className="text-[10px] text-slate-500 uppercase font-semibold tracking-wider">Margin ~<span className="text-emerald-400 font-bold">{c.est_margin_pct}%</span></div>
                          <div className="text-lg font-extrabold text-emerald-400 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{c.score}</div>
                        </div>
                      </div>
                      <p className="text-xs text-slate-400 mt-1 leading-relaxed">{c.reason}</p>
                      <div className="mt-2 h-1 w-full bg-slate-800 rounded-full overflow-hidden">
                        <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-indigo-500" style={{ width: `${c.score}%` }} />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Ad Spend estimator */}
          <section className="rounded-2xl bg-slate-900/80 border border-slate-800 overflow-hidden" data-testid="ad-spend-estimator">
            <div className="p-6 pb-4 flex items-center gap-2">
              <Megaphone className="h-4 w-4 text-violet-400" />
              <h2 className="text-lg font-bold text-slate-50">Ad-spend to break into top 10</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-t border-slate-800 bg-slate-950/40">
                    <th className="text-left px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500">Platform</th>
                    <th className="text-left px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500">Monthly Budget</th>
                    <th className="text-left px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500">Expected ROAS</th>
                    <th className="text-left px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500">Difficulty</th>
                  </tr>
                </thead>
                <tbody>
                  {product.ad_spend_estimates.map((a) => (
                    <tr key={a.platform} className="border-t border-slate-800 hover:bg-slate-950/30" data-testid="ad-spend-row">
                      <td className="px-6 py-4 text-sm font-bold text-slate-100">{a.platform}</td>
                      <td className="px-6 py-4 text-sm text-emerald-400 tabular-nums font-semibold" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{a.monthly_budget}</td>
                      <td className="px-6 py-4 text-sm text-slate-200 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{a.expected_roas}</td>
                      <td className="px-6 py-4">
                        <span className={`text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-md border ${difficultyColor[a.difficulty] || ""}`}>{a.difficulty}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Bundle suggestions */}
          <section className="rounded-2xl bg-slate-900/80 border border-slate-800 p-6" data-testid="bundle-suggestions">
            <div className="flex items-center gap-2 mb-6">
              <Layers className="h-4 w-4 text-pink-400" />
              <h2 className="text-lg font-bold text-slate-50">Bundle opportunities</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {product.bundle_suggestions.map((b, i) => (
                <div key={i} data-testid="bundle-card" className="rounded-xl bg-slate-950/40 border border-slate-800 p-4 hover:border-pink-500/40 transition-all">
                  <div className="flex items-center justify-between mb-3">
                    <div className="text-[10px] font-bold tracking-wider uppercase text-pink-400">Bundle #{i + 1}</div>
                    <div className="flex items-baseline gap-2">
                      <span className="text-lg font-extrabold text-emerald-400 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{b.bundle_price}</span>
                      <span className="text-[10px] font-bold text-emerald-400">+{b.margin_uplift_pct}% margin</span>
                    </div>
                  </div>
                  <div className="space-y-1.5 mb-3">
                    {b.items.map((item) => (
                      <div key={item} className="flex items-center gap-2 text-sm text-slate-200">
                        <div className="h-1.5 w-1.5 rounded-full bg-pink-400" />
                        {item}
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed pt-3 border-t border-slate-800">{b.reason}</p>
                </div>
              ))}
            </div>
          </section>
        </TabsContent>

        {/* ============ SOURCING & PROFIT TAB ============ */}
        <TabsContent value="sourcing" className="mt-6 space-y-6">
          {/* Profit calculator */}
          <section className="rounded-2xl bg-gradient-to-br from-slate-900 to-indigo-950/40 border border-slate-800 p-6" data-testid="profit-calculator">
            <div className="flex items-center gap-2 mb-6">
              <Target className="h-4 w-4 text-emerald-400" />
              <h2 className="text-lg font-bold text-slate-50">Profit calculator</h2>
            </div>
            <ProfitCalculator product={product} />
          </section>

          {/* Suppliers */}
          {product.suppliers && product.suppliers.length > 0 && (
            <section className="rounded-2xl bg-slate-900/80 border border-slate-800 p-6" data-testid="suppliers-section">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-bold text-slate-50 flex items-center gap-2">
                  <Factory className="h-4 w-4 text-indigo-400" />
                  Verified suppliers
                </h2>
                <span className="text-xs text-slate-500">{product.suppliers.length} options</span>
              </div>
              <div className="space-y-3">
                {product.suppliers.map((s) => (
                  <a key={`${s.name}-${s.platform}`} href={s.url} target="_blank" rel="noopener noreferrer" data-testid="supplier-item" className="block rounded-xl bg-slate-950/40 border border-slate-800 p-4 hover:border-indigo-500/40 transition-all">
                    <div className="flex items-start justify-between gap-4 mb-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="font-bold text-sm text-slate-100 truncate">{s.name}</h3>
                          <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-md border border-indigo-500/30 bg-indigo-500/10 text-indigo-400">{s.platform}</span>
                        </div>
                        <div className="mt-1.5 flex items-center gap-1 text-xs text-amber-400">
                          <Star className="h-3 w-3 fill-current" />
                          <span className="font-bold tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{s.rating.toFixed(1)}</span>
                        </div>
                      </div>
                      <ExternalLink className="h-4 w-4 text-slate-500 shrink-0" />
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      <div>
                        <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500 flex items-center gap-1"><DollarSign className="h-3 w-3" /> Unit</div>
                        <div className="text-xs font-bold text-emerald-400 mt-0.5 tabular-nums">{s.unit_price}</div>
                      </div>
                      <div>
                        <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500 flex items-center gap-1"><Package className="h-3 w-3" /> MOQ</div>
                        <div className="text-xs font-bold text-slate-100 mt-0.5 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{s.moq === 1 ? "None" : `${s.moq}`}</div>
                      </div>
                      <div>
                        <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500 flex items-center gap-1"><Clock className="h-3 w-3" /> Lead</div>
                        <div className="text-xs font-bold text-slate-100 mt-0.5 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{s.lead_time_days}d</div>
                      </div>
                    </div>
                  </a>
                ))}
              </div>
            </section>
          )}
        </TabsContent>

        {/* ============ INTELLIGENCE TAB ============ */}
        <TabsContent value="intel" className="mt-6 space-y-6">
          {/* Market brief */}
          <section className="rounded-2xl bg-slate-900/80 border border-slate-800 p-6" data-testid="market-brief-section">
            <div className="flex items-center justify-between mb-6 gap-3 flex-wrap">
              <h2 className="text-lg font-bold text-slate-50 flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-emerald-400" />
                AI Market Brief
              </h2>
              <button
                onClick={() => briefMutation.mutate(!!product.market_brief)}
                disabled={briefMutation.isPending}
                data-testid="generate-brief-button"
                className="h-9 px-4 rounded-xl bg-gradient-to-br from-emerald-500 to-indigo-500 text-slate-950 font-semibold text-xs flex items-center gap-2 shadow-lg shadow-emerald-500/20 hover:-translate-y-0.5 transition-all disabled:opacity-70 disabled:cursor-not-allowed"
              >
                <Sparkles className={`h-3.5 w-3.5 ${briefMutation.isPending ? "animate-spin" : ""}`} />
                {briefMutation.isPending ? "Generating…" : product.market_brief ? "Regenerate" : "Generate Brief"}
              </button>
            </div>
            {product.market_brief ? (
              <MarketBriefView brief={product.market_brief} productName={product.name} />
            ) : (
              <div className="text-center py-12 rounded-xl border border-dashed border-slate-800">
                <Sparkles className="h-6 w-6 text-slate-600 mx-auto mb-3" />
                <p className="text-sm text-slate-400">Click "Generate Brief" for a 1-page AI market summary.</p>
              </div>
            )}
          </section>

          {/* Niches */}
          <section className="rounded-2xl bg-slate-900/80 border border-slate-800 p-6" data-testid="niches-section">
            <div className="flex items-center justify-between mb-6 gap-3 flex-wrap">
              <h2 className="text-lg font-bold text-slate-50 flex items-center gap-2">
                <Search className="h-4 w-4 text-violet-400" />
                Niche opportunities
              </h2>
              <button
                onClick={() => nichesMutation.mutate()}
                disabled={nichesMutation.isPending}
                data-testid="generate-niches-button"
                className="h-9 px-4 rounded-xl bg-slate-800 border border-slate-700 text-slate-100 font-semibold text-xs flex items-center gap-2 hover:border-violet-500/40 transition-all disabled:opacity-70"
              >
                <Sparkles className={`h-3.5 w-3.5 ${nichesMutation.isPending ? "animate-spin" : ""}`} />
                {nichesMutation.isPending ? "Mining…" : "Regenerate with AI"}
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {product.niches.map((n, i) => (
                <div key={i} data-testid="niche-item" className="rounded-xl bg-slate-950/40 border border-slate-800 p-4 hover:border-violet-500/40 transition-all">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm text-slate-100 font-medium leading-snug flex-1">{n.name}</p>
                    <span className={`text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-md border shrink-0 ${compColor[n.competition] || compColor.Medium}`}>{n.competition}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Competitors */}
          <section className="rounded-2xl bg-slate-900/80 border border-slate-800 p-6" data-testid="competitors-section">
            <div className="flex items-center gap-2 mb-6">
              <Trophy className="h-4 w-4 text-amber-400" />
              <h2 className="text-lg font-bold text-slate-50">Top competitors · {country.flag} {country.name}</h2>
            </div>
            <div className="space-y-3">
              {(product.local_competitors && product.local_competitors.length > 0 ? product.local_competitors : product.competitors).map((c, i) => (
                <div key={c.name} data-testid="competitor-row" className="flex items-center gap-4 rounded-xl bg-slate-950/40 border border-slate-800 p-4">
                  <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-amber-400 to-rose-500 flex items-center justify-center text-slate-950 font-black text-sm shrink-0">#{i + 1}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-3 flex-wrap">
                      <h3 className="font-bold text-sm text-slate-100 truncate">{c.name}</h3>
                      <div className="text-sm font-bold text-emerald-400 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{c.monthly_revenue}/mo</div>
                    </div>
                    <div className="mt-1 flex items-center justify-between gap-3 flex-wrap">
                      <span className="text-xs text-slate-400">{c.platform}</span>
                      <div className="flex items-center gap-2">
                        <div className="text-[10px] text-slate-500 uppercase font-semibold tracking-wider">Strength</div>
                        <div className="h-1.5 w-24 bg-slate-800 rounded-full overflow-hidden">
                          <div className="h-full bg-gradient-to-r from-amber-400 to-rose-500" style={{ width: `${c.strength}%` }} />
                        </div>
                        <div className="text-xs font-bold text-slate-100 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{c.strength}</div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default ProductDetail;
