import React, { createContext, useContext, useEffect, useState } from "react";
import type { Product } from "@/types";

// -------- Watchlist --------
interface WatchlistEntry {
  id: string;
  savedAt: string;
  lastKnownScore: number;
}

interface WatchlistCtx {
  entries: WatchlistEntry[];
  isSaved: (id: string) => boolean;
  toggle: (product: Product) => void;
  getDelta: (product: Product) => number;
}

const WatchlistContext = createContext<WatchlistCtx>({
  entries: [],
  isSaved: () => false,
  toggle: () => {},
  getDelta: () => 0,
});

const WATCHLIST_KEY = "trendsell-watchlist-v1";

export const WatchlistProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [entries, setEntries] = useState<WatchlistEntry[]>(() => {
    if (typeof window === "undefined") return [];
    try {
      return JSON.parse(localStorage.getItem(WATCHLIST_KEY) || "[]");
    } catch {
      return [];
    }
  });

  useEffect(() => {
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(entries));
  }, [entries]);

  const isSaved = (id: string) => entries.some((e) => e.id === id);

  const toggle = (product: Product) => {
    setEntries((prev) => {
      if (prev.some((e) => e.id === product.id)) {
        return prev.filter((e) => e.id !== product.id);
      }
      return [
        ...prev,
        { id: product.id, savedAt: new Date().toISOString(), lastKnownScore: product.trend_score },
      ];
    });
  };

  const getDelta = (product: Product) => {
    const entry = entries.find((e) => e.id === product.id);
    if (!entry) return 0;
    return product.trend_score - entry.lastKnownScore;
  };

  return (
    <WatchlistContext.Provider value={{ entries, isSaved, toggle, getDelta }}>
      {children}
    </WatchlistContext.Provider>
  );
};

export const useWatchlist = () => useContext(WatchlistContext);

// -------- Compare --------
interface CompareCtx {
  ids: string[];
  toggle: (id: string) => void;
  clear: () => void;
  isSelected: (id: string) => boolean;
}

const CompareContext = createContext<CompareCtx>({
  ids: [],
  toggle: () => {},
  clear: () => {},
  isSelected: () => false,
});

export const CompareProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [ids, setIds] = useState<string[]>(() => {
    if (typeof window === "undefined") return [];
    try {
      return JSON.parse(localStorage.getItem("trendsell-compare-v1") || "[]");
    } catch {
      return [];
    }
  });

  useEffect(() => {
    localStorage.setItem("trendsell-compare-v1", JSON.stringify(ids));
  }, [ids]);

  const toggle = (id: string) => {
    setIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 2) return [prev[1], id]; // FIFO — keep most recent 2
      return [...prev, id];
    });
  };

  const clear = () => setIds([]);
  const isSelected = (id: string) => ids.includes(id);

  return (
    <CompareContext.Provider value={{ ids, toggle, clear, isSelected }}>
      {children}
    </CompareContext.Provider>
  );
};

export const useCompare = () => useContext(CompareContext);
