import React from "react";

const config = {
  Low: { color: "bg-emerald-500", text: "text-emerald-400", label: "Low competition" },
  Medium: { color: "bg-amber-500", text: "text-amber-400", label: "Medium competition" },
  High: { color: "bg-orange-500", text: "text-orange-400", label: "High competition" },
  Oversaturated: { color: "bg-rose-500", text: "text-rose-400", label: "Oversaturated" },
};

export const SaturationPill: React.FC<{ score: number; label: string; size?: "sm" | "md" }> = ({ score, label, size = "sm" }) => {
  const cfg = config[label as keyof typeof config] || config.Medium;
  return (
    <div className="flex items-center gap-2" data-testid="saturation-pill">
      <div className={`flex-1 ${size === "md" ? "h-2" : "h-1.5"} rounded-full bg-slate-800 overflow-hidden`}>
        <div
          className={`h-full rounded-full ${cfg.color} transition-all duration-500`}
          style={{ width: `${score}%` }}
        />
      </div>
      <div className={`text-[10px] font-bold tracking-wider uppercase ${cfg.text} min-w-[80px] text-right`}>
        {label}
      </div>
    </div>
  );
};
