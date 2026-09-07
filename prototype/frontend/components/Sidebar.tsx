import React from "react";
import { NavLink } from "react-router-dom";
import { LayoutDashboard, TrendingUp, Zap, BarChart3, Sparkles, Factory, Star, Layers, Receipt } from "lucide-react";
import { cn } from "@/lib/utils";

const items = [
  { name: "Dashboard", icon: LayoutDashboard, path: "/" },
  { name: "Watchlist", icon: Star, path: "/watchlist" },
  { name: "Compare", icon: Layers, path: "/compare" },
  { name: "Sales Drivers", icon: Zap, path: "/drivers" },
  { name: "Suppliers", icon: Factory, path: "/suppliers" },
  { name: "Platform Fees", icon: Receipt, path: "/fees" },
  { name: "Analytics", icon: BarChart3, path: "/analytics" },
  { name: "AI Research", icon: Sparkles, path: "/research" },
];

const Sidebar: React.FC = () => {
  return (
    <aside
      className="hidden md:flex fixed left-0 top-0 h-screen w-64 flex-col border-r border-slate-800 bg-slate-950/95 backdrop-blur-xl z-40"
      data-testid="sidebar"
    >
      <div className="flex items-center gap-3 px-6 py-5 border-b border-slate-800">
        <div className="relative">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-emerald-400 to-indigo-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <TrendingUp className="h-5 w-5 text-slate-950" strokeWidth={2.5} />
          </div>
          <span className="absolute -top-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse ring-2 ring-slate-950" />
        </div>
        <div>
          <div className="text-lg font-extrabold tracking-tight text-slate-100" style={{ fontFamily: "'Plus Jakarta Sans', sans-serif" }} data-testid="app-header-brand">
            TrendSell
          </div>
          <div className="text-[10px] font-semibold tracking-wider uppercase text-emerald-400">
            Global · Signal
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-6 space-y-1 overflow-y-auto">
        {items.map(({ name, icon: Icon, path }) => (
          <NavLink
            key={path}
            to={path}
            end
            data-testid="sidebar-nav-link"
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-slate-800 text-slate-50 shadow-inner ring-1 ring-slate-700"
                  : "text-slate-400 hover:text-slate-100 hover:bg-slate-900"
              )
            }
          >
            <Icon className="h-4 w-4" />
            <span>{name}</span>
          </NavLink>
        ))}
      </nav>

      <div className="px-4 py-4 border-t border-slate-800">
        <div className="rounded-xl bg-gradient-to-br from-indigo-500/10 to-emerald-500/10 border border-slate-800 p-4">
          <div className="text-xs font-semibold tracking-wider uppercase text-emerald-400">Pro Tip</div>
          <p className="mt-1.5 text-xs text-slate-400 leading-relaxed">
            Switch the country selector to instantly see PPP-adjusted pricing and local platform rankings.
          </p>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
