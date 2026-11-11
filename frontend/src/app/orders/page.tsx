"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  ShoppingCart,
  Search,
  Filter,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Ban,
  CheckCircle2,
  Clock,
  Truck,
  RotateCcw,
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
        return "bg-sky-500/10 text-sky-400 border-sky-500/20";
      case "PROCESSING":
      case "CONFIRMED":
        return "bg-indigo-500/10 text-indigo-400 border-indigo-500/20";
      case "PENDING":
        return "bg-amber-500/10 text-amber-400 border-amber-500/20";
      case "CANCELLED":
      case "RETURNED":
        return "bg-rose-500/10 text-rose-400 border-rose-500/20";
      default:
        return "bg-slate-800 text-slate-300 border-slate-700";
    }
  };

  const formatInr = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
    }).format(val);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <ShoppingCart className="h-6 w-6 text-sky-400" />
            Orders Management
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Full transactional order lifecycle, line items, payment capture, and fulfillment status.
          </p>
        </div>

        <button
          onClick={loadOrders}
          disabled={loading}
          className="self-start sm:self-auto flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-800 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-sky-400" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Search & Filters */}
      <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4">
        {/* Status Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 lg:pb-0 scrollbar-thin">
          {STATUS_FILTERS.map((st) => (
            <button
              key={st}
              onClick={() => {
                setSelectedStatus(st);
                setPage(0);
              }}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors shrink-0 ${
                selectedStatus === st
                  ? "bg-sky-500 text-white font-semibold"
                  : "bg-slate-900 text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              }`}
            >
              {st}
            </button>
          ))}
        </div>

        {/* Search Bar */}
        <form onSubmit={handleSearchSubmit} className="relative w-full lg:w-80">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search order #, customer, email..."
            className="w-full rounded-lg border border-slate-800 bg-slate-900/80 pl-9 pr-4 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
          />
        </form>
      </div>

      {/* Orders Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden shadow">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 bg-slate-900/80 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-4 py-3">Order Number</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3">Items</th>
                <th className="px-4 py-3">Total Amount</th>
                <th className="px-4 py-3">Order Status</th>
                <th className="px-4 py-3">Payment</th>
                <th className="px-4 py-3">Logistics</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {loading && orders.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-500">
                    <RefreshCw className="mx-auto h-6 w-6 animate-spin text-sky-400 mb-2" />
                    Loading orders...
                  </td>
                </tr>
              ) : orders.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-500">
                    No orders found matching the filter criteria.
                  </td>
                </tr>
              ) : (
                orders.map((o) => {
                  const latestPayment = o.payments?.[0];
                  const latestShipment = o.shipments?.[0];
                  return (
                    <tr key={o.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-4 py-3 font-mono font-semibold text-sky-400">
                        <Link href={`/orders/${o.id}`} className="hover:underline">
                          {o.order_number}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                        {new Date(o.created_at).toLocaleDateString("en-IN", {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-200">
                          {o.customer_name || "Customer"}
                        </div>
                        <div className="text-[10px] text-slate-500 truncate max-w-[150px]">
                          {o.customer_email || o.customer_id}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-slate-400">
                        {o.items?.length || 0} SKU{o.items?.length !== 1 ? "s" : ""}
                      </td>
                      <td className="px-4 py-3 font-semibold text-white">
                        {formatInr(o.total_amount)}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-semibold ${getStatusBadge(
                            o.status
                          )}`}
                        >
                          {o.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {latestPayment ? (
                          <div className="flex items-center gap-1.5">
                            <span className="text-[10px] font-mono uppercase text-slate-400">
                              {latestPayment.payment_method}
                            </span>
                            <span
                              className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${
                                latestPayment.status === "SUCCESSFUL"
                                  ? "bg-emerald-500/20 text-emerald-400"
                                  : latestPayment.status === "FAILED"
                                  ? "bg-rose-500/20 text-rose-400"
                                  : "bg-amber-500/20 text-amber-400"
                              }`}
                            >
                              {latestPayment.status}
                            </span>
                          </div>
                        ) : (
                          <span className="text-slate-500">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {latestShipment ? (
                          <div>
                            <div className="text-slate-300 font-medium">{latestShipment.carrier}</div>
                            <div className="text-[10px] font-mono text-slate-500">
                              {latestShipment.tracking_number}
                            </div>
                          </div>
                        ) : (
                          <span className="text-slate-500 text-[11px]">Unassigned</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Link
                          href={`/orders/${o.id}`}
                          className="inline-flex items-center gap-1 rounded bg-slate-800 px-2 py-1 text-[11px] font-medium text-slate-300 hover:bg-sky-600 hover:text-white transition-colors"
                        >
                          <span>Inspect</span>
                          <ExternalLink className="h-3 w-3" />
                        </Link>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        <div className="flex items-center justify-between border-t border-slate-800 bg-slate-900/60 px-4 py-3 text-xs text-slate-400">
          <div>
            Showing <span className="font-semibold text-white">{orders.length}</span> of{" "}
            <span className="font-semibold text-white">{total}</span> total records
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0 || loading}
              className="flex items-center gap-1 rounded border border-slate-800 bg-slate-900 px-2.5 py-1 text-slate-300 hover:bg-slate-800 disabled:opacity-40"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Previous</span>
            </button>
            <span className="font-mono text-xs">
              Page {page + 1} of {Math.max(1, Math.ceil(total / pageSize))}
            </span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={(page + 1) * pageSize >= total || loading}
              className="flex items-center gap-1 rounded border border-slate-800 bg-slate-900 px-2.5 py-1 text-slate-300 hover:bg-slate-800 disabled:opacity-40"
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

