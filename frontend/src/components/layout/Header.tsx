"use client";

import React from "react";
import Link from "next/link";
import {
  Bell,
  Search,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";

export default function Header() {
  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-slate-800 bg-slate-950/80 px-6 backdrop-blur-md">
      {/* Search Bar / Fast Navigation */}
      <div className="flex items-center gap-3 w-72 md:w-96">
        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search orders, tracking, SKUs, customers..."
            className="w-full rounded-lg border border-slate-800 bg-slate-900/60 pl-9 pr-10 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
          />
          <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400 font-mono">
            ⌘K
          </kbd>
        </div>
      </div>

      {/* Right Action Bar */}
      <div className="flex items-center gap-3">
        {/* Environment Badge */}
        <div className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-400">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
          Live Ops Runtime (INR)
        </div>

        {/* Quick Scenario Runner link */}
        <Link
          href="/scenarios"
          className="inline-flex items-center gap-1.5 rounded-lg border border-sky-500/30 bg-sky-500/10 px-3 py-1.5 text-xs font-medium text-sky-300 hover:bg-sky-500/20 transition-colors"
        >
          <Sparkles className="h-3.5 w-3.5" />
          <span>Demo Scenarios</span>
        </Link>

        {/* Exceptions Notification */}
        <Link
          href="/exceptions"
          className="relative flex h-8 w-8 items-center justify-center rounded-lg border border-slate-800 bg-slate-900/60 text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          title="Operational Exceptions"
        >
          <Bell className="h-4 w-4" />
          <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[10px] font-bold text-white">
            !
          </span>
        </Link>

        {/* User / Operator Profile */}
        <div className="flex items-center gap-2 pl-2 border-l border-slate-800">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-tr from-sky-600 to-indigo-600 text-xs font-bold text-white shadow">
            OP
          </div>
          <div className="hidden lg:block text-left">
            <div className="text-xs font-semibold text-slate-200">
              Operations Lead
            </div>
            <div className="text-[10px] text-slate-400">
              Supervisor (Full Auth)
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

