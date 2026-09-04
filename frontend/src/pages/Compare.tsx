import React from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { compareProducts } from "@/lib/api";
import { useCompare } from "@/context/AppState";
import { useLocation } from "@/context/LocationContext";
import { Layers, X, Trophy, Download, ArrowLeft } from "lucide-react";
import { exportProductsToCSV } from "@/lib/csv";
import { toast } from "sonner";
import { PlatformBadge } from "@/components/PlatformBadge";
import { SaturationPill } from "@/components/SaturationPill";

const winner = (a: number, b: number, higherIsBetter = true): 0 | 1 | -1 => {
  if (a === b) return 0;
  const aWins = higherIsBetter ? a > b : a < b;
  return aWins ? -1 : 1; // -1 means "a wins"
};

const WinnerPill: React.FC<{ status: 0 | 1 | -1; side: "a" | "b" }> = ({ status, side }) => {
  if (status === 0) return <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Tie</span>;
  const wins = (status === -1 && side === "a") || (status === 1 && side === "b");
  return wins ? (
    <span className="inline-flex items-center gap-1 text-[9px] font-bold text-emerald-400 uppercase tracking-widest">
      <Trophy className="h-3 w-3" /> Wins
    </span>
  ) : (
    <span className="text-[9px] font-bold text-slate-600 uppercase tracking-widest">—</span>
  );
};

