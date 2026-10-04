import React from "react";
import { LucideIcon } from "lucide-react";

interface Props {
  label: string;
  value: string | number;
  sub?: string;
  icon: LucideIcon;
  accent?: "emerald" | "indigo" | "violet" | "amber";
}

const accents = {
  emerald: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  indigo: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
  violet: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  amber: "text-amber-400 bg-amber-500/10 border-amber-500/20",
};

const KPICard: React.FC<Props> = ({ label, value, sub, icon: Icon, accent = "emerald" }) => {
  return (
    <div
      className="rounded-2xl bg-slate-900/80 border border-slate-800 p-5 hover:border-slate-700 transition-all duration-200"
      data-testid="kpi-card"
    >
      <div className="flex items-start justify-between mb-4">
        <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500">{label}</div>
        <div className={`h-9 w-9 rounded-lg border flex items-center justify-center ${accents[accent]}`}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <div
        className="text-3xl font-extrabold text-slate-50 tabular-nums"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        {value}
      </div>
      {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
    </div>
  );
};

export default KPICard;
