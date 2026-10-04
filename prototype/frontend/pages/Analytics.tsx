import React from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchTrends } from "@/lib/api";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from "recharts";
import { BarChart3, Radar as RadarIcon } from "lucide-react";

const Analytics: React.FC = () => {
  const { data: trends } = useQuery({ queryKey: ["trends"], queryFn: fetchTrends });

  return (
    <div className="space-y-8" data-testid="analytics-page">
      <div>
        <div className="text-xs font-semibold tracking-[0.2em] uppercase text-emerald-400 mb-2">
          Platform Analytics
        </div>
        <h1
          className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-50"
          style={{ fontFamily: "'Plus Jakarta Sans', sans-serif" }}
        >
          Where the sales flow.
        </h1>
        <p className="mt-2 text-sm text-slate-400">Category demand and platform velocity, side by side.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="rounded-2xl bg-slate-900/80 border border-slate-800 p-6" data-testid="trend-recharts-container">
          <div className="flex items-center gap-2 mb-6">
            <BarChart3 className="h-4 w-4 text-emerald-400" />
            <h2 className="text-lg font-bold text-slate-50">Category demand</h2>
          </div>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={trends?.categories || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgb(30 41 59)" />
                <XAxis dataKey="category" stroke="#64748b" fontSize={11} />
                <YAxis stroke="#64748b" fontSize={11} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, fontSize: 12 }}
                  labelStyle={{ color: "#f8fafc", fontWeight: 700 }}
                />
                <Bar dataKey="avg_score" fill="#10b981" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="rounded-2xl bg-slate-900/80 border border-slate-800 p-6">
          <div className="flex items-center gap-2 mb-6">
            <RadarIcon className="h-4 w-4 text-violet-400" />
            <h2 className="text-lg font-bold text-slate-50">Platform footprint</h2>
          </div>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={trends?.platforms || []}>
                <PolarGrid stroke="rgb(30 41 59)" />
                <PolarAngleAxis dataKey="platform" stroke="#94a3b8" fontSize={10} />
                <PolarRadiusAxis stroke="#334155" fontSize={9} />
                <Radar dataKey="count" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.35} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, fontSize: 12 }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      <section className="rounded-2xl bg-slate-900/80 border border-slate-800 p-6">
        <h2 className="text-lg font-bold text-slate-50 mb-6">Top platforms by product presence</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {(trends?.platforms || []).slice(0, 8).map((p) => (
            <div key={p.platform} className="rounded-xl bg-slate-950/50 border border-slate-800 p-4">
              <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500">Platform</div>
              <div className="text-sm font-bold text-slate-100 mt-0.5 truncate">{p.platform}</div>
              <div className="mt-3 text-3xl font-extrabold text-emerald-400 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {p.count}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">products active</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};

export default Analytics;
