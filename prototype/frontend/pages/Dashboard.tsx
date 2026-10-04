import React from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchProducts, fetchCategories, fetchTrends } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import CategoryChips from "@/components/CategoryChips";
import KPICard from "@/components/KPICard";
import { Package, Gauge, Rocket, Layers, Download, Sparkles } from "lucide-react";
import { useLocation } from "@/context/LocationContext";
import { exportProductsToCSV } from "@/lib/csv";
import { toast } from "sonner";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from "recharts";

interface Props {
  search: string;
}

const chartColors = ["#10b981", "#6366f1", "#8b5cf6", "#f59e0b", "#f43f5e"];

const Dashboard: React.FC<Props> = ({ search }) => {
  const [category, setCategory] = React.useState("All");
  const [earlyOnly, setEarlyOnly] = React.useState(false);
  const { country } = useLocation();

  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: fetchCategories });
  const { data: trends } = useQuery({ queryKey: ["trends", country.code], queryFn: fetchTrends });
  const { data: products = [], isLoading } = useQuery({
    queryKey: ["products", category, search, earlyOnly, country.code],
    queryFn: () => fetchProducts({ category, search, early_only: earlyOnly, country: country.code }),
  });

  const trendSeriesKeys = trends?.trend_series?.length
    ? Object.keys(trends.trend_series[0]).filter((k) => k !== "week")
    : [];

  const handleExport = () => {
    if (!products.length) {
      toast.error("No products to export");
      return;
    }
    exportProductsToCSV(products, `trendsell-${country.code}-${new Date().toISOString().split("T")[0]}.csv`);
    toast.success(`Exported ${products.length} products to CSV`);
  };

  return (
    <div className="space-y-8" data-testid="dashboard-page">
      <section className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div>
          <div className="text-xs font-semibold tracking-[0.2em] uppercase text-emerald-400 mb-2 flex items-center gap-2">
            <span>{country.flag}</span> {country.name} Intelligence
          </div>
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-slate-50" style={{ fontFamily: "'Plus Jakarta Sans', sans-serif" }}>
            What's selling & <span className="text-emerald-400">why</span>.
          </h1>
          <p className="mt-2 text-sm text-slate-400 max-w-2xl leading-relaxed">
            Live pulse of trending products calibrated for the <span className="text-slate-200 font-semibold">{country.name}</span> market — with local platform rankings, PPP-adjusted pricing, and sourcing intelligence.
          </p>
        </div>
      </section>

      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard label="Tracked Products" value={trends?.total_products ?? 0} sub="Refreshed hourly" icon={Package} accent="emerald" />
        <KPICard label="Avg Opportunity" value={`${trends?.avg_opportunity ?? 0}`} sub="Composite score" icon={Gauge} accent="indigo" />
        <KPICard label="Top Platform" value={trends?.top_velocity_platform ?? "—"} sub="Leading globally" icon={Rocket} accent="violet" />
        <KPICard label="Early Opportunities" value={trends?.early_opportunities ?? 0} sub="TikTok-led, low saturation" icon={Sparkles} accent="amber" />
      </section>

      <section className="rounded-2xl bg-slate-900/80 border border-slate-800 p-6" data-testid="trend-recharts-container">
        <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-50">Top 5 · 7-Week Trajectory</h2>
            <p className="text-xs text-slate-500 mt-0.5">Weekly composite trend score across leading products</p>
          </div>
          <div className="text-[10px] font-semibold tracking-wider uppercase text-emerald-400 px-2 py-1 rounded-md border border-emerald-500/30 bg-emerald-500/10">Live</div>
        </div>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trends?.trend_series || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgb(30 41 59)" />
              <XAxis dataKey="week" stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} domain={[30, 100]} />
              <Tooltip contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, fontSize: 12 }} labelStyle={{ color: "#f8fafc", fontWeight: 700 }} />
              <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
              {trendSeriesKeys.map((k, i) => (
                <Line key={k} type="monotone" dataKey={k} stroke={chartColors[i % chartColors.length]} strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 5 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="text-2xl font-bold text-slate-50">Trending in {country.flag} {country.name}</h2>
            <p className="text-xs text-slate-500 mt-0.5">Click any product to unlock local + global sales-driver breakdown.</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setEarlyOnly((v) => !v)}
              data-testid="early-only-toggle"
              className={`h-9 px-3 rounded-lg text-xs font-semibold border transition-all ${
                earlyOnly ? "bg-emerald-500 text-slate-950 border-emerald-400" : "bg-slate-900 text-slate-300 border-slate-800 hover:border-slate-700"
              }`}
            >
              🚀 Early only
            </button>
            <button
              onClick={handleExport}
              data-testid="export-csv-button"
              className="h-9 px-3 rounded-lg bg-slate-900 border border-slate-800 text-slate-100 text-xs font-semibold flex items-center gap-1.5 hover:border-emerald-500/40 transition-all"
            >
              <Download className="h-3.5 w-3.5" /> Export CSV
            </button>
          </div>
        </div>

        <CategoryChips categories={categories} active={category} onChange={setCategory} />

        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="h-96 rounded-2xl bg-slate-900/60 border border-slate-800 animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6" data-testid="product-grid">
            {products.map((p, i) => <ProductCard key={p.id} product={p} index={i} />)}
          </div>
        )}

        {!isLoading && products.length === 0 && (
          <div className="rounded-2xl border border-dashed border-slate-800 p-12 text-center">
            <p className="text-slate-400 text-sm">No products match your filters.</p>
          </div>
        )}
      </section>
    </div>
  );
};

export default Dashboard;
