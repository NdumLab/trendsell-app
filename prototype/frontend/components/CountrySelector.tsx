import React, { useState, useMemo, useRef, useEffect } from "react";
import { ChevronDown, Globe, Search } from "lucide-react";
import { useLocation } from "@/context/LocationContext";
import { useQueryClient } from "@tanstack/react-query";

const CountrySelector: React.FC = () => {
  const { country, setCountry, countries } = useLocation();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const grouped = useMemo(() => {
    const filtered = countries.filter(
      (c) =>
        !q ||
        c.name.toLowerCase().includes(q.toLowerCase()) ||
        c.code.toLowerCase().includes(q.toLowerCase()) ||
        c.currency.toLowerCase().includes(q.toLowerCase())
    );
    const map = new Map<string, typeof countries>();
    for (const c of filtered) {
      if (!map.has(c.region)) map.set(c.region, []);
      map.get(c.region)!.push(c);
    }
    return Array.from(map.entries());
  }, [countries, q]);

  const select = (code: string) => {
    setCountry(code);
    setOpen(false);
    setQ("");
    // Invalidate all country-scoped queries
    queryClient.invalidateQueries();
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        data-testid="country-selector-button"
        className="h-10 pl-2 pr-3 rounded-xl bg-slate-900 border border-slate-800 text-slate-100 flex items-center gap-2 hover:border-emerald-500/40 transition-all"
      >
        <span className="text-lg leading-none">{country.flag}</span>
        <div className="hidden sm:flex flex-col items-start leading-tight">
          <span className="text-[10px] font-semibold tracking-wider uppercase text-slate-500">Market</span>
          <span className="text-xs font-bold text-slate-100">{country.name}</span>
        </div>
        <span className="sm:hidden text-xs font-bold text-slate-100">{country.code}</span>
        <ChevronDown className={`h-3.5 w-3.5 text-slate-500 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div
          data-testid="country-selector-dropdown"
          className="absolute right-0 mt-2 w-80 max-h-[70vh] rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl overflow-hidden z-50 flex flex-col"
        >
          <div className="p-3 border-b border-slate-800">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500" />
              <input
                type="text"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search country or currency…"
                autoFocus
                data-testid="country-search-input"
                className="w-full h-9 pl-9 pr-3 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500/40"
              />
            </div>
          </div>
          <div className="overflow-y-auto flex-1">
            {grouped.map(([region, list]) => (
              <div key={region}>
                <div className="sticky top-0 bg-slate-900 px-4 py-2 border-b border-slate-800 flex items-center gap-2">
                  <Globe className="h-3 w-3 text-slate-500" />
                  <span className="text-[10px] font-bold tracking-wider uppercase text-slate-500">{region}</span>
                </div>
                {list.map((c) => (
                  <button
                    key={c.code}
                    onClick={() => select(c.code)}
                    data-testid={`country-option-${c.code}`}
                    className={`w-full px-4 py-2.5 flex items-center gap-3 hover:bg-slate-800/60 transition-colors text-left ${
                      c.code === country.code ? "bg-emerald-500/10 border-l-2 border-emerald-400" : ""
                    }`}
                  >
                    <span className="text-lg leading-none">{c.flag}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-bold text-slate-100 truncate">{c.name}</div>
                      <div className="text-[10px] text-slate-500">
                        {c.currency} · {c.symbol} · PPP {c.ppp.toFixed(2)}
                      </div>
                    </div>
                    {c.code === country.code && (
                      <span className="text-[9px] font-bold text-emerald-400 uppercase tracking-widest">Active</span>
                    )}
                  </button>
                ))}
              </div>
            ))}
            {grouped.length === 0 && (
              <div className="p-8 text-center text-xs text-slate-500">No countries match "{q}"</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default CountrySelector;
