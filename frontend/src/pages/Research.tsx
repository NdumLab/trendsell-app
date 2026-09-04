import React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { refreshResearch } from "@/lib/api";
import { toast } from "sonner";
import { Sparkles, Search, Zap, Brain, RefreshCw } from "lucide-react";

const stages = [
  { icon: Search, label: "Scanning TikTok Shop signals", color: "text-pink-400" },
  { icon: Brain, label: "Analyzing Meta Ad Library patterns", color: "text-blue-400" },
  { icon: Zap, label: "Cross-referencing Amazon Best Sellers", color: "text-amber-400" },
  { icon: Sparkles, label: "Scoring driver ecosystem impact", color: "text-emerald-400" },
];

const Research: React.FC = () => {
  const [active, setActive] = React.useState(-1);
  const [running, setRunning] = React.useState(false);
  const [lastRun, setLastRun] = React.useState<{ count: number; source: string; generated_at: string } | null>(null);
  const queryClient = useQueryClient();

  const run = async () => {
    if (running) return;
    setRunning(true);
    setActive(0);
    const interval = setInterval(() => setActive((a) => (a < stages.length - 1 ? a + 1 : a)), 900);
    try {
      const res = await refreshResearch();
      setLastRun({ count: res.count, source: res.source, generated_at: res.generated_at });
      toast.success(`AI Research complete · ${res.count} products refreshed`);
      await queryClient.invalidateQueries();
    } catch {
      toast.error("Research failed");
    } finally {
      clearInterval(interval);
      setActive(stages.length);
      setRunning(false);
    }
  };

  return (
    <div className="space-y-8" data-testid="research-page">
      <div>
        <div className="text-xs font-semibold tracking-[0.2em] uppercase text-emerald-400 mb-2">AI Research Lab</div>
        <h1
          className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-50"
          style={{ fontFamily: "'Plus Jakarta Sans', sans-serif" }}
        >
          Signals from the whole internet.
        </h1>
        <p className="mt-2 text-sm text-slate-400 max-w-2xl">
          Trigger a fresh Gemini-powered research run to update trend scores, growth rates, and "why trending" narratives across every tracked product.
        </p>
      </div>

      <section className="rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950/40 border border-slate-800 p-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-slate-50">Run new research cycle</h2>
            <p className="text-xs text-slate-400 mt-1">Uses Gemini 3 Flash · streaming category & platform signals</p>
          </div>
          <button
            onClick={run}
            disabled={running}
            data-testid="research-run-button"
            className="h-12 px-6 rounded-xl bg-gradient-to-br from-emerald-500 to-indigo-500 text-slate-950 font-bold text-sm flex items-center gap-2 shadow-lg shadow-emerald-500/20 hover:-translate-y-0.5 hover:shadow-emerald-500/40 transition-all disabled:opacity-70 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`h-4 w-4 ${running ? "animate-spin" : ""}`} />
            {running ? "Researching…" : "Run Research"}
          </button>
        </div>

        <div className="mt-8 space-y-2">
          {stages.map(({ icon: Icon, label, color }, i) => {
            const isDone = i < active || (active === stages.length && i < stages.length);
            const isActive = i === active && running;
            return (
              <div
                key={label}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl border transition-all duration-300 ${
                  isActive
                    ? "bg-slate-950/80 border-emerald-500/40 shadow-lg shadow-emerald-500/10"
                    : isDone
                    ? "bg-slate-950/40 border-slate-800"
                    : "bg-slate-950/20 border-slate-800/50 opacity-50"
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? color + " animate-pulse" : isDone ? "text-emerald-400" : "text-slate-500"}`} />
                <span className={`text-sm font-medium ${isActive || isDone ? "text-slate-100" : "text-slate-500"}`}>{label}</span>
                {isActive && <span className="ml-auto text-[10px] text-emerald-400 font-semibold tracking-wider uppercase">Running</span>}
                {isDone && !isActive && <span className="ml-auto text-[10px] text-emerald-400 font-semibold tracking-wider uppercase">Done</span>}
              </div>
            );
          })}
        </div>
      </section>

      {lastRun && (
        <section className="rounded-2xl bg-slate-900/80 border border-slate-800 p-6">
          <h2 className="text-xs font-semibold tracking-[0.2em] uppercase text-slate-500 mb-4">Last research cycle</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500">Products Refreshed</div>
              <div className="mt-1 text-3xl font-extrabold text-emerald-400 tabular-nums" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{lastRun.count}</div>
            </div>
            <div>
              <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500">Model</div>
              <div className="mt-1 text-sm font-bold text-slate-100 break-all">{lastRun.source}</div>
            </div>
            <div>
              <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500">Generated</div>
              <div className="mt-1 text-sm font-bold text-slate-100">{new Date(lastRun.generated_at).toLocaleString()}</div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
};

export default Research;
