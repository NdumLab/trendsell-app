import React from "react";
import { cn } from "@/lib/utils";

const platformColors: Record<string, string> = {
  "TikTok Shop": "bg-pink-500/10 text-pink-400 border-pink-500/30",
  "Amazon": "bg-amber-500/10 text-amber-400 border-amber-500/30",
  "Meta Ads": "bg-blue-500/10 text-blue-400 border-blue-500/30",
  "Instagram Shop": "bg-fuchsia-500/10 text-fuchsia-400 border-fuchsia-500/30",
  "Sephora": "bg-rose-500/10 text-rose-400 border-rose-500/30",
  "Target": "bg-red-500/10 text-red-400 border-red-500/30",
  "Costco": "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
  "Best Buy": "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  "Chewy": "bg-orange-500/10 text-orange-400 border-orange-500/30",
  "Nordstrom": "bg-purple-500/10 text-purple-400 border-purple-500/30",
  "Apple Store": "bg-slate-500/10 text-slate-300 border-slate-500/30",
  "Anker DTC": "bg-teal-500/10 text-teal-400 border-teal-500/30",
  "Halara DTC": "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  "Ridge DTC": "bg-indigo-500/10 text-indigo-400 border-indigo-500/30",
  "Meta Shops": "bg-blue-500/10 text-blue-400 border-blue-500/30",
};

export const PlatformBadge: React.FC<{ platform: string; className?: string }> = ({ platform, className }) => {
  const color = platformColors[platform] || "bg-slate-500/10 text-slate-300 border-slate-500/30";
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-md text-[11px] font-medium border tracking-wide transition-colors",
        color,
        className
      )}
      data-testid="platform-badge"
    >
      {platform}
    </span>
  );
};
