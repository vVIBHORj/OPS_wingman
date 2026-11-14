"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ArrowUpRight,
  Filter,
} from "lucide-react";
import { fetchJson } from "@/lib/api";

interface OrderItemSummary {
  id: string;
  sku: string;
  product_name: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

interface OrderItem {
  id: string;
  order_number: string;
  customer_id: string;
  customer_name?: string;
  customer_email?: string;
  status: string;
  currency: string;
  subtotal: number;
  tax_amount: number;
  shipping_amount: number;
  discount_amount: number;
  total_amount: number;
  created_at: string;
  items: OrderItemSummary[];
  payments: Array<{ id: string; status: string; payment_method: string }>;
  shipments: Array<{ id: string; status: string; carrier: string; tracking_number: string }>;
}

interface OrderListResponse {
  total: number;
  limit: number;
  offset: number;
  items: OrderItem[];
  orders?: OrderItem[];
}

const STATUS_FILTERS = [
  "ALL",
  "PENDING",
  "CONFIRMED",
  "PROCESSING",
  "SHIPPED",
  "DELIVERED",
  "CANCELLED",
  "RETURNED",
];

export default function OrdersPage() {
  const [orders, setOrders] = useState<OrderItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("ALL");
  const [page, setPage] = useState(0);
  const pageSize = 15;

  const loadOrders = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      let query = `/orders?limit=${pageSize}&offset=${page * pageSize}`;
      if (selectedStatus !== "ALL") {
        query += `&status=${selectedStatus}`;
      }
      if (searchTerm.trim()) {
        query += `&search=${encodeURIComponent(searchTerm.trim())}`;
      }

      const res = await fetchJson<OrderListResponse>(query);
      setOrders(res.items || res.orders || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      setError(err.message || "Failed to load orders");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, selectedStatus, searchTerm]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(0);
    loadOrders();
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "DELIVERED":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
      case "SHIPPED":
        return "bg-indigo-500/10 text-indigo-300 border-indigo-500/20";
      case "PROCESSING":
      case "CONFIRMED":
        return "bg-white/[0.06] text-zinc-300 border-white/10";
      case "PENDING":
        return "bg-amber-500/10 text-amber-300 border-amber-500/20";
      case "CANCELLED":
      case "RETURNED":
        return "bg-rose-500/10 text-rose-300 border-rose-500/20";
      default:
        return "bg-zinc-800 text-zinc-400 border-zinc-700";
    }
  };

  const formatInr = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);
  };

  return (
    <div className="space-y-5">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.07] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold tracking-tight text-white">Orders Ledger</h1>
            <span className="rounded-full bg-white/[0.06] border border-white/[0.08] px-2 py-0.5 text-xs font-mono text-zinc-400">
              {total}
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5">
            Operational order ledger with live settlement, line items, and fulfillment state.
          </p>
        </div>

        <button
          onClick={loadOrders}
          disabled={loading}
          className="self-start sm:self-auto flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-white/[0.03] px-2.5 py-1.5 text-xs font-medium text-zinc-300 hover:text-white hover:bg-white/[0.06] transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin text-zinc-300" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter Bar & Search */}
      <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3">
        {/* Status Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 lg:pb-0 scrollbar-none">
          {STATUS_FILTERS.map((st) => (
            <button
              key={st}
              onClick={() => {
                setSelectedStatus(st);
                setPage(0);
              }}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors shrink-0 ${
                selectedStatus === st
                  ? "bg-white/[0.1] text-white shadow-sm border border-white/10"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]"
              }`}
            >
              {st}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <form onSubmit={handleSearchSubmit} className="relative w-full lg:w-72">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Filter order #, email, customer..."
            className="w-full rounded-md border border-white/[0.08] bg-white/[0.02] pl-8 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-400 transition-colors focus:border-zinc-500 focus:bg-white/[0.04] focus:outline-none"
          />
        </form>
      </div>

      {/* Orders Table Container */}
      <div className="rounded-lg border border-white/[0.08] bg-[#0c0d14] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-white/[0.06] bg-white/[0.01] text-[11px] font-medium tracking-wider text-zinc-400 uppercase">
              <tr>
                <th className="px-4 py-3">Order</th>
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3 text-center">Items</th>
                <th className="px-4 py-3 text-right">Amount</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Settlement</th>
                <th className="px-4 py-3">Logistics</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04] text-zinc-300">
              {loading && orders.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-16 text-center text-zinc-400">
                    <RefreshCw className="mx-auto h-5 w-5 animate-spin text-zinc-400 mb-2" />
                    <span>Loading order records...</span>
                  </td>
                </tr>
              ) : orders.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-16 text-center text-zinc-400">
                    <Filter className="mx-auto h-5 w-5 text-zinc-400 mb-2" />
                    <p className="text-xs font-medium text-zinc-300">No matching orders</p>
                    <p className="text-[11px] text-zinc-400 mt-0.5">Try clearing your filters or search query.</p>
                  </td>
                </tr>
              ) : (
                orders.map((o) => {
                  const latestPayment = o.payments?.[0];
                  const latestShipment = o.shipments?.[0];

                  return (
                    <tr key={o.id} className="hover:bg-white/[0.02] transition-colors group">
                      <td className="px-4 py-3 font-mono font-medium text-zinc-100">
                        <Link href={`/orders/${o.id}`} className="hover:text-indigo-400 transition-colors">
                          {o.order_number}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-zinc-400 whitespace-nowrap font-mono text-[11px] tabular-nums">
                        {new Date(o.created_at).toLocaleDateString("en-IN", {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-zinc-200">
                          {o.customer_name || "Customer"}
                        </div>
                        <div className="text-[11px] text-zinc-400 truncate max-w-[150px]">
                          {o.customer_email || o.customer_id.slice(0, 8)}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-center text-zinc-400 font-mono text-[11px] tabular-nums">
                        {o.items?.length || 0}
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-medium text-zinc-100 tabular-nums">
                        {formatInr(o.total_amount)}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-block rounded px-2 py-0.5 text-[10px] font-mono tracking-wide border ${getStatusBadge(
                            o.status
                          )}`}
                        >
                          {o.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {latestPayment ? (
                          <div className="flex items-center gap-1.5 text-[11px]">
                            <span className="font-mono uppercase text-zinc-400 text-[10px]">
                              {latestPayment.payment_method}
                            </span>
                            <span
                              className={`rounded px-1.5 py-0.2 text-[9px] font-mono border ${
                                latestPayment.status === "SUCCESSFUL"
                                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                                  : latestPayment.status === "FAILED"
                                  ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
                                  : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                              }`}
                            >
                              {latestPayment.status}
                            </span>
                          </div>
                        ) : (
                          <span className="text-zinc-600">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {latestShipment ? (
                          <div className="text-[11px]">
                            <div className="text-zinc-300 font-medium">{latestShipment.carrier}</div>
                            <div className="text-[10px] font-mono text-zinc-400">
                              {latestShipment.tracking_number}
                            </div>
                          </div>
                        ) : (
                          <span className="text-zinc-400 text-[11px]">Unassigned</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Link
                          href={`/orders/${o.id}`}
                          className="inline-flex items-center gap-1 rounded border border-white/[0.08] bg-white/[0.02] px-2 py-1 text-[11px] font-medium text-zinc-300 hover:text-white hover:bg-white/[0.06] transition-colors"
                        >
                          <span>View</span>
                          <ArrowUpRight className="h-3 w-3" />
                        </Link>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Table Pagination */}
        <div className="flex items-center justify-between border-t border-white/[0.06] px-4 py-3 text-xs text-zinc-400">
          <div>
            Showing <span className="font-mono text-zinc-200">{orders.length}</span> of{" "}
            <span className="font-mono text-zinc-200">{total}</span> records
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0 || loading}
              className="flex items-center gap-1 rounded border border-white/[0.08] bg-white/[0.02] px-2 py-1 text-zinc-300 hover:text-white hover:bg-white/[0.05] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Previous</span>
            </button>
            <span className="font-mono text-xs px-1">
              Page {page + 1} of {Math.max(1, Math.ceil(total / pageSize))}
            </span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={(page + 1) * pageSize >= total || loading}
              className="flex items-center gap-1 rounded border border-white/[0.08] bg-white/[0.02] px-2 py-1 text-zinc-300 hover:text-white hover:bg-white/[0.05] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <span>Next</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
