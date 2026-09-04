import React, { createContext, useContext, useState } from "react";
import { cn } from "@/lib/utils";

interface TabsCtx {
  value: string;
  setValue: (v: string) => void;
}
const Ctx = createContext<TabsCtx>({ value: "", setValue: () => {} });

interface TabsProps {
  defaultValue: string;
  value?: string;
  onValueChange?: (v: string) => void;
  className?: string;
  children: React.ReactNode;
}

export const Tabs: React.FC<TabsProps> = ({ defaultValue, value, onValueChange, className, children }) => {
  const [internal, setInternal] = useState<string>(defaultValue);
  const current = value ?? internal;
  const setter = (v: string) => {
    if (value === undefined) setInternal(v);
    onValueChange?.(v);
  };
  return (
    <Ctx.Provider value={{ value: current, setValue: setter }}>
      <div className={className}>{children}</div>
    </Ctx.Provider>
  );
};

export const TabsList: React.FC<{ className?: string; children: React.ReactNode }> = ({ className, children }) => (
  <div className={cn("inline-flex items-center rounded-xl p-1", className)}>{children}</div>
);

interface TabsTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string;
  className?: string;
  children: React.ReactNode;
}

export const TabsTrigger: React.FC<TabsTriggerProps> = ({ value, className, children, ...rest }) => {
  const ctx = useContext(Ctx);
  const active = ctx.value === value;
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={() => ctx.setValue(value)}
      className={cn(
        "px-3 sm:px-4 py-2 rounded-lg transition-all",
        active ? "bg-slate-800 text-slate-50 shadow-inner" : "text-slate-400 hover:text-slate-100",
        className
      )}
      {...rest}
    >
      {children}
    </button>
  );
};

export const TabsContent: React.FC<{ value: string; className?: string; children: React.ReactNode }> = ({ value, className, children }) => {
  const ctx = useContext(Ctx);
  if (ctx.value !== value) return null;
  return <div className={className}>{children}</div>;
};
