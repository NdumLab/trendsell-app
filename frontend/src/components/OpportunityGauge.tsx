import React from "react";
import type { OpportunityBreakdown } from "@/types";

interface Props {
  score: number;
  breakdown: OpportunityBreakdown;
}

const factorLabels: Record<keyof OpportunityBreakdown, { label: string; color: string }> = {
  trend: { label: "Trend score", color: "bg-emerald-400" },
  velocity: { label: "Velocity", color: "bg-indigo-400" },
  saturation_inverse: { label: "White space", color: "bg-violet-400" },
  margin_potential: { label: "Margin", color: "bg-amber-400" },
  first_mover: { label: "First-mover", color: "bg-pink-400" },
};

export const OpportunityGauge: React.FC<Props> = ({ score, breakdown }) => {
  const radius = 62;
  const circumference = 2 * Math.PI * radius;
  const dash = (score / 100) * circumference;

  const rating =
    score >= 85 ? "EXCEPTIONAL" : score >= 70 ? "STRONG" : score >= 55 ? "MODERATE" : "WATCHLIST";
  const ratingColor =
    score >= 85 ? "text-emerald-400" : score >= 70 ? "text-indigo-400" : score >= 55 ? "text-amber-400" : "text-rose-400";

  return (
    <div className="flex flex-col items-center" data-testid="market-opportunity-gauge">
      <div className="relative">
        <svg width="180" height="180" viewBox="0 0 180 180">
          <defs>
            <linearGradient id="opportunityGradient" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#f43f5e" />
              <stop offset="30%" stopColor="#f59e0b" />
              <stop offset="70%" stopColor="#6366f1" />
              <stop offset="100%" stopColor="#10b981" />
            </linearGradient>
          </defs>
          <circle cx="90" cy="90" r={radius} stroke="rgb(30 41 59)" strokeWidth="12" fill="none" />
          <circle
            cx="90"
            cy="90"
            r={radius}
            stroke="url(#opportunityGradient)"
            strokeWidth="12"
            fill="none"
            strokeLinecap="round"
            strokeDasharray={`${dash} ${circumference}`}
            transform="rotate(-90 90 90)"
            style={{ transition: "stroke-dasharray 800ms ease-out" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <div
            className="text-4xl font-extrabold text-slate-50 tabular-nums"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {score}
          </div>
          <div className="text-[10px] font-semibold tracking-widest text-slate-500 uppercase">Score</div>
        </div>
      </div>
      <div className={`mt-2 text-xs font-bold tracking-widest uppercase ${ratingColor}`}>{rating}</div>

      <div className="mt-6 w-full space-y-2">
        {(Object.entries(breakdown) as [keyof OpportunityBreakdown, number][]).map(([k, v]) => {
          const meta = factorLabels[k];
          if (!meta) return null;
          return (
            <div key={k}>
              <div className="flex items-center justify-between text-[10px] mb-1">
                <span className="font-semibold tracking-wider uppercase text-slate-500">{meta.label}</span>
                <span className="tabular-nums font-bold text-slate-300" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{Math.round(v)}</span>
              </div>
              <div className="h-1 w-full bg-slate-800 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${meta.color}`} style={{ width: `${v}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
