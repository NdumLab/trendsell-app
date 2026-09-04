import React from "react";
import { cn } from "@/lib/utils";

interface Props {
  categories: string[];
  active: string;
  onChange: (c: string) => void;
}

const CategoryChips: React.FC<Props> = ({ categories, active, onChange }) => {
  const all = ["All", ...categories];
  return (
    <div className="flex flex-wrap gap-2" data-testid="category-filter-list">
      {all.map((cat) => {
        const isActive = cat === active;
        return (
          <button
            key={cat}
            onClick={() => onChange(cat)}
            data-testid="category-filter-chip"
            className={cn(
              "px-4 py-2 rounded-full text-xs font-semibold tracking-wide transition-all duration-200 border",
              isActive
                ? "bg-slate-50 text-slate-950 border-slate-50 shadow-lg shadow-emerald-500/10"
                : "bg-slate-900 text-slate-300 border-slate-800 hover:border-slate-700 hover:text-slate-100"
            )}
          >
            {cat}
          </button>
        );
      })}
    </div>
  );
};

export default CategoryChips;