const Compare: React.FC = () => {
  const { ids, clear, toggle } = useCompare();
  const { country } = useLocation();

  const { data: products = [], isLoading } = useQuery({
    queryKey: ["compare", ids, country.code],
    queryFn: () => compareProducts(ids, country.code),
    enabled: ids.length > 0,
  });

  if (ids.length === 0) {
    return (
      <div className="space-y-6" data-testid="compare-page">
        <div>
          <div className="text-xs font-semibold tracking-[0.2em] uppercase text-indigo-400 mb-2 flex items-center gap-2">
            <Layers className="h-3.5 w-3.5" /> Head-to-Head
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-50" style={{ fontFamily: "'Plus Jakarta Sans', sans-serif" }}>
            Compare products side-by-side.
          </h1>
        </div>
        <div className="rounded-2xl border border-dashed border-slate-800 p-16 text-center">
          <Layers className="h-8 w-8 text-slate-600 mx-auto mb-4" />
          <p className="text-slate-400 text-sm mb-4">No products selected yet. Tap the <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-xs font-bold text-slate-200">VS</span> button on any product card to add it here.</p>
          <Link to="/" className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-400 hover:gap-2 transition-all">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to dashboard
          </Link>
        </div>
      </div>
    );
  }

  if (isLoading || products.length === 0) {
    return <div className="h-96 rounded-2xl bg-slate-900 animate-pulse" data-testid="compare-page" />;
  }

  const [a, b] = products;

  const rows: { label: string; a: any; b: any; aScore?: number; bScore?: number; higherBetter?: boolean; format?: (v: any) => React.ReactNode }[] = [
    { label: `Local score (${country.flag})`, a: a.local_score ?? a.trend_score, b: b?.local_score ?? b?.trend_score, aScore: a.local_score ?? a.trend_score, bScore: b?.local_score ?? b?.trend_score },
    { label: "Global score", a: a.global_score ?? a.trend_score, b: b?.global_score ?? b?.trend_score, aScore: a.global_score ?? a.trend_score, bScore: b?.global_score ?? b?.trend_score },
    { label: "Opportunity score", a: a.opportunity_score, b: b?.opportunity_score, aScore: a.opportunity_score, bScore: b?.opportunity_score },
    { label: "Velocity %", a: `${a.velocity_pct >= 0 ? "+" : ""}${a.velocity_pct}%`, b: b ? `${b.velocity_pct >= 0 ? "+" : ""}${b.velocity_pct}%` : "—", aScore: a.velocity_pct, bScore: b?.velocity_pct ?? 0 },
    { label: "Growth rate", a: `${a.growth_rate >= 0 ? "+" : ""}${a.growth_rate}%`, b: b ? `${b.growth_rate >= 0 ? "+" : ""}${b.growth_rate}%` : "—", aScore: a.growth_rate, bScore: b?.growth_rate ?? 0 },
    { label: "Saturation", a: a.saturation_label, b: b?.saturation_label, aScore: a.saturation_score, bScore: b?.saturation_score, higherBetter: false },
    { label: "Est. monthly revenue", a: a.local_estimated_monthly_revenue || a.estimated_monthly_revenue, b: b?.local_estimated_monthly_revenue || b?.estimated_monthly_revenue },
    { label: "Local price range", a: a.local_price_range || a.price_range, b: b?.local_price_range || b?.price_range },
    { label: "Sales drivers count", a: a.sales_drivers.length, b: b?.sales_drivers.length ?? 0, aScore: a.sales_drivers.length, bScore: b?.sales_drivers.length ?? 0 },
    { label: "Suppliers available", a: a.suppliers.length, b: b?.suppliers.length ?? 0, aScore: a.suppliers.length, bScore: b?.suppliers.length ?? 0 },
  ];

  return (
    <div className="space-y-6" data-testid="compare-page">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div className="text-xs font-semibold tracking-[0.2em] uppercase text-indigo-400 mb-2 flex items-center gap-2">
            <Layers className="h-3.5 w-3.5" /> Head-to-Head · {country.flag} {country.name}
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-50" style={{ fontFamily: "'Plus Jakarta Sans', sans-serif" }}>Compare</h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              exportProductsToCSV(products, `compare-${country.code}.csv`);
              toast.success("Comparison exported");
            }}
            data-testid="compare-export"
            className="h-9 px-3 rounded-lg bg-slate-900 border border-slate-800 text-slate-100 text-xs font-semibold flex items-center gap-1.5 hover:border-emerald-500/40"
          >
            <Download className="h-3.5 w-3.5" /> Export
          </button>
          <button onClick={clear} className="h-9 px-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-semibold flex items-center gap-1.5 hover:bg-rose-500/20">
            <X className="h-3.5 w-3.5" /> Clear
          </button>
        </div>
      </div>

      {/* Side-by-side headers */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[a, b].filter(Boolean).map((p, idx) => (
          <div key={p.id} className="rounded-2xl bg-slate-900/80 border border-slate-800 overflow-hidden" data-testid="compare-column">
            <div className="relative h-40 bg-slate-950">
              <img src={p.image_url} alt={p.name} className="h-full w-full object-cover opacity-90" />
              <div className="absolute inset-0 bg-gradient-to-t from-slate-950/95 via-slate-950/20 to-transparent" />
              <button
                onClick={() => toggle(p.id)}
                className="absolute top-3 right-3 h-8 w-8 rounded-lg bg-slate-950/80 border border-slate-800 flex items-center justify-center text-slate-400 hover:text-rose-400"
              >
                <X className="h-4 w-4" />
              </button>
              <div className="absolute bottom-0 left-0 right-0 p-4">
                <div className="text-[10px] font-semibold tracking-widest uppercase text-emerald-400 mb-1">Option {String.fromCharCode(65 + idx)} · {p.category}</div>
                <h3 className="text-lg font-extrabold text-slate-50 leading-tight" style={{ fontFamily: "'Plus Jakarta Sans', sans-serif" }}>{p.name}</h3>
              </div>
            </div>
            <div className="p-4 space-y-3">
              <div className="flex flex-wrap gap-1.5">
                {(p.local_platforms || p.trending_platforms).slice(0, 4).map((pl: string) => <PlatformBadge key={pl} platform={pl} />)}
              </div>
              <SaturationPill score={p.saturation_score} label={p.saturation_label} />
            </div>
          </div>
        ))}
      </div>

      {/* Comparison table */}
      {b && (
        <div className="rounded-2xl bg-slate-900/80 border border-slate-800 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-950/60">
                <th className="text-left px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500">Metric</th>
                <th className="text-left px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500">Option A</th>
                <th className="text-center px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500">→</th>
                <th className="text-left px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500">Option B</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const status = r.aScore !== undefined && r.bScore !== undefined
                  ? winner(r.aScore, r.bScore, r.higherBetter !== false)
                  : 0;
                return (
                  <tr key={r.label} className="border-b border-slate-800 last:border-b-0 hover:bg-slate-950/30" data-testid="compare-row">
                    <td className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">{r.label}</td>
                    <td className="px-6 py-4">
                      <div className={`text-sm font-bold tabular-nums ${status === -1 ? "text-emerald-400" : "text-slate-100"}`} style={{ fontFamily: "'JetBrains Mono', monospace" }}>{r.a}</div>
                      <WinnerPill status={status} side="a" />
                    </td>
                    <td className="px-6 py-4 text-center text-slate-600">·</td>
                    <td className="px-6 py-4">
                      <div className={`text-sm font-bold tabular-nums ${status === 1 ? "text-emerald-400" : "text-slate-100"}`} style={{ fontFamily: "'JetBrains Mono', monospace" }}>{r.b}</div>
                      <WinnerPill status={status} side="b" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {!b && (
        <div className="rounded-2xl border border-dashed border-slate-800 p-8 text-center text-sm text-slate-400">
          Add one more product to see head-to-head comparison.
        </div>
      )}
    </div>
  );
};

export default Compare;
