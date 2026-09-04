import React from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchProducts } from "@/lib/api";
import { Zap } from "lucide-react";

const driverTypeColor: Record<string, string> = {
  marketplace: "bg-pink-500/10 text-pink-400 border-pink-500/30",
  ads: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  influencer: "bg-purple-500/10 text-purple-400 border-purple-500/30",
  shopify_app: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  analytics: "bg-indigo-500/10 text-indigo-400 border-indigo-500/30",
  email: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  loyalty: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
};

interface Aggregated {
  name: string;
  type: string;
  totalImpact: number;
  productCount: number;
  avgImpact: number;
  descriptions: string[];
}

const Drivers: React.FC<{ search: string }> = ({ search }) => {
  const { data: products = [] } = useQuery({ queryKey: ["products-all-drivers"], queryFn: () => fetchProducts({}) });

  const aggregated: Aggregated[] = React.useMemo(() => {
    const map = new Map<string, Aggregated>();
    for (const p of products) {
      for (const d of p.sales_drivers) {
        const key = d.name;
        const existing = map.get(key);
        if (existing) {
          existing.totalImpact += d.impact_score;
          existing.productCount += 1;
          existing.descriptions.push(d.description);
        } else {
          map.set(key, {
            name: d.name,
            type: d.type,
            totalImpact: d.impact_score,
            productCount: 1,
            avgImpact: 0,
            descriptions: [d.description],
          });
        }
      }
    }
    const arr = Array.from(map.values()).map((a) => ({ ...a, avgImpact: Math.round(a.totalImpact / a.productCount) }));
    arr.sort((a, b) => b.totalImpact - a.totalImpact);
    return arr;
  }, [products]);

  const filtered = search
    ? aggregated.filter((a) => a.name.toLowerCase().includes(search.toLowerCase()) || a.type.toLowerCase().includes(search.toLowerCase()))
    : aggregated;

  return (
    <div className="space-y-8" data-testid="drivers-page">
      <div>
        <div className="text-xs font-semibold tracking-[0.2em] uppercase text-emerald-400 mb-2">Sales Driver Index</div>
        <h1
          className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-50"
          style={{ fontFamily: "'Plus Jakarta Sans', sans-serif" }}
        >
          The stack behind every winner.
        </h1>
        <p className="mt-2 text-sm text-slate-400">Ranked list of apps, ad platforms & tools by their aggregate impact across tracked products.</p>
      </div>

      <div className="rounded-2xl bg-slate-900/80 border border-slate-800 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-950/60">
              <th className="text-left px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500">Driver</th>
              <th className="text-left px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500">Type</th>
              <th className="text-right px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500 hidden sm:table-cell">Products</th>
              <th className="text-right px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500">Avg Impact</th>
              <th className="text-right px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500">Total</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((d) => (
              <tr key={d.name} className="border-b border-slate-800 last:border-b-0 hover:bg-slate-950/30 transition-colors" data-testid="driver-row">
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                      <Zap className="h-3.5 w-3.5 text-emerald-400" />
                    </div>
                    <div>
                      <div className="text-sm font-bold text-slate-100">{d.name}</div>
                      <div className="text-[11px] text-slate-500 max-w-md line-clamp-1">{d.descriptions[0]}</div>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <span className={`text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-md border ${driverTypeColor[d.type] || "text-slate-400 bg-slate-500/10 border-slate-500/30"}`}>
                    {d.type.replace("_", " ")}
                  </span>
                </td>
                <td className="px-6 py-4 text-right text-sm text-slate-300 hidden sm:table-cell tabular-nums">{d.productCount}</td>
                <td className="px-6 py-4 text-right">
                  <div className="inline-flex items-center gap-2">
                    <div className="h-1.5 w-16 rounded-full bg-slate-800 overflow-hidden hidden md:block">
                      <div className="h-full bg-gradient-to-r from-emerald-400 to-indigo-500" style={{ width: `${d.avgImpact}%` }} />
                    </div>
                    <span className="text-sm font-bold text-slate-50 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{d.avgImpact}</span>
                  </div>
                </td>
                <td className="px-6 py-4 text-right text-sm font-bold text-emerald-400 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{d.totalImpact}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="p-12 text-center text-sm text-slate-400">No drivers match your search.</div>
        )}
      </div>
    </div>
  );
};

export default Drivers;
