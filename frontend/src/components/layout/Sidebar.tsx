"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Bot,
  ShoppingCart,
  Users,
  Package,
  CreditCard,
  Truck,
  LifeBuoy,
  ShieldAlert,
  AlertTriangle,
  History,
  PlayCircle,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
} from "lucide-react";

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  badgeVariant?: "default" | "warning" | "danger" | "success";
}

const navItems: NavItem[] = [
  { name: "Command Center", href: "/", icon: LayoutDashboard },
  { name: "AI Ops Agent", href: "/agent", icon: Bot, badge: "AI" },
  { name: "Orders", href: "/orders", icon: ShoppingCart },
  { name: "Customers", href: "/customers", icon: Users },
  { name: "Catalog", href: "/products", icon: Package },
  { name: "Payments", href: "/payments", icon: CreditCard },
  { name: "Logistics", href: "/shipments", icon: Truck },
  { name: "Support Tickets", href: "/tickets", icon: LifeBuoy },
  {
    name: "Approval Queue",
    href: "/approvals",
    icon: ShieldAlert,
    badgeVariant: "warning",
  },
  {
    name: "Exceptions Queue",
    href: "/exceptions",
    icon: AlertTriangle,
    badgeVariant: "danger",
  },
  { name: "Audit Explorer", href: "/audit", icon: History },
  {
    name: "Scenario Runner",
    href: "/scenarios",
    icon: PlayCircle,
    badgeVariant: "success",
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`fixed top-0 bottom-0 left-0 z-40 flex flex-col border-r border-slate-800 bg-slate-950/95 backdrop-blur-md transition-all duration-300 ${
        collapsed ? "w-20" : "w-64"
      }`}
    >
      {/* Brand Header */}
      <div className="flex h-16 items-center justify-between border-b border-slate-800/80 px-4">
        {!collapsed ? (
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-sky-500 to-indigo-600 shadow-md shadow-sky-500/20">
              <ShieldCheck className="h-5 w-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-bold tracking-tight text-white text-base">
                  OPSwingman
                </span>
                <span className="rounded bg-sky-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-sky-400">
                  v2.0
                </span>
              </div>
              <p className="text-[11px] font-medium text-slate-400">
                Operations Engine
              </p>
            </div>
          </Link>
        ) : (
          <Link href="/" className="mx-auto flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-sky-500 to-indigo-600">
            <ShieldCheck className="h-5 w-5 text-white" />
          </Link>
        )}

        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex h-7 w-7 items-center justify-center rounded-md border border-slate-800 text-slate-400 hover:bg-slate-900 hover:text-white"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>

      {/* Navigation List */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4 scrollbar-thin">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all ${
                isActive
                  ? "bg-sky-500/10 text-sky-400 font-semibold border-l-2 border-sky-400"
                  : "text-slate-400 hover:bg-slate-900/80 hover:text-slate-100"
              }`}
              title={collapsed ? item.name : undefined}
            >
              <Icon
                className={`h-5 w-5 shrink-0 transition-colors ${
                  isActive ? "text-sky-400" : "text-slate-400 group-hover:text-slate-200"
                }`}
              />
              {!collapsed && (
                <div className="flex flex-1 items-center justify-between">
                  <span className="truncate">{item.name}</span>
                  {item.badge && (
                    <span className="rounded bg-sky-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-sky-400">
                      {item.badge}
                    </span>
                  )}
                </div>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Operational Status Footer */}
      {!collapsed ? (
        <div className="border-t border-slate-800/80 p-3 bg-slate-900/40">
          <div className="rounded-lg border border-slate-800 bg-slate-950 p-2.5">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] font-medium text-slate-400">
                Runtime Guard
              </span>
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                ACTIVE
              </span>
            </div>
            <p className="text-[10px] text-slate-400 leading-tight">
              Deterministic policy enforcement &amp; transactional idempotency active.
            </p>
          </div>
        </div>
      ) : (
        <div className="border-t border-slate-800/80 p-3 text-center">
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
        </div>
      )}
    </aside>
  );
}

