import React from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchSuppliers } from "@/lib/api";
import { Factory, Star, ExternalLink, Package, Clock, DollarSign, Search as SearchIcon } from "lucide-react";

const platformColor: Record<string, string> = {
  "Alibaba": "bg-orange-500/10 text-orange-400 border-orange-500/30",
  "AliExpress": "bg-red-500/10 text-red-400 border-red-500/30",
  "DHgate": "bg-blue-500/10 text-blue-400 border-blue-500/30",
  "Faire": "bg-rose-500/10 text-rose-400 border-rose-500/30",
  "Spocket": "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  "Zendrop": "bg-purple-500/10 text-purple-400 border-purple-500/30",
  "CJ Dropshipping": "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
  "Global Sources": "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
};

const Suppliers: React.FC<{ search: string }> = ({ search }) => {
  const { data, isLoading } = useQuery({ queryKey: ["suppliers"], queryFn: fetchSuppliers });

  const [platformFilter, setPlatformFilter] = React.useState("All");
  const suppliers = data?.suppliers || [];

  const platforms = React.useMemo(() => {
    const set = new Set<string>();
    suppliers.forEach((s) => set.add(s.platform));
    return ["All", ...Array.from(set).sort()];
  }, [suppliers]);

  const filtered = suppliers.filter((s) => {
    if (platformFilter !== "All" && s.platform !== platformFilter) return false;
    if (!search) return true;
    const q = search.toLowerCase();
    return s.name.toLowerCase().includes(q) || s.platform.toLowerCase().includes(q) || s.categories.some((c) => c.toLowerCase().includes(q));
  });

  return (
    <div className="space-y-8" data-testid="suppliers-page">
      <div>
        <div className="text-xs font-semibold tracking-[0.2em] uppercase text-emerald-400 mb-2">Sourcing Intelligence</div>
        <h1
          className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-50"
          style={{ fontFamily: "'Plus Jakarta Sans', sans-serif" }}
        >
          Source it. Ship it. <span className="text-indigo-400">Sell it.</span>
        </h1>
        <p className="mt-2 text-sm text-slate-400 max-w-2xl">
          Verified manufacturers, dropshipping platforms, and wholesale networks behind every trending product — with MOQ, unit price, and lead time at a glance.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {platforms.map((p) => (
            <button
              key={p}
              onClick={() => setPlatformFilter(p)}
              data-testid="supplier-platform-chip"
              className={`px-4 py-2 rounded-full text-xs font-semibold tracking-wide transition-all duration-200 border ${
                platformFilter === p
                  ? "bg-slate-50 text-slate-950 border-slate-50 shadow-lg shadow-indigo-500/10"
                  : "bg-slate-900 text-slate-300 border-slate-800 hover:border-slate-700 hover:text-slate-100"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
        <div className="text-xs text-slate-400">
          <span className="text-emerald-400 font-bold">{filtered.length}</span> of {suppliers.length} suppliers
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-56 rounded-2xl bg-slate-900/60 border border-slate-800 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((s) => (
            <a
              key={`${s.name}-${s.platform}`}
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              data-testid="supplier-card"
              className="group rounded-2xl bg-slate-900/80 border border-slate-800 p-5 hover:border-indigo-500/50 hover:-translate-y-1 hover:shadow-2xl hover:shadow-indigo-500/10 transition-all duration-200"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="h-10 w-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                  <Factory className="h-4 w-4 text-indigo-400" />
                </div>
                <ExternalLink className="h-4 w-4 text-slate-500 group-hover:text-emerald-400 transition-colors" />
              </div>

              <h3 className="font-bold text-sm text-slate-100 group-hover:text-emerald-400 transition-colors line-clamp-1">
                {s.name}
              </h3>

              <div className="mt-2 flex items-center gap-2 flex-wrap">
                <span className={`text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-md border ${platformColor[s.platform] || "bg-slate-500/10 text-slate-300 border-slate-500/30"}`}>
                  {s.platform}
                </span>
                <div className="flex items-center gap-1 text-xs text-amber-400">
                  <Star className="h-3 w-3 fill-current" />
                  <span className="font-bold tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{s.rating.toFixed(1)}</span>
                </div>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-3 pt-4 border-t border-slate-800">
                <div>
                  <div className="text-[9px] font-semibold tracking-wider uppercase text-slate-500 flex items-center gap-1">
                    <DollarSign className="h-2.5 w-2.5" /> Unit
                  </div>
                  <div className="text-xs font-bold text-emerald-400 mt-0.5 tabular-nums truncate">{s.unit_price}</div>
                </div>
                <div>
                  <div className="text-[9px] font-semibold tracking-wider uppercase text-slate-500 flex items-center gap-1">
                    <Package className="h-2.5 w-2.5" /> MOQ
                  </div>
                  <div className="text-xs font-bold text-slate-100 mt-0.5 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                    {s.moq === 1 ? "None" : s.moq}
                  </div>
                </div>
                <div>
                  <div className="text-[9px] font-semibold tracking-wider uppercase text-slate-500 flex items-center gap-1">
                    <Clock className="h-2.5 w-2.5" /> Lead
                  </div>
                  <div className="text-xs font-bold text-slate-100 mt-0.5 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                    {s.lead_time_days}d
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-slate-800">
                <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500 mb-1.5">
                  Products supplied ({s.product_count})
                </div>
                <div className="text-xs text-slate-300 line-clamp-2 leading-relaxed">
                  {s.products.slice(0, 3).join(" · ")}
                  {s.products.length > 3 && ` · +${s.products.length - 3} more`}
                </div>
              </div>
            </a>
          ))}
        </div>
      )}

      {!isLoading && filtered.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-800 p-12 text-center">
          <SearchIcon className="h-6 w-6 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400 text-sm">No suppliers match your filters.</p>
        </div>
      )}
    </div>
  );
};

export default Suppliers;
