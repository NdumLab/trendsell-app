import React from "react";
import { Link } from "react-router-dom";
import { TrendingUp, ArrowUpRight, Flame, Star, Rocket, Info, Check, Sparkles, Compass } from "lucide-react";
import { PlatformBadge } from "@/components/PlatformBadge";
import { SaturationPill } from "@/components/SaturationPill";
import { useWatchlist, useCompare } from "@/context/AppState";
import { useLocation } from "@/context/LocationContext";
import type { Product } from "@/types";

const demandColor = (d: string) => {
  switch (d) {
    case "very_high":
      return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
    case "high":
      return "text-indigo-400 bg-indigo-500/10 border-indigo-500/30";
    case "medium":
      return "text-amber-400 bg-amber-500/10 border-amber-500/30";
    default:
      return "text-slate-400 bg-slate-500/10 border-slate-500/30";
  }
};

const velocityStyle = (label: string) => {
  switch (label) {
    case "surging":
      return { color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/30", arrow: "▲▲" };
    case "climbing":
      return { color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/30", arrow: "▲" };
    case "flat":
      return { color: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/30", arrow: "▬" };
    default:
      return { color: "text-rose-400", bg: "bg-rose-500/10 border-rose-500/30", arrow: "▼" };
  }
};

const regulationColor = (flag?: string) => {
  if (flag === "restricted") return "bg-rose-500";
  if (flag === "certification") return "bg-amber-500";
  return "bg-emerald-500";
};

const ProductCard: React.FC<{ product: Product; index?: number }> = ({ product, index = 0 }) => {
  const { isSaved, toggle: toggleSaved } = useWatchlist();
  const { isSelected, toggle: toggleCompare } = useCompare();
  const { country } = useLocation();
  const [showWhy, setShowWhy] = React.useState(false);

  const saved = isSaved(product.id);
  const selected = isSelected(product.id);
  const vs = velocityStyle(product.velocity_label);

  const localScore = product.local_score ?? product.trend_score;
  const globalScore = product.global_score ?? product.trend_score;
  const priceDisplay = product.local_price_range || product.price_range;

  return (
    <div
      data-testid="product-card"
      className="group relative flex flex-col rounded-2xl bg-slate-900/80 border border-slate-800 overflow-hidden hover:border-emerald-500/50 hover:-translate-y-1 hover:shadow-2xl hover:shadow-emerald-500/10 transition-all duration-200"
      style={{ animationDelay: `${index * 40}ms` }}
    >
      {/* Top-right action buttons */}
      <div className="absolute top-3 right-3 z-20 flex items-center gap-1.5">
        <button
          onClick={(e) => {
            e.preventDefault();
            toggleCompare(product.id);
          }}
          aria-label={selected ? "Remove from compare" : "Add to compare"}
          data-testid="product-compare-checkbox"
          className={`h-8 w-8 rounded-lg backdrop-blur-md flex items-center justify-center border transition-all ${
            selected
              ? "bg-emerald-500 border-emerald-400 text-slate-950"
              : "bg-slate-950/70 border-slate-700 text-slate-400 hover:text-emerald-400 hover:border-emerald-500/50"
          }`}
        >
          {selected ? <Check className="h-4 w-4" strokeWidth={3} /> : <span className="text-[10px] font-bold tracking-wider">VS</span>}
        </button>
        <button
          onClick={(e) => {
            e.preventDefault();
            toggleSaved(product);
          }}
          aria-label={saved ? "Remove from watchlist" : "Add to watchlist"}
          data-testid="product-watchlist-btn"
          className={`h-8 w-8 rounded-lg backdrop-blur-md flex items-center justify-center border transition-all ${
            saved
              ? "bg-amber-500/90 border-amber-400 text-slate-950"
              : "bg-slate-950/70 border-slate-700 text-slate-400 hover:text-amber-400 hover:border-amber-500/50"
          }`}
        >
          <Star className={`h-4 w-4 ${saved ? "fill-current" : ""}`} />
        </button>
      </div>

      <Link to={`/products/${product.id}`} className="flex flex-col flex-1">
        <div className="relative h-40 overflow-hidden bg-slate-950">
          <img
            src={product.image_url}
            alt={product.name}
            loading="lazy"
            className="h-full w-full object-cover opacity-90 group-hover:opacity-100 group-hover:scale-105 transition-all duration-300"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-slate-950/10 to-transparent" />

          {/* Top-left stacked badges */}
          <div className="absolute top-3 left-3 flex flex-col gap-1.5 max-w-[75%]">
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-slate-950/80 backdrop-blur-sm border border-slate-800 text-[10px] font-semibold tracking-wider uppercase text-slate-300 w-fit">
              {product.category}
            </div>
            {product.is_local_hidden_gem && (
              <div
                data-testid="local-hidden-gem-badge"
                className="flex items-center gap-1 px-2 py-1 rounded-md bg-gradient-to-r from-violet-500 to-pink-500 text-slate-950 text-[10px] font-bold tracking-wider uppercase shadow-lg shadow-violet-500/40 w-fit"
              >
                <Sparkles className="h-3 w-3" />
                🌍 Local Hidden Gem
              </div>
            )}
            {product.is_untapped_local && (
              <div
                data-testid="untapped-local-badge"
                className="flex items-center gap-1 px-2 py-1 rounded-md bg-gradient-to-r from-amber-400 to-rose-500 text-slate-950 text-[10px] font-bold tracking-wider uppercase shadow-lg shadow-amber-500/40 w-fit"
              >
                <Compass className="h-3 w-3" />
                🚀 Untapped in {country.name}
              </div>
            )}
            {product.is_early_opportunity && !product.is_local_hidden_gem && !product.is_untapped_local && (
              <div
                data-testid="early-opportunity-badge"
                className="flex items-center gap-1 px-2 py-1 rounded-md bg-gradient-to-r from-emerald-500 to-indigo-500 text-slate-950 text-[10px] font-bold tracking-wider uppercase shadow-lg shadow-emerald-500/30 w-fit"
              >
                <Rocket className="h-3 w-3" />
                Early Opportunity
              </div>
            )}
          </div>

          <div className={`absolute bottom-3 left-3 flex items-center gap-1 px-2 py-1 rounded-md border text-[10px] font-bold tracking-wider uppercase ${demandColor(product.demand_level)}`}>
            <Flame className="h-3 w-3" />
            {product.demand_level.replace("_", " ")}
          </div>

          {/* Regulation dot */}
          {product.regulation_flag && (
            <div
              title={product.regulation_note}
              data-testid="regulation-dot"
              className="absolute bottom-3 right-3 flex items-center gap-1 px-2 py-1 rounded-md bg-slate-950/80 backdrop-blur-sm border border-slate-800"
            >
              <span className={`h-1.5 w-1.5 rounded-full ${regulationColor(product.regulation_flag)}`} />
              <span className="text-[9px] font-bold tracking-wider uppercase text-slate-400">
                {product.regulation_flag === "clear" ? "Clear" : product.regulation_flag === "certification" ? "Cert Req" : "Restricted"}
              </span>
            </div>
          )}
        </div>

        <div className="flex-1 flex flex-col p-4 gap-3">
          <div>
            <h3 className="font-bold text-sm sm:text-base text-slate-100 line-clamp-1 group-hover:text-emerald-400 transition-colors" data-testid="product-card-title">
              {product.name}
            </h3>
            <p className="mt-1 text-xs text-slate-400 line-clamp-1 leading-relaxed">{product.description}</p>
          </div>

          {/* Local vs Global scores */}
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-lg bg-slate-950/60 border border-slate-800 p-2" data-testid="local-score-card">
              <div className="flex items-center gap-1 text-[9px] font-semibold tracking-wider uppercase text-slate-500">
                <span>{country.flag}</span> Local
              </div>
              <div className="flex items-baseline gap-1 mt-0.5">
                <span
                  className="text-lg font-extrabold text-emerald-400 tabular-nums leading-tight"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                  data-testid="product-card-demand-score"
                >
                  {localScore}
                </span>
                <span className={`text-[10px] font-bold tabular-nums ${localScore - globalScore > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                  {localScore - globalScore > 0 ? "+" : ""}{localScore - globalScore}
                </span>
              </div>
            </div>
            <div className="rounded-lg bg-slate-950/60 border border-slate-800 p-2" data-testid="global-score-card">
              <div className="text-[9px] font-semibold tracking-wider uppercase text-slate-500">🌐 Global</div>
              <div className="text-lg font-extrabold text-slate-100 tabular-nums leading-tight" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {globalScore}
              </div>
            </div>
          </div>

          {/* Velocity + Opp */}
          <div className="grid grid-cols-2 gap-2">
            <div className={`rounded-lg border p-2 ${vs.bg}`} data-testid="velocity-indicator">
              <div className="text-[9px] font-semibold tracking-wider uppercase text-slate-500">Velocity</div>
              <div className={`text-sm font-extrabold tabular-nums leading-tight ${vs.color}`} style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {vs.arrow} {product.velocity_pct >= 0 ? "+" : ""}{product.velocity_pct}%
              </div>
            </div>
            <div className="rounded-lg bg-slate-950/60 border border-slate-800 p-2">
              <div className="text-[9px] font-semibold tracking-wider uppercase text-slate-500">Opportunity</div>
              <div className="text-sm font-extrabold text-indigo-400 tabular-nums leading-tight" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {product.opportunity_score}
              </div>
            </div>
          </div>

          {/* Saturation */}
          <SaturationPill score={product.saturation_score} label={product.saturation_label} />

          {/* Local platforms */}
          <div className="flex flex-wrap gap-1.5">
            {(product.local_platforms || product.trending_platforms || []).slice(0, 3).map((p) => (
              <PlatformBadge key={p} platform={p} />
            ))}
          </div>

          <div className="mt-auto pt-3 border-t border-slate-800 flex items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="text-sm font-bold text-slate-100 tabular-nums truncate" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {priceDisplay}
              </div>
              {product.local_price_range && (
                <div className="text-[10px] text-slate-500">≈ {product.usd_price_range}</div>
              )}
            </div>
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-400 group-hover:gap-2 transition-all shrink-0" data-testid="product-deep-dive-trigger">
              Deep dive
              <ArrowUpRight className="h-3.5 w-3.5" />
            </span>
          </div>
        </div>
      </Link>

      <button
        onClick={(e) => {
          e.preventDefault();
          setShowWhy((s) => !s);
        }}
        data-testid="why-trending-toggle"
        className="absolute bottom-2 right-2 h-6 w-6 rounded-full bg-slate-950/80 border border-slate-800 flex items-center justify-center text-slate-500 hover:text-emerald-400 hover:border-emerald-500/50 transition-all opacity-0 group-hover:opacity-100 z-10"
        aria-label="Why is this trending?"
      >
        <Info className="h-3 w-3" />
      </button>
      {showWhy && (
        <div className="absolute inset-x-4 bottom-14 z-30 p-3 rounded-xl bg-slate-950 border border-emerald-500/40 shadow-2xl shadow-emerald-500/20">
          <div className="text-[10px] font-bold tracking-wider uppercase text-emerald-400 mb-1">Why it's trending</div>
          <p className="text-xs text-slate-200 leading-relaxed">{product.why_trending}</p>
        </div>
      )}

      {selected && <div className="absolute inset-0 pointer-events-none ring-2 ring-emerald-500/60 rounded-2xl" />}
    </div>
  );
};

export default ProductCard;
