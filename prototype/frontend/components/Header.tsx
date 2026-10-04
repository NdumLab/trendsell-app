import React, { useState } from "react";
import { Search, RefreshCw, Sun, Moon, Bell, Star, Layers } from "lucide-react";
import { useTheme } from "@/context/ThemeContext";
import { useWatchlist, useCompare } from "@/context/AppState";
import { refreshResearch } from "@/lib/api";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import CountrySelector from "@/components/CountrySelector";

interface HeaderProps {
  search: string;
  onSearch: (v: string) => void;
}

const Header: React.FC<HeaderProps> = ({ search, onSearch }) => {
  const { theme, toggle } = useTheme();
  const { entries: watchlistEntries } = useWatchlist();
  const { ids: compareIds } = useCompare();
  const [refreshing, setRefreshing] = useState(false);
  const queryClient = useQueryClient();

  const handleRefresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    const stages = [
      "Scanning TikTok Shop signals…",
      "Analyzing Meta Ad Library…",
      "Cross-referencing Amazon Best Sellers…",
      "Scoring driver ecosystem impact…",
    ];
    const toastId = toast.loading(stages[0]);
    stages.slice(1).forEach((s, i) => {
      setTimeout(() => toast.loading(s, { id: toastId }), (i + 1) * 700);
    });
    try {
      const res = await refreshResearch();
      toast.success(`Refreshed ${res.count} products · ${res.source}`, { id: toastId });
      await queryClient.invalidateQueries();
    } catch (e) {
      toast.error("Refresh failed, please retry", { id: toastId });
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <header
      className="sticky top-0 z-30 h-16 bg-slate-950/90 backdrop-blur-xl border-b border-slate-800 flex items-center px-4 sm:px-6 gap-3"
      data-testid="app-header"
    >
      <div className="relative flex-1 max-w-md">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
        <input
          type="text"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="Search products, categories, drivers…"
          className="w-full h-10 pl-10 pr-4 rounded-xl bg-slate-900 border border-slate-800 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 focus:border-slate-700 transition-all"
          data-testid="global-search-input"
        />
      </div>

      <CountrySelector />

      <div className="flex items-center gap-1.5 ml-auto">
        {compareIds.length > 0 && (
          <Link
            to="/compare"
            data-testid="compare-header-link"
            className="hidden md:flex h-10 px-3 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 text-xs font-semibold items-center gap-1.5 hover:bg-indigo-500/20 transition-all"
          >
            <Layers className="h-3.5 w-3.5" />
            Compare <span className="tabular-nums">{compareIds.length}/2</span>
          </Link>
        )}
        {watchlistEntries.length > 0 && (
          <Link
            to="/watchlist"
            data-testid="watchlist-header-link"
            className="hidden md:flex h-10 px-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-semibold items-center gap-1.5 hover:bg-amber-500/20 transition-all"
          >
            <Star className="h-3.5 w-3.5 fill-current" />
            <span className="tabular-nums">{watchlistEntries.length}</span>
          </Link>
        )}
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          data-testid="refresh-data-button"
          className="h-10 px-3 sm:px-4 rounded-xl bg-gradient-to-br from-emerald-500 to-indigo-500 text-slate-950 font-semibold text-xs sm:text-sm flex items-center gap-2 shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/40 hover:-translate-y-0.5 transition-all disabled:opacity-70 disabled:cursor-not-allowed"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          <span className="hidden sm:inline">{refreshing ? "Researching…" : "Refresh"}</span>
        </button>
        <button
          onClick={toggle}
          data-testid="theme-toggle-button"
          className="h-10 w-10 rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-slate-50 hover:border-slate-700 transition-all flex items-center justify-center"
          aria-label="Toggle theme"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
        <button
          data-testid="notifications-button"
          className="hidden sm:flex relative h-10 w-10 rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-slate-50 hover:border-slate-700 transition-all items-center justify-center"
          aria-label="Notifications"
        >
          <Bell className="h-4 w-4" />
          <span className="absolute top-2 right-2 h-2 w-2 rounded-full bg-rose-500 ring-2 ring-slate-950" />
        </button>
      </div>
    </header>
  );
};

export default Header;
