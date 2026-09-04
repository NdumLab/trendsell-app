import React from "react";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export const SeasonalCalendar: React.FC<{ monthly: number[] }> = ({ monthly }) => {
  if (!monthly || monthly.length === 0) return null;
  const max = Math.max(...monthly);
  const peakIdx = monthly.indexOf(max);
  const min = Math.min(...monthly);
  const offIdx = monthly.indexOf(min);

  const colorFor = (v: number) => {
    const pct = v / 100;
    if (pct >= 0.85) return "bg-emerald-500";
    if (pct >= 0.7) return "bg-indigo-500";
    if (pct >= 0.55) return "bg-violet-500";
    if (pct >= 0.4) return "bg-amber-500";
    return "bg-slate-700";
  };

  return (
    <div>
      <div className="grid grid-cols-6 sm:grid-cols-12 gap-2 mb-4">
        {monthly.map((val, i) => (
          <div key={i} data-testid="seasonal-month" className="flex flex-col items-center">
            <div className="w-full h-24 rounded-md bg-slate-950/60 border border-slate-800 flex items-end p-1 relative overflow-hidden">
              <div className={`w-full rounded-sm ${colorFor(val)} transition-all`} style={{ height: `${val}%` }} />
              {i === peakIdx && (
                <div className="absolute top-1 left-1/2 -translate-x-1/2 text-[8px] font-bold tracking-wider uppercase text-emerald-400">PEAK</div>
              )}
              {i === offIdx && (
                <div className="absolute top-1 left-1/2 -translate-x-1/2 text-[8px] font-bold tracking-wider uppercase text-slate-500">OFF</div>
              )}
            </div>
            <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500 mt-1.5">{MONTHS[i]}</div>
            <div
              className="text-[10px] font-bold text-slate-300 tabular-nums"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {val}
            </div>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-4 text-[10px] font-semibold tracking-wider uppercase text-slate-500 pt-3 border-t border-slate-800">
        <div className="flex items-center gap-1.5"><span className="h-2 w-4 rounded-sm bg-emerald-500" /> 85+ Peak</div>
        <div className="flex items-center gap-1.5"><span className="h-2 w-4 rounded-sm bg-indigo-500" /> 70-84 Strong</div>
        <div className="flex items-center gap-1.5"><span className="h-2 w-4 rounded-sm bg-violet-500" /> 55-69 Steady</div>
        <div className="flex items-center gap-1.5"><span className="h-2 w-4 rounded-sm bg-amber-500" /> 40-54 Soft</div>
        <div className="flex items-center gap-1.5"><span className="h-2 w-4 rounded-sm bg-slate-700" /> Off-season</div>
      </div>
    </div>
  );
};
