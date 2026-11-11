"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  TrendingUp,
  AlertTriangle,
  Clock,
  ShieldAlert,
  CreditCard,
  Truck,
  LifeBuoy,
  ShoppingCart,
  CheckCircle2,
  RefreshCw,
  ArrowRight,
  IndianRupee,
  Activity,
  Flame,
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
  revenue_today: number;
  revenue_this_month: number;
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

  const formatInr = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);
  };

  if (loading && !metrics) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-3 text-slate-400">
        <RefreshCw className="h-8 w-8 animate-spin text-sky-400" />
        <p className="text-sm">Connecting to Operations Runtime &amp; Database...</p>
      </div>
    );
  }

  if (error && !metrics) {
    return (
      <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 p-6 text-center">
        <AlertTriangle className="mx-auto h-10 w-10 text-rose-400 mb-2" />
        <h3 className="text-lg font-bold text-rose-200">Data Synchronization Error</h3>
        <p className="text-sm text-slate-400 mt-1 max-w-md mx-auto">{error}</p>
        <button
          onClick={loadDashboard}
          className="mt-4 rounded-lg bg-rose-600 px-4 py-2 text-xs font-semibold text-white hover:bg-rose-500"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  const m = metrics!;
  const maxDailyRev = Math.max(...(m.recent_daily_revenue.map((d) => d.amount) || [1]), 1);

  return (
    <div className="space-y-6">
      {/* Top Banner / Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-white">
              Operations Command Center
            </h1>
            <span className="rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 text-xs font-medium text-emerald-400">
              Live System
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time fulfillment, payments, shipments, exceptions, and AI agent execution telemetry.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-[11px] text-slate-400 font-mono">
            Synced: {lastRefreshed.toLocaleTimeString()}
          </span>
          <button
            onClick={loadDashboard}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-800 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-sky-400" : ""}`} />
            <span>Refresh</span>
          </button>
          <Link
            href="/scenarios"
            className="flex items-center gap-1.5 rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-sky-500 transition-colors"
          >
            <span>Trigger Scenario</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>

      {/* Critical Operational Alerts Ribbon */}
      {(m.pending_approvals > 0 || m.delayed_shipments > 0 || m.failed_payments > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {m.pending_approvals > 0 && (
            <Link
              href="/approvals"
              className="flex items-center justify-between rounded-xl border border-amber-500/30 bg-amber-950/20 p-3.5 hover:bg-amber-950/30 transition-all group"
            >
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-amber-500/20 p-2 text-amber-400">
                  <ShieldAlert className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xs font-bold text-amber-300">
                    {m.pending_approvals} High-Risk Action{m.pending_approvals > 1 ? "s" : ""} Gated
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Awaiting human supervisor authorization
                  </div>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-amber-400 group-hover:translate-x-0.5 transition-transform" />
            </Link>
          )}

          {m.delayed_shipments > 0 && (
            <Link
              href="/shipments?is_delayed=true"
              className="flex items-center justify-between rounded-xl border border-rose-500/30 bg-rose-950/20 p-3.5 hover:bg-rose-950/30 transition-all group"
            >
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-rose-500/20 p-2 text-rose-400">
                  <Truck className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xs font-bold text-rose-300">
                    {m.delayed_shipments} Transit Delay{m.delayed_shipments > 1 ? "s" : ""}
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Shipments breached delivery target window
                  </div>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-rose-400 group-hover:translate-x-0.5 transition-transform" />
            </Link>
          )}

          {m.failed_payments > 0 && (
            <Link
              href="/payments?status=FAILED"
              className="flex items-center justify-between rounded-xl border border-orange-500/30 bg-orange-950/20 p-3.5 hover:bg-orange-950/30 transition-all group"
            >
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-orange-500/20 p-2 text-orange-400">
                  <CreditCard className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xs font-bold text-orange-300">
                    {m.failed_payments} Payment Authorization Failures
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Failed payment retry notifications required
                  </div>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-orange-400 group-hover:translate-x-0.5 transition-transform" />
            </Link>
          )}
        </div>
      )}

      {/* Primary KPI Grid (14 Operational Metrics) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-3">
        {/* Total Orders */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] font-medium">Total Orders</span>
            <ShoppingCart className="h-3.5 w-3.5 text-sky-400" />
          </div>
          <div className="text-xl font-bold text-white">{m.total_orders}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Lifetime system total</div>
        </div>

        {/* Orders Today */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] font-medium">Orders Today</span>
            <Flame className="h-3.5 w-3.5 text-amber-400" />
          </div>
          <div className="text-xl font-bold text-white">{m.orders_today}</div>
          <div className="text-[10px] text-emerald-400 mt-0.5 font-medium">New orders logged</div>
        </div>

        {/* Processing Orders */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] font-medium">In Processing</span>
            <Activity className="h-3.5 w-3.5 text-indigo-400" />
          </div>
          <div className="text-xl font-bold text-white">{m.orders_processing}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Warehouse dispatching</div>
        </div>

        {/* Orders At Risk */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] font-medium">Orders At Risk</span>
            <AlertTriangle className="h-3.5 w-3.5 text-rose-400" />
          </div>
          <div className="text-xl font-bold text-rose-400">{m.orders_at_risk}</div>
          <div className="text-[10px] text-rose-400/80 mt-0.5">Delayed or ticketed</div>
        </div>

        {/* Revenue Today */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] font-medium">Revenue Today</span>
            <IndianRupee className="h-3.5 w-3.5 text-emerald-400" />
          </div>
          <div className="text-lg font-bold text-emerald-400">{formatInr(m.revenue_today)}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Settled captured total</div>
        </div>

        {/* Revenue This Month */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] font-medium">Month Revenue</span>
            <TrendingUp className="h-3.5 w-3.5 text-emerald-400" />
          </div>
          <div className="text-lg font-bold text-emerald-400">{formatInr(m.revenue_this_month)}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Current billing cycle</div>
        </div>

        {/* In-Transit Shipments */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] font-medium">In Transit</span>
            <Truck className="h-3.5 w-3.5 text-sky-400" />
          </div>
          <div className="text-xl font-bold text-sky-300">{m.shipments_in_transit}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Active carrier routes</div>
        </div>

        {/* Delayed Shipments */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] font-medium">Delayed Shipments</span>
            <Clock className="h-3.5 w-3.5 text-rose-400" />
          </div>
          <div className="text-xl font-bold text-rose-400">{m.delayed_shipments}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Exceeded target ETA</div>
        </div>

        {/* Pending Payments */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] font-medium">Pending Payments</span>
            <CreditCard className="h-3.5 w-3.5 text-amber-400" />
          </div>
          <div className="text-xl font-bold text-amber-300">{m.pending_payments}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Awaiting capture/gateway</div>
        </div>

        {/* Failed Payments */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] font-medium">Failed Payments</span>
            <AlertTriangle className="h-3.5 w-3.5 text-rose-400" />
          </div>
          <div className="text-xl font-bold text-rose-400">{m.failed_payments}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Authorization errors</div>
        </div>

        {/* Pending Refunds */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] font-medium">Pending Refunds</span>
            <RefreshCw className="h-3.5 w-3.5 text-purple-400" />
          </div>
          <div className="text-xl font-bold text-purple-300">{m.refunds_pending}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Disbursement in progress</div>
        </div>

        {/* Open Support Tickets */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] font-medium">Open Tickets</span>
            <LifeBuoy className="h-3.5 w-3.5 text-sky-400" />
          </div>
          <div className="text-xl font-bold text-white">{m.open_tickets}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Active customer inquiries</div>
        </div>

        {/* Pending Approvals */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] font-medium">Pending Approvals</span>
            <ShieldAlert className="h-3.5 w-3.5 text-amber-400" />
          </div>
          <div className="text-xl font-bold text-amber-400">{m.pending_approvals}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Supervisor review</div>
        </div>

        {/* SLA Breaches */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-[11px] font-medium">SLA Breaches</span>
            <AlertTriangle className="h-3.5 w-3.5 text-rose-400" />
          </div>
          <div className="text-xl font-bold text-rose-400">{m.sla_breaches}</div>
          <div className="text-[10px] text-rose-400/80 mt-0.5">&gt;48h resolution exceeded</div>
        </div>
      </div>

      {/* Charts & Distribution Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 7-Day Revenue Trend */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-white">7-Day Revenue &amp; Order Trend</h3>
              <p className="text-xs text-slate-400">
                Daily settled volume captured across all payment gateways
              </p>
            </div>
            <span className="text-xs font-mono text-emerald-400 font-semibold">
              Peak: {formatInr(maxDailyRev)}
            </span>
          </div>

          <div className="h-44 flex items-end gap-3 pt-4 pb-2 border-b border-slate-800">
            {m.recent_daily_revenue.map((day, idx) => {
              const heightPct = Math.max(12, Math.round((day.amount / maxDailyRev) * 100));
              const orderCount = m.recent_daily_orders[idx]?.count || 0;
              return (
                <div key={day.date} className="flex-1 flex flex-col items-center gap-1.5 h-full justify-end group">
                  <div className="opacity-0 group-hover:opacity-100 transition-opacity text-[10px] font-mono text-slate-300 text-center">
                    {formatInr(day.amount)}
                    <br />
                    <span className="text-sky-400">{orderCount} ord</span>
                  </div>
                  <div
                    style={{ height: `${heightPct}%` }}
                    className="w-full rounded-t-md bg-gradient-to-t from-sky-600/70 to-sky-400 transition-all group-hover:from-sky-500 group-hover:to-sky-300"
                  />
                  <span className="text-[10px] text-slate-400 font-mono mt-1">{day.date}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Payment Methods Distribution */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
          <h3 className="text-sm font-bold text-white mb-1">Payment Method Mix</h3>
          <p className="text-xs text-slate-400 mb-4">
            Customer gateway transaction distribution
          </p>

          <div className="space-y-3">
            {Object.entries(m.payment_method_stats).map(([method, count]) => {
              const totalPayments = Object.values(m.payment_method_stats).reduce((a, b) => a + b, 0) || 1;
              const pct = Math.round((count / totalPayments) * 100);
              return (
                <div key={method} className="space-y-1">
                  <div className="flex justify-between text-xs font-medium">
                    <span className="text-slate-300 uppercase">{method}</span>
                    <span className="text-slate-400 font-mono">
                      {count} ({pct}%)
                    </span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                    <div
                      style={{ width: `${pct}%` }}
                      className={`h-full rounded-full ${
                        method === "UPI"
                          ? "bg-emerald-500"
                          : method === "CARD"
                          ? "bg-sky-500"
                          : method === "NET_BANKING"
                          ? "bg-indigo-500"
                          : method === "COD"
                          ? "bg-amber-500"
                          : "bg-purple-500"
                      }`}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Orders Status Distribution Bar */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-white">Order Pipeline Distribution</h3>
          <Link href="/orders" className="text-xs text-sky-400 hover:text-sky-300 font-medium">
            View All Orders &rarr;
          </Link>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
          {Object.entries(m.orders_by_status).map(([st, cnt]) => (
            <div key={st} className="rounded-lg border border-slate-800/80 bg-slate-950 p-3">
              <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">
                {st}
              </div>
              <div className="text-lg font-bold text-white mt-1">{cnt}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
