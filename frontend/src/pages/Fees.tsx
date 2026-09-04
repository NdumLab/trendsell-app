import React from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchPlatformFees } from "@/lib/api";
import { Receipt } from "lucide-react";

const Fees: React.FC = () => {
  const { data: fees = [] } = useQuery({ queryKey: ["platform-fees"], queryFn: fetchPlatformFees });

  return (
    <div className="space-y-8" data-testid="fees-page">
      <div>
        <div className="text-xs font-semibold tracking-[0.2em] uppercase text-emerald-400 mb-2 flex items-center gap-2">
          <Receipt className="h-3.5 w-3.5" /> Platform Fee Breakdown
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-50" style={{ fontFamily: "'Plus Jakarta Sans', sans-serif" }}>
          Know your true margin.
        </h1>
        <p className="mt-2 text-sm text-slate-400 max-w-2xl">
          Referral fees, fulfillment costs, subscriptions and payment processing across the major marketplaces — side by side.
        </p>
      </div>

      <section className="rounded-2xl bg-slate-900/80 border border-slate-800 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-950/60">
              <th className="text-left px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500">Platform</th>
              <th className="text-right px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500">Referral</th>
              <th className="text-left px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500">Fulfillment</th>
              <th className="text-left px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500 hidden md:table-cell">Subscription</th>
              <th className="text-right px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500">Payment</th>
              <th className="text-left px-6 py-3 text-[10px] font-semibold tracking-wider uppercase text-slate-500 hidden lg:table-cell">Notes</th>
            </tr>
          </thead>
          <tbody>
            {fees.map((f) => (
              <tr key={f.platform} className="border-b border-slate-800 last:border-b-0 hover:bg-slate-950/30" data-testid="fee-row">
                <td className="px-6 py-4 text-sm font-bold text-slate-100">{f.platform}</td>
                <td className="px-6 py-4 text-right text-sm font-bold text-emerald-400 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                  {f.referral_fee_pct.toFixed(1)}%
                </td>
                <td className="px-6 py-4 text-xs text-slate-300">{f.fulfillment_fee}</td>
                <td className="px-6 py-4 text-xs text-slate-300 hidden md:table-cell">{f.monthly_subscription}</td>
                <td className="px-6 py-4 text-right text-xs text-slate-300 tabular-nums">{f.payment_processing_pct ? `${f.payment_processing_pct.toFixed(1)}%` : "—"}</td>
                <td className="px-6 py-4 text-xs text-slate-400 hidden lg:table-cell max-w-md">{f.notes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
};

export default Fees;
