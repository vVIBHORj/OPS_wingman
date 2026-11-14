"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  TrendingUp,
  CreditCard,
  Truck,
  ShieldAlert,
  ChevronRight,
  RefreshCw,
  Sparkles,
  AlertTriangle,
  Receipt,
  ShoppingBag,
} from "lucide-react";
import { fetchJson } from "@/lib/api";

interface DailyRevenue {
  date: string;
  amount: number;
}

interface DailyOrder {
  date: string;
  count: number;
}

interface DashboardMetrics {
  total_orders: number;
  orders_today: number;
  orders_processing: number;
  orders_at_risk: number;
  revenue_today: number | string;
  revenue_this_month: number | string;
  pending_payments: number;
  failed_payments: number;
  refunds_pending: number;
  shipments_in_transit: number;
  delayed_shipments: number;
  open_tickets: number;
  pending_approvals: number;
  sla_breaches: number;
  orders_by_status: Record<string, number>;
  payment_method_stats: Record<string, number>;
  recent_daily_revenue: DailyRevenue[];
  recent_daily_orders: DailyOrder[];
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());
  const [chartView, setChartView] = useState<"revenue" | "orders">("revenue");
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  const loadDashboard = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchJson<DashboardMetrics>("/operations/dashboard");
      setMetrics(data);
      setLastRefreshed(new Date());
    } catch (err: any) {
      setError(err.message || "Failed to load dashboard metrics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const formatInr = (val: number | string) => {
    const num = typeof val === "string" ? parseFloat(val) : Number(val);
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(isNaN(num) ? 0 : num);
  };

  if (loading && !metrics) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-3 text-zinc-300">
        <RefreshCw className="h-5 w-5 animate-spin text-zinc-400" />
        <p className="text-xs font-mono text-zinc-300">Connecting to operations runtime...</p>
      </div>
    );
  }

  if (error && !metrics) {
    return (
      <div className="rounded-lg border border-red-500/20 bg-red-500/[0.04] p-6 text-center max-w-lg mx-auto my-12">
        <AlertTriangle className="mx-auto h-6 w-6 text-rose-400 mb-2" />
        <h3 className="text-sm font-semibold text-zinc-100">System Connection Error</h3>
        <p className="text-xs text-zinc-300 mt-2 leading-relaxed font-mono">{error}</p>
        <button
          onClick={loadDashboard}
          className="mt-4 rounded-md bg-white/[0.08] hover:bg-white/[0.12] border border-white/10 px-3.5 py-1.5 text-xs font-medium text-zinc-200 transition-colors"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  const m = metrics!;
  const maxDailyRev = Math.max(...(m.recent_daily_revenue.map((d) => d.amount) || [1]), 1);
  const maxDailyOrd = Math.max(...(m.recent_daily_orders.map((d) => d.count) || [1]), 1);

  const totalActionItems = m.pending_approvals + m.delayed_shipments + m.failed_payments;
  const deliveredOrders = m.orders_by_status?.DELIVERED || 0;
  const deliveredPct = m.total_orders > 0 ? Math.round((deliveredOrders / m.total_orders) * 100) : 0;
  const upiCount = m.payment_method_stats?.UPI || 0;
  const totalPayments = Object.values(m.payment_method_stats || {}).reduce((a, b) => a + b, 0) || 1;
  const upiPct = Math.round((upiCount / totalPayments) * 100);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
            Command Center
          </h1>
          <p className="text-xs text-zinc-300 mt-1">
            Continuous operations telemetry: orders, settlement, fulfillment, and exception gating.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-zinc-400 font-mono hidden sm:inline">
            Updated {lastRefreshed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
          </span>
          <button
            onClick={loadDashboard}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-white/[0.03] px-2.5 py-1.5 text-xs font-medium text-zinc-200 hover:text-white hover:bg-white/[0.06] transition-colors disabled:opacity-50"
            title="Refresh metrics"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-zinc-300" : ""}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
          <Link
            href="/scenarios"
            className="flex items-center gap-1.5 rounded-md bg-zinc-100 hover:bg-white text-zinc-950 px-3 py-1.5 text-xs font-semibold shadow-sm transition-all active:scale-[0.99]"
          >
            <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
            <span>Scenario Runner</span>
          </Link>
        </div>
      </div>

      {/* Critical Exceptions & Gating Alert Strip */}
      {totalActionItems > 0 && (
        <div className="rounded-lg border border-amber-500/25 bg-amber-500/[0.05] p-3 sm:p-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <span className="flex h-2 w-2 rounded-full bg-amber-400 animate-pulse shrink-0" />
              <div className="text-xs text-zinc-200">
                <span className="font-semibold text-zinc-100">{totalActionItems} operational items</span> require supervisor or carrier intervention:
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 text-xs">
              {m.pending_approvals > 0 && (
                <Link
                  href="/approvals"
                  className="inline-flex items-center gap-1.5 rounded bg-amber-500/10 border border-amber-500/25 px-2.5 py-1 text-xs font-medium text-amber-300 hover:bg-amber-500/20 transition-colors"
                >
                  <ShieldAlert className="h-3.5 w-3.5" />
                  <span>{m.pending_approvals} Gated Approvals</span>
                  <ChevronRight className="h-3 w-3" />
                </Link>
              )}

              {m.delayed_shipments > 0 && (
                <Link
                  href="/shipments?is_delayed=true"
                  className="inline-flex items-center gap-1.5 rounded bg-rose-500/10 border border-rose-500/25 px-2.5 py-1 text-xs font-medium text-rose-300 hover:bg-rose-500/20 transition-colors"
                >
                  <Truck className="h-3.5 w-3.5" />
                  <span>{m.delayed_shipments} Transit Delays</span>
                  <ChevronRight className="h-3 w-3" />
                </Link>
              )}

              {m.failed_payments > 0 && (
                <Link
                  href="/payments?status=FAILED"
                  className="inline-flex items-center gap-1.5 rounded bg-zinc-800 border border-zinc-700 px-2.5 py-1 text-xs font-medium text-zinc-200 hover:text-white hover:bg-zinc-700 transition-colors"
                >
                  <CreditCard className="h-3.5 w-3.5" />
                  <span>{m.failed_payments} Failed Payments</span>
                  <ChevronRight className="h-3 w-3" />
                </Link>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Primary 4-Card Executive Metric Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        {/* Card 1: Monthly Revenue Velocity */}
        <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-4 flex flex-col justify-between hover:border-white/[0.14] transition-colors">
          <div>
            <div className="flex items-center justify-between text-zinc-300 mb-1">
              <span className="text-xs font-semibold tracking-wider uppercase text-zinc-300">Revenue (MTD)</span>
              <span className="text-[11px] font-mono text-emerald-300 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20 font-medium">
                Settled
              </span>
            </div>
            <div className="text-2xl font-semibold tracking-tight text-zinc-100 tabular-nums font-mono mt-1">
              {formatInr(m.revenue_this_month)}
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs text-zinc-300">
            <span>Today&apos;s settlement:</span>
            <span className="font-mono text-zinc-200 font-medium tabular-nums">{formatInr(m.revenue_today)}</span>
          </div>
        </div>

        {/* Card 2: Total Orders Volume & Delivery */}
        <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-4 flex flex-col justify-between hover:border-white/[0.14] transition-colors">
          <div>
            <div className="flex items-center justify-between text-zinc-300 mb-1">
              <span className="text-xs font-semibold tracking-wider uppercase text-zinc-300">Total Orders</span>
              <span className="text-[11px] font-mono text-zinc-300 bg-white/[0.04] px-1.5 py-0.5 rounded border border-white/[0.08]">
                {m.orders_today} today
              </span>
            </div>
            <div className="text-2xl font-semibold tracking-tight text-zinc-100 tabular-nums font-mono mt-1">
              {m.total_orders}
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs text-zinc-300">
            <span>Delivered orders:</span>
            <span className="font-mono text-zinc-200 font-medium tabular-nums">
              {deliveredOrders} ({deliveredPct}%)
            </span>
          </div>
        </div>

        {/* Card 3: Active Fulfillment */}
        <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-4 flex flex-col justify-between hover:border-white/[0.14] transition-colors">
          <div>
            <div className="flex items-center justify-between text-zinc-300 mb-1">
              <span className="text-xs font-semibold tracking-wider uppercase text-zinc-300">In-Transit Freight</span>
              <span className="text-[11px] font-mono text-sky-300 bg-sky-500/10 px-1.5 py-0.5 rounded border border-sky-500/20 font-medium">
                Active Waybills
              </span>
            </div>
            <div className="text-2xl font-semibold tracking-tight text-zinc-100 tabular-nums font-mono mt-1">
              {m.shipments_in_transit}
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs text-zinc-300">
            <span>Transit delays:</span>
            <span className={`font-mono tabular-nums ${m.delayed_shipments > 0 ? "text-amber-300 font-medium" : "text-zinc-200"}`}>
              {m.delayed_shipments} packages
            </span>
          </div>
        </div>

        {/* Card 4: Incident & Risk Health */}
        <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-4 flex flex-col justify-between hover:border-white/[0.14] transition-colors">
          <div>
            <div className="flex items-center justify-between text-zinc-300 mb-1">
              <span className="text-xs font-semibold tracking-wider uppercase text-zinc-300">Orders At Risk</span>
              <span className={`text-[11px] font-mono px-1.5 py-0.5 rounded border font-medium ${
                m.orders_at_risk > 0 ? "text-rose-300 bg-rose-500/10 border-rose-500/20" : "text-zinc-300 bg-zinc-800/40 border-zinc-700/40"
              }`}>
                Exceptions
              </span>
            </div>
            <div className="text-2xl font-semibold tracking-tight text-zinc-100 tabular-nums font-mono mt-1">
              {m.orders_at_risk}
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs text-zinc-300">
            <span>SLA breaches:</span>
            <span className={`font-mono tabular-nums font-medium ${m.sla_breaches > 0 ? "text-rose-300" : "text-zinc-200"}`}>
              {m.sla_breaches} tickets
            </span>
          </div>
        </div>
      </div>

      {/* Asymmetric Section: 7-Day Chart & Payment Channels */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column (8 cols): Interactive Revenue & Volume Chart */}
        <div className="lg:col-span-8 rounded-xl border border-white/[0.08] bg-[#0c0d14] p-5 flex flex-col justify-between">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <div>
              <h3 className="text-sm font-semibold text-zinc-100">Operations Throughput</h3>
              <p className="text-xs text-zinc-300 mt-0.5">7-day continuous settlement and order generation trend</p>
            </div>

            {/* Metric Toggle Tabs */}
            <div className="inline-flex rounded-md bg-white/[0.04] p-0.5 border border-white/[0.08]">
              <button
                onClick={() => setChartView("revenue")}
                className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                  chartView === "revenue"
                    ? "bg-white/[0.12] text-zinc-100 shadow-sm border border-white/[0.1]"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                Revenue (INR)
              </button>
              <button
                onClick={() => setChartView("orders")}
                className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                  chartView === "orders"
                    ? "bg-white/[0.12] text-zinc-100 shadow-sm border border-white/[0.1]"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                Order Volume
              </button>
            </div>
          </div>

          {/* Chart Display Area */}
          <div className="pt-6 pb-2">
            <div className="h-48 flex items-end gap-2 sm:gap-4 border-b border-white/[0.08] pb-3">
              {m.recent_daily_revenue.map((day, idx) => {
                const orderCount = m.recent_daily_orders[idx]?.count || 0;
                const heightPct = chartView === "revenue"
                  ? Math.max(10, Math.round((day.amount / maxDailyRev) * 100))
                  : Math.max(10, Math.round((orderCount / maxDailyOrd) * 100));

                const isHovered = hoveredIdx === idx;

                return (
                  <div
                    key={day.date}
                    className="flex-1 flex flex-col items-center justify-end h-full group relative cursor-pointer"
                    onMouseEnter={() => setHoveredIdx(idx)}
                    onMouseLeave={() => setHoveredIdx(null)}
                  >
                    {/* Tooltip */}
                    <div
                      className={`absolute -top-12 z-20 pointer-events-none rounded-md bg-zinc-900 border border-white/10 px-2.5 py-1 text-center shadow-lg transition-all duration-150 ${
                        isHovered ? "opacity-100 translate-y-0" : "opacity-0 translate-y-1"
                      }`}
                    >
                      <div className="text-xs font-mono font-semibold text-white tabular-nums">
                        {formatInr(day.amount)}
                      </div>
                      <div className="text-[11px] text-zinc-300 font-mono">
                        {orderCount} orders
                      </div>
                    </div>

                    {/* Bar Column */}
                    <div className="w-full max-w-[48px] bg-white/[0.03] hover:bg-white/[0.06] rounded-t transition-colors h-full flex items-end">
                      <div
                        style={{ height: `${heightPct}%` }}
                        className={`w-full rounded-t transition-all duration-200 ${
                          isHovered
                            ? "bg-zinc-200"
                            : chartView === "revenue"
                            ? "bg-white/[0.35]"
                            : "bg-indigo-400/60"
                        }`}
                      />
                    </div>

                    <span className="text-[11px] text-zinc-300 font-mono mt-2 tracking-tight">
                      {day.date}
                    </span>
                  </div>
                );
              })}
            </div>

            <div className="flex items-center justify-between text-xs text-zinc-300 font-mono pt-3">
              <span>Past 7 days continuous</span>
              <span>Peak: {chartView === "revenue" ? formatInr(maxDailyRev) : `${maxDailyOrd} orders/day`}</span>
            </div>
          </div>
        </div>

        {/* Right Column (4 cols): Payment Channel Distribution */}
        <div className="lg:col-span-4 rounded-xl border border-white/[0.08] bg-[#0c0d14] p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm font-semibold text-zinc-100">Payment Channels</h3>
              <Link href="/payments" className="text-xs font-medium text-zinc-300 hover:text-white transition-colors">
                Ledger &rarr;
              </Link>
            </div>
            <p className="text-xs text-zinc-300 mb-4">Customer gateway settlement distribution</p>

            <div className="space-y-3.5">
              {Object.entries(m.payment_method_stats).map(([method, count]) => {
                const pct = Math.round((count / totalPayments) * 100);
                const isUpi = method === "UPI";

                return (
                  <div key={method} className="space-y-1.5">
                    <div className="flex justify-between items-center text-xs">
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold text-zinc-200 uppercase tracking-wide text-xs">
                          {method === "NETBANKING" ? "Net Banking" : method}
                        </span>
                        {isUpi && (
                          <span className="rounded bg-emerald-500/10 border border-emerald-500/20 px-1 py-0.2 text-[10px] font-mono text-emerald-300">
                            Primary Rail
                          </span>
                        )}
                      </div>
                      <span className="font-mono text-zinc-300 tabular-nums text-xs font-medium">
                        {count} ({pct}%)
                      </span>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-white/[0.06] overflow-hidden">
                      <div
                        style={{ width: `${pct}%` }}
                        className={`h-full rounded-full ${
                          isUpi
                            ? "bg-emerald-400"
                            : method === "CARD"
                            ? "bg-zinc-200"
                            : method === "NETBANKING" || method === "NET_BANKING"
                            ? "bg-indigo-400"
                            : "bg-amber-400"
                        }`}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="mt-5 pt-4 border-t border-white/[0.06] flex items-center justify-between text-xs text-zinc-300">
            <span>Pending settlement:</span>
            <span className="font-mono text-zinc-200 font-semibold tabular-nums">{m.pending_payments} txns</span>
          </div>
        </div>
      </div>

      {/* Order Pipeline Segmented Grid */}
      <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-zinc-100">Order Pipeline Distribution</h3>
            <p className="text-xs text-zinc-300 mt-0.5">Status breakdown across the 507-order enterprise catalog</p>
          </div>
          <Link href="/orders" className="text-xs font-medium text-zinc-300 hover:text-white transition-colors">
            View All Orders &rarr;
          </Link>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5">
          {Object.entries(m.orders_by_status).map(([st, cnt]) => (
            <div
              key={st}
              className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3 text-left transition-colors hover:border-white/10"
            >
              <div className="text-[11px] font-semibold text-zinc-300 uppercase tracking-wider">
                {st}
              </div>
              <div className="text-lg font-semibold text-zinc-100 font-mono tabular-nums mt-1">
                {cnt}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
