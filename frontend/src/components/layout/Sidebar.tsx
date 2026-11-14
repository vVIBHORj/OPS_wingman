"use client";

import React from "react";
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
  X,
} from "lucide-react";

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  badgeTone?: "info" | "warning" | "danger";
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const navSections: NavSection[] = [
  {
    title: "Operations",
    items: [
      { name: "Command Center", href: "/", icon: LayoutDashboard },
      { name: "AI Ops Agent", href: "/agent", icon: Bot, badge: "AI", badgeTone: "info" },
      { name: "Scenario Runner", href: "/scenarios", icon: PlayCircle },
    ],
  },
  {
    title: "Commerce & Fulfillment",
    items: [
      { name: "Orders", href: "/orders", icon: ShoppingCart },
      { name: "Customers", href: "/customers", icon: Users },
      { name: "Catalog", href: "/products", icon: Package },
      { name: "Payments", href: "/payments", icon: CreditCard },
      { name: "Logistics", href: "/shipments", icon: Truck },
    ],
  },
  {
    title: "Governance & Support",
    items: [
      { name: "Support Tickets", href: "/tickets", icon: LifeBuoy },
      { name: "Approval Queue", href: "/approvals", icon: ShieldAlert, badge: "Gated", badgeTone: "warning" },
      { name: "Exceptions Queue", href: "/exceptions", icon: AlertTriangle, badge: "Alert", badgeTone: "danger" },
      { name: "Audit Explorer", href: "/audit", icon: History },
    ],
  },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

export default function Sidebar({
  collapsed,
  onToggle,
  mobileOpen,
  onCloseMobile,
}: SidebarProps) {
  const pathname = usePathname();

  const isLinkActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  const sidebarContent = (
    <div className="flex h-full flex-col justify-between">
      {/* Brand & Collapse Header */}
      <div>
        <div className="flex h-14 items-center justify-between px-3.5 border-b border-white/[0.07]">
          {!collapsed ? (
            <Link href="/" className="flex items-center gap-2.5 group">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-zinc-900 border border-white/10 text-zinc-100 shadow-sm group-hover:border-zinc-500 transition-colors">
                <ShieldCheck className="h-4 w-4 text-zinc-200" />
              </div>
              <div className="flex items-center gap-1.5">
                <span className="font-semibold text-sm tracking-tight text-zinc-100">
                  OPS<span className="text-zinc-400 font-normal">wingman</span>
                </span>
                <span className="rounded bg-white/[0.06] border border-white/[0.08] px-1 py-0.2 text-[10px] font-mono text-zinc-400">
                  v2
                </span>
              </div>
            </Link>
          ) : (
            <Link href="/" className="mx-auto flex h-7 w-7 items-center justify-center rounded-md bg-zinc-900 border border-white/10">
              <ShieldCheck className="h-4 w-4 text-zinc-200" />
            </Link>
          )}

          {/* Desktop Toggle Button */}
          <button
            onClick={onToggle}
            className="hidden md:flex h-6 w-6 items-center justify-center rounded text-zinc-400 hover:text-zinc-100 hover:bg-white/[0.05] transition-colors"
            title={collapsed ? "Expand sidebar (⌘B)" : "Collapse sidebar (⌘B)"}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
          </button>

          {/* Mobile Close Button */}
          <button
            onClick={onCloseMobile}
            className="flex md:hidden h-7 w-7 items-center justify-center rounded text-zinc-400 hover:text-white"
            aria-label="Close sidebar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Navigation Sections */}
        <nav className="space-y-5 px-2.5 py-4 overflow-y-auto max-h-[calc(100vh-125px)]">
          {navSections.map((section) => (
            <div key={section.title} className="space-y-1">
              {!collapsed && (
                <div className="px-2 pb-1 text-[10px] font-semibold tracking-wider text-zinc-400 uppercase">
                  {section.title}
                </div>
              )}
              <div className="space-y-0.5">
                {section.items.map((item) => {
                  const Icon = item.icon;
                  const active = isLinkActive(item.href);

                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={onCloseMobile}
                      title={collapsed ? item.name : undefined}
                      className={`group flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                        active
                          ? "bg-white/[0.08] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]"
                          : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03]"
                      }`}
                    >
                      <Icon
                        className={`h-4 w-4 shrink-0 transition-colors ${
                          active ? "text-white" : "text-zinc-400 group-hover:text-zinc-300"
                        }`}
                      />
                      {!collapsed && (
                        <div className="flex flex-1 items-center justify-between overflow-hidden">
                          <span className="truncate">{item.name}</span>
                          {item.badge && (
                            <span
                              className={`rounded px-1.5 py-0.2 text-[9px] font-mono tracking-wide uppercase border ${
                                item.badgeTone === "warning"
                                  ? "bg-amber-500/10 text-amber-300 border-amber-500/20"
                                  : item.badgeTone === "danger"
                                  ? "bg-rose-500/10 text-rose-300 border-rose-500/20"
                                  : "bg-indigo-500/10 text-indigo-300 border-indigo-500/20"
                              }`}
                            >
                              {item.badge}
                            </span>
                          )}
                        </div>
                      )}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </div>

      {/* Footer System Status */}
      <div className="p-3 border-t border-white/[0.07]">
        {!collapsed ? (
          <div className="rounded-md border border-white/[0.06] bg-white/[0.02] p-2.5">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-zinc-400 font-medium">Deterministic Engine</span>
              <span className="inline-flex items-center gap-1.5 font-mono text-[10px] text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                ACTIVE
              </span>
            </div>
            <p className="mt-1 text-[10px] text-zinc-400 leading-tight">
              State verification &amp; policy boundaries enforced
            </p>
          </div>
        ) : (
          <div className="flex justify-center" title="Deterministic Engine Active">
            <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          onClick={onCloseMobile}
          className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm md:hidden transition-opacity"
          aria-hidden="true"
        />
      )}

      {/* Desktop Persistent Sidebar */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-40 hidden md:flex flex-col border-r border-white/[0.07] bg-[#0b0c12] transition-all duration-200 ease-out ${
          collapsed ? "w-20" : "w-64"
        }`}
      >
        {sidebarContent}
      </aside>

      {/* Mobile Slide-over Drawer */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 flex w-72 flex-col border-r border-white/[0.07] bg-[#0b0c12] md:hidden transition-transform duration-200 ease-out ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {sidebarContent}
      </aside>
    </>
  );
}
