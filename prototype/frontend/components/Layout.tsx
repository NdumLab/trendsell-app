import React from "react";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import { Toaster } from "sonner";

interface Props {
  children: React.ReactNode;
  search: string;
  onSearch: (v: string) => void;
}

const Layout: React.FC<Props> = ({ children, search, onSearch }) => {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100" data-testid="app-shell">
      <Sidebar />
      <div className="md:pl-64">
        <Header search={search} onSearch={onSearch} />
        <main className="px-4 sm:px-6 lg:px-8 py-8 max-w-[1600px] mx-auto">{children}</main>
      </div>
      <Toaster theme="dark" position="top-right" richColors closeButton />
    </div>
  );
};

export default Layout;
