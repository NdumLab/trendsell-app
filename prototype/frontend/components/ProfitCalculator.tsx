import React, { useMemo, useState } from "react";
import type { Product } from "@/types";
import { DollarSign, TrendingUp, Target } from "lucide-react";

const parseDollarLow = (s: string): number => {
  const m = s.match(/\$?([\d,.]+)/);
  return m ? parseFloat(m[1].replace(/,/g, "")) : 0;
};

const parseDollarHigh = (s: string): number => {
  const parts = s.match(/\$?([\d,.]+).*?\$?([\d,.]+)/);
  if (parts) return parseFloat(parts[2].replace(/,/g, ""));
  return parseDollarLow(s);
};

export const ProfitCalculator: React.FC<{ product: Product }> = ({ product }) => {
  const unitCost = useMemo(() => {
    const supplier = product.suppliers?.[0];
    if (!supplier) return 8;
    return parseDollarLow(supplier.unit_price);
  }, [product]);

  const sellPrice = useMemo(() => {
    return parseDollarHigh(product.price_range) || unitCost * 3;
  }, [product, unitCost]);

  const [budget, setBudget] = useState<number>(5000);
  const [units, setUnits] = useState<number>(200);
  const [adSpendPct, setAdSpendPct] = useState<number>(20);
  const [platformFeePct, setPlatformFeePct] = useState<number>(15);

  const gross = units * sellPrice;
  const cogs = units * unitCost;
  const platformFees = gross * (platformFeePct / 100);
  const adSpend = gross * (adSpendPct / 100);
  const netProfit = gross - cogs - platformFees - adSpend;
  const totalInvestment = cogs + adSpend + Math.max(0, budget - cogs - adSpend);
  const roi = totalInvestment > 0 ? (netProfit / (cogs + adSpend)) * 100 : 0;
  const breakEvenUnits = Math.ceil((cogs + adSpend) / Math.max(sellPrice - platformFees / Math.max(units, 1), 0.01));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Inputs */}
      <div className="space-y-4">
        <div>
          <label className="flex items-center justify-between text-[10px] font-semibold tracking-wider uppercase text-slate-500 mb-2">
            <span>Total Budget</span>
            <span className="tabular-nums text-slate-100 font-bold" style={{ fontFamily: "'JetBrains Mono', monospace" }}>${budget.toLocaleString()}</span>
          </label>
          <input
            type="range"
            min={500}
            max={50000}
            step={500}
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
            data-testid="calc-budget"
            className="w-full h-2 rounded-full bg-slate-800 appearance-none cursor-pointer accent-emerald-500"
          />
        </div>

        <div>
          <label className="flex items-center justify-between text-[10px] font-semibold tracking-wider uppercase text-slate-500 mb-2">
            <span>Expected Units Sold</span>
            <span className="tabular-nums text-slate-100 font-bold" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{units.toLocaleString()}</span>
          </label>
          <input
            type="range"
            min={50}
            max={5000}
            step={25}
            value={units}
            onChange={(e) => setUnits(Number(e.target.value))}
            data-testid="calc-units"
            className="w-full h-2 rounded-full bg-slate-800 appearance-none cursor-pointer accent-emerald-500"
          />
        </div>

        <div>
          <label className="flex items-center justify-between text-[10px] font-semibold tracking-wider uppercase text-slate-500 mb-2">
            <span>Ad Spend %</span>
            <span className="tabular-nums text-slate-100 font-bold" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{adSpendPct}%</span>
          </label>
          <input
            type="range"
            min={0}
            max={50}
            step={1}
            value={adSpendPct}
            onChange={(e) => setAdSpendPct(Number(e.target.value))}
            data-testid="calc-adspend"
            className="w-full h-2 rounded-full bg-slate-800 appearance-none cursor-pointer accent-emerald-500"
          />
        </div>

        <div>
          <label className="flex items-center justify-between text-[10px] font-semibold tracking-wider uppercase text-slate-500 mb-2">
            <span>Platform Fees %</span>
            <span className="tabular-nums text-slate-100 font-bold" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{platformFeePct}%</span>
          </label>
          <input
            type="range"
            min={0}
            max={30}
            step={0.5}
            value={platformFeePct}
            onChange={(e) => setPlatformFeePct(Number(e.target.value))}
            data-testid="calc-fees"
            className="w-full h-2 rounded-full bg-slate-800 appearance-none cursor-pointer accent-emerald-500"
          />
        </div>

        <div className="grid grid-cols-2 gap-3 pt-2">
          <div className="rounded-lg bg-slate-950/60 border border-slate-800 p-3">
            <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500">Unit Cost (supplier)</div>
            <div className="text-sm font-bold text-slate-100 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>${unitCost.toFixed(2)}</div>
          </div>
          <div className="rounded-lg bg-slate-950/60 border border-slate-800 p-3">
            <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500">Sell Price</div>
            <div className="text-sm font-bold text-slate-100 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>${sellPrice.toFixed(2)}</div>
          </div>
        </div>
      </div>

      {/* Outputs */}
      <div className="space-y-3">
        <div className="rounded-xl bg-gradient-to-br from-emerald-500/10 to-indigo-500/10 border border-emerald-500/30 p-5">
          <div className="text-[10px] font-semibold tracking-widest uppercase text-emerald-400 mb-1">Estimated Net Profit</div>
          <div className={`text-4xl font-extrabold tabular-nums ${netProfit >= 0 ? "text-emerald-400" : "text-rose-400"}`} style={{ fontFamily: "'JetBrains Mono', monospace" }} data-testid="calc-profit">
            ${netProfit.toFixed(0).toLocaleString()}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl bg-slate-950/60 border border-slate-800 p-4" data-testid="calc-roi">
            <div className="flex items-center gap-2 mb-1">
              <TrendingUp className="h-3 w-3 text-emerald-400" />
              <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500">ROI</div>
            </div>
            <div className={`text-2xl font-extrabold tabular-nums ${roi >= 0 ? "text-emerald-400" : "text-rose-400"}`} style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              {roi.toFixed(0)}%
            </div>
          </div>
          <div className="rounded-xl bg-slate-950/60 border border-slate-800 p-4" data-testid="calc-breakeven">
            <div className="flex items-center gap-2 mb-1">
              <Target className="h-3 w-3 text-indigo-400" />
              <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500">Break-even</div>
            </div>
            <div className="text-2xl font-extrabold text-slate-100 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
              {breakEvenUnits} <span className="text-xs text-slate-500 font-semibold">units</span>
            </div>
          </div>
        </div>

        <div className="rounded-xl bg-slate-950/60 border border-slate-800 p-4 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">Gross revenue</span>
            <span className="tabular-nums font-semibold text-slate-100" style={{ fontFamily: "'JetBrains Mono', monospace" }}>${gross.toLocaleString()}</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">– COGS ({units} × ${unitCost.toFixed(2)})</span>
            <span className="tabular-nums font-semibold text-rose-400" style={{ fontFamily: "'JetBrains Mono', monospace" }}>${cogs.toLocaleString()}</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">– Platform fees ({platformFeePct}%)</span>
            <span className="tabular-nums font-semibold text-rose-400" style={{ fontFamily: "'JetBrains Mono', monospace" }}>${platformFees.toLocaleString()}</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">– Ad spend ({adSpendPct}%)</span>
            <span className="tabular-nums font-semibold text-rose-400" style={{ fontFamily: "'JetBrains Mono', monospace" }}>${adSpend.toLocaleString()}</span>
          </div>
          <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs">
            <span className="text-slate-300 font-semibold">Net</span>
            <span className={`tabular-nums font-extrabold ${netProfit >= 0 ? "text-emerald-400" : "text-rose-400"}`} style={{ fontFamily: "'JetBrains Mono', monospace" }}>${netProfit.toLocaleString()}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
