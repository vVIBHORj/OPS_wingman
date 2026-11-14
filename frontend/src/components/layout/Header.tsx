"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bell,
  Search,
  Sparkles,
  Menu,
} from "lucide-react";

interface HeaderProps {
  onOpenMobile: () => void;
}

const PAGE_NAMES: Record<string, string> = {
  "/": "Command Center",
  "/agent": "AI Operations Agent",
  "/orders": "Orders Ledger",
  "/customers": "Customer Directory",
  "/products": "Product Catalog",
  "/payments": "Payment Ledger",
  "/shipments": "Logistics & Fulfillment",
  "/tickets": "Support Ticket Queue",
  "/approvals": "Gated Approval Queue",
  "/exceptions": "Operational Exceptions",
  "/audit": "Audit & Compliance Trail",
  "/scenarios": "Scenario Runner",
};

export default function Header({ onOpenMobile }: HeaderProps) {
  const pathname = usePathname();

  const getPageTitle = () => {
    if (PAGE_NAMES[pathname]) return PAGE_NAMES[pathname];
    if (pathname.startsWith("/orders/")) return "Order Details";
    if (pathname.startsWith("/customers/")) return "Customer Profile";
    return "Operations";
  };

  return (
    <header className="sticky top-0 z-30 flex h-14 w-full items-center justify-between border-b border-white/[0.07] bg-[#08090d]/80 px-4 sm:px-6 backdrop-blur-md">
      {/* Left: Mobile hamburger & Contextual Breadcrumb */}
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenMobile}
          className="flex md:hidden h-8 w-8 items-center justify-center rounded-md text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors"
          aria-label="Open navigation menu"
        >
          <Menu className="h-4 w-4" />
        </button>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-zinc-400 hidden sm:inline">Operations</span>
          <span className="text-zinc-600 hidden sm:inline">/</span>
          <span className="font-medium text-zinc-200">{getPageTitle()}</span>
        </div>
      </div>

      {/* Middle: Minimalist Command Search Bar */}
      <div className="hidden lg:flex items-center max-w-sm w-full mx-4">
        <div className="relative w-full">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-400" />
          <input
            type="text"
            placeholder="Search orders, SKUs, customers, shipments..."
            className="w-full rounded-md border border-white/[0.07] bg-white/[0.03] pl-8 pr-12 py-1.5 text-xs text-zinc-200 placeholder-zinc-400 transition-colors focus:border-zinc-500 focus:bg-white/[0.05] focus:outline-none"
          />
          <kbd className="absolute right-2 top-1/2 -translate-y-1/2 rounded border border-white/[0.08] bg-white/[0.04] px-1.5 py-0.5 text-[9px] text-zinc-400 font-mono">
            ⌘K
          </kbd>
        </div>
      </div>

      {/* Right: Quick actions and status */}
      <div className="flex items-center gap-2.5">
        {/* Runtime Status Pill */}
        <div className="hidden xl:inline-flex items-center gap-1.5 rounded-full border border-white/[0.07] bg-white/[0.02] px-2.5 py-1 text-[11px] font-mono text-zinc-400">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
          <span>INR Runtime</span>
        </div>

        {/* Demo Scenarios Shortcut */}
        <Link
          href="/scenarios"
          className="inline-flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-white/[0.03] px-2.5 py-1 text-xs font-medium text-zinc-300 hover:text-white hover:bg-white/[0.06] transition-colors"
        >
          <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
          <span className="hidden sm:inline">Scenarios</span>
        </Link>

        {/* Exceptions Notification Link */}
        <Link
          href="/exceptions"
          className="relative flex h-8 w-8 items-center justify-center rounded-md border border-white/[0.07] bg-white/[0.02] text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.05] transition-colors"
          title="Operational Exceptions Queue"
          aria-label="View Operational Exceptions"
        >
          <Bell className="h-3.5 w-3.5" />
          <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-amber-400" />
        </Link>

        {/* Operator Profile */}
        <div className="flex items-center gap-2 pl-2 border-l border-white/[0.07]">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-zinc-800 border border-white/10 text-[11px] font-medium text-zinc-200">
            OP
          </div>
          <div className="hidden 2xl:block text-left text-xs leading-none">
            <div className="font-medium text-zinc-200">Ops Supervisor</div>
            <div className="text-[10px] text-zinc-400 mt-0.5">Primary Session</div>
          </div>
        </div>
      </div>
    </header>
  );
}
