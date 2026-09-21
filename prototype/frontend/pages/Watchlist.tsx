import React from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchProducts } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import { useWatchlist } from "@/context/AppState";
import { useLocation } from "@/context/LocationContext";
import { Star, TrendingUp, TrendingDown } from "lucide-react";

const Watchlist: React.FC = () => {
  const { entries } = useWatchlist();
  const { country } = useLocation();

  const { data: products = [], isLoading } = useQuery({
    queryKey: ["watchlist-products", country.code],
    queryFn: () => fetchProducts({ country: country.code }),
    enabled: entries.length > 0,
  });

  const savedProducts = products.filter((p) => entries.some((e) => e.id === p.id));

  return (
    <div className="space-y-8" data-testid="watchlist-page">
      <div>
        <div className="text-xs font-semibold tracking-[0.2em] uppercase text-amber-400 mb-2 flex items-center gap-2">
          <Star className="h-3.5 w-3.5 fill-current" /> Your Watchlist
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-50" style={{ fontFamily: "'Plus Jakarta Sans', sans-serif" }}>
          Products you're tracking.
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Score deltas show how each product has moved since you saved it — jump on the risers.
        </p>
      </div>

      {entries.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-800 p-16 text-center">
          <Star className="h-8 w-8 text-slate-600 mx-auto mb-4" />
          <p className="text-slate-400 text-sm">Your watchlist is empty. Tap the ⭐ on any product card to start tracking.</p>
        </div>
      ) : isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {entries.map((_, i) => (
            <div key={i} className="h-96 rounded-2xl bg-slate-900/60 border border-slate-800 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {savedProducts.map((p, i) => {
            const entry = entries.find((e) => e.id === p.id)!;
            const delta = p.trend_score - entry.lastKnownScore;
            return (
              <div key={p.id} className="relative">
                <ProductCard product={p} index={i} />
                {delta !== 0 && (
                  <div
                    data-testid="watchlist-delta-badge"
                    className={`absolute -top-2 left-4 z-30 px-2 py-1 rounded-md text-[10px] font-bold tracking-wider uppercase shadow-lg flex items-center gap-1 ${
                      delta > 0
                        ? "bg-emerald-500 text-slate-950 shadow-emerald-500/40"
                        : "bg-rose-500 text-slate-50 shadow-rose-500/40"
                    }`}
                  >
                    {delta > 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                    {delta > 0 ? "+" : ""}
                    {delta} pts
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default Watchlist;
