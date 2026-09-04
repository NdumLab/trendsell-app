import React from "react";
import { Printer, AlertTriangle, ListChecks, TrendingUp, Users, Rocket } from "lucide-react";
import type { MarketBrief } from "@/types";

interface Props {
  brief: MarketBrief;
  productName: string;
}

export const MarketBriefView: React.FC<Props> = ({ brief, productName }) => {
  return (
    <div className="space-y-5" data-testid="market-brief-content">
      <div className="flex items-center justify-between gap-3 pb-4 border-b border-slate-800">
        <div>
          <div className="text-[10px] font-semibold tracking-wider uppercase text-emerald-400">Market Brief · {brief.model}</div>
          <div className="text-xs text-slate-500 mt-0.5">Generated {new Date(brief.generated_at).toLocaleString()}</div>
        </div>
        <button
          onClick={() => window.print()}
          className="h-8 px-3 rounded-lg bg-slate-800 border border-slate-700 text-slate-100 text-xs font-semibold flex items-center gap-1.5 hover:border-slate-600 transition-all"
        >
          <Printer className="h-3 w-3" /> Print
        </button>
      </div>

      <div>
        <div className="text-[10px] font-bold tracking-widest uppercase text-slate-500 mb-2">Executive Summary</div>
        <p className="text-sm text-slate-100 leading-relaxed">{brief.executive_summary}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-xl bg-slate-950/40 border border-slate-800 p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="h-3.5 w-3.5 text-emerald-400" />
            <div className="text-[10px] font-bold tracking-widest uppercase text-emerald-400">Market Opportunity</div>
          </div>
          <p className="text-xs text-slate-200 leading-relaxed">{brief.market_opportunity}</p>
        </div>
        <div className="rounded-xl bg-slate-950/40 border border-slate-800 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Users className="h-3.5 w-3.5 text-amber-400" />
            <div className="text-[10px] font-bold tracking-widest uppercase text-amber-400">Competition</div>
          </div>
          <p className="text-xs text-slate-200 leading-relaxed">{brief.competition_level}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-xl bg-slate-950/40 border border-slate-800 p-4">
          <div className="flex items-center gap-2 mb-3">
            <Rocket className="h-3.5 w-3.5 text-indigo-400" />
            <div className="text-[10px] font-bold tracking-widest uppercase text-indigo-400">Recommended Platforms</div>
          </div>
          <div className="space-y-2">
            {brief.recommended_platforms.map((p, i) => (
              <div key={p} className="flex items-center gap-2 text-xs text-slate-100">
                <div className="h-5 w-5 rounded-md bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-[10px] font-bold text-indigo-400">{i + 1}</div>
                {p}
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-xl bg-gradient-to-br from-emerald-500/10 to-indigo-500/10 border border-emerald-500/30 p-4">
          <div className="text-[10px] font-bold tracking-widest uppercase text-emerald-400 mb-2">Estimated ROI</div>
          <div className="text-2xl font-extrabold text-slate-50" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{brief.estimated_roi}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-xl bg-slate-950/40 border border-slate-800 p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="h-3.5 w-3.5 text-rose-400" />
            <div className="text-[10px] font-bold tracking-widest uppercase text-rose-400">Key Risks</div>
          </div>
          <ul className="space-y-2">
            {brief.key_risks.map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-slate-200">
                <span className="h-1.5 w-1.5 rounded-full bg-rose-400 mt-1.5 shrink-0" />
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl bg-slate-950/40 border border-slate-800 p-4">
          <div className="flex items-center gap-2 mb-3">
            <ListChecks className="h-3.5 w-3.5 text-emerald-400" />
            <div className="text-[10px] font-bold tracking-widest uppercase text-emerald-400">Action Items</div>
          </div>
          <ol className="space-y-2">
            {brief.action_items.map((a, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-slate-200">
                <span className="h-4 w-4 rounded-md bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-[9px] font-bold text-emerald-400 shrink-0 mt-0.5">{i + 1}</span>
                <span>{a}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
};
