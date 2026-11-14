"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  CreditCard,
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  CheckCircle2,
  ExternalLink,
  ShieldAlert,
} from "lucide-react";
import { fetchJson, API_BASE_URL } from "@/lib/api";

interface PaymentItem {
  id: string;
  order_id: string;
  amount: number;
  currency: string;
  payment_method: string;
  payment_reference: string;
  status: string;
  error_code?: string;
  error_message?: string;
  paid_at?: string;
  created_at: string;
}

interface PaymentListResponse {
  total: number;
  limit: number;
  offset: number;
  items: PaymentItem[];
  payments?: PaymentItem[];
}

const STATUS_FILTERS = ["ALL", "SUCCESSFUL", "PENDING", "FAILED", "REFUNDED"];

const statusConfig: Record<string, { label: string; dot: string; badge: string }> = {
  SUCCESSFUL: {
    label: "Successful",
    dot: "bg-emerald-400",
    badge: "border-emerald-500/20 bg-emerald-500/10 text-emerald-300",
  },
  PENDING: {
    label: "Pending",
    dot: "bg-amber-400",
    badge: "border-amber-500/20 bg-amber-500/10 text-amber-300",
  },
  FAILED: {
    label: "Failed",
    dot: "bg-rose-400",
    badge: "border-rose-500/20 bg-rose-500/10 text-rose-300",
  },
  REFUNDED: {
    label: "Refunded",
    dot: "bg-purple-400",
    badge: "border-purple-500/20 bg-purple-500/10 text-purple-300",
  },
};

export default function PaymentsPage() {
  const [payments, setPayments] = useState<PaymentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedStatus, setSelectedStatus] = useState("ALL");
  const [searchTerm, setSearchTerm] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 15;

  // Refund modal state
  const [activeRefundPayment, setActiveRefundPayment] = useState<PaymentItem | null>(null);
  const [refundReason, setRefundReason] = useState("");
  const [refundAmount, setRefundAmount] = useState("");
  const [refunding, setRefunding] = useState(false);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const loadPayments = useCallback(async () => {
    try {
      setLoading(true);
      let query = `/payments?limit=${pageSize}&offset=${page * pageSize}`;
      if (selectedStatus !== "ALL") {
        query += `&status=${selectedStatus}`;
      }
      if (searchTerm.trim()) {
        query += `&search=${encodeURIComponent(searchTerm.trim())}`;
      }

      const res = await fetchJson<PaymentListResponse>(query);
      setPayments(res.items || res.payments || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      console.error("Failed to load payment ledger:", err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, selectedStatus, searchTerm]);

  useEffect(() => {
    loadPayments();
  }, [loadPayments]);

  const handleRefundSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeRefundPayment) return;
    try {
      setRefunding(true);
      const res = await fetch(
        `${API_BASE_URL}/payments/${activeRefundPayment.id}/refund`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            amount: refundAmount ? parseFloat(refundAmount) : undefined,
            reason: refundReason || "Customer return verified",
          }),
        }
      );
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Refund processing failed");
      }
      setActionSuccess(
        `Refund successfully initiated for transaction ${activeRefundPayment.payment_reference}.`
      );
      setActiveRefundPayment(null);
      loadPayments();
    } catch (err: any) {
      alert(`Refund error: ${err.message}`);
    } finally {
      setRefunding(false);
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
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <CreditCard className="h-5 w-5 text-zinc-400" />
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">Payments &amp; Ledger</h1>
            <span className="text-xs font-mono text-zinc-500 tabular-nums">({total})</span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Settlement records, gateway response codes, authorization logs, and policy-governed refund queues.
          </p>
        </div>

        <button
          onClick={loadPayments}
          disabled={loading}
          className="self-start sm:self-auto inline-flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-[#0c0d14] px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-zinc-400" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {actionSuccess && (
        <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/10 p-3.5 text-xs text-emerald-300 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Status Tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 scrollbar-none">
          {STATUS_FILTERS.map((st) => {
            const isSelected = selectedStatus === st;
            return (
              <button
                key={st}
                onClick={() => {
                  setSelectedStatus(st);
                  setPage(0);
                }}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors shrink-0 ${
                  isSelected
                    ? "bg-white/[0.12] text-zinc-100 border border-white/[0.16]"
                    : "border border-white/[0.06] bg-[#0c0d14] text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60"
                }`}
              >
                {st}
              </button>
            );
          })}
        </div>

        {/* Search */}
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search reference, order ID..."
            className="w-full rounded-md border border-white/[0.08] bg-[#0c0d14] pl-9 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-400 focus:border-zinc-500 focus:outline-none transition-colors"
          />
        </div>
      </div>

      {/* Payment Ledger Table */}
      <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-white/[0.06] bg-[#0a0b10] text-[11px] font-medium text-zinc-400 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3">Reference</th>
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3">Linked Order</th>
                <th className="px-4 py-3">Method</th>
                <th className="px-4 py-3">Amount</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Diagnostic</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.06] text-zinc-300">
              {loading && payments.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-zinc-500 font-mono text-xs">
                    <RefreshCw className="mx-auto h-5 w-5 animate-spin text-zinc-600 mb-2" />
                    Querying payment ledger...
                  </td>
                </tr>
              ) : payments.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-zinc-500 text-xs">
                    No payment transactions located for this filter.
                  </td>
                </tr>
              ) : (
                payments.map((p) => {
                  const style = statusConfig[p.status] || {
                    label: p.status,
                    dot: "bg-zinc-400",
                    badge: "border-zinc-700 bg-zinc-800 text-zinc-300",
                  };

                  return (
                    <tr key={p.id} className="hover:bg-white/[0.02] transition-colors">
                      <td className="px-4 py-3 font-mono font-medium text-zinc-200">
                        {p.payment_reference}
                      </td>
                      <td className="px-4 py-3 text-zinc-400 whitespace-nowrap text-[11px] font-mono">
                        {new Date(p.created_at).toLocaleDateString("en-IN", {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                      <td className="px-4 py-3 font-mono text-[11px]">
                        <Link
                          href={`/orders/${p.order_id}`}
                          className="text-zinc-300 hover:text-white inline-flex items-center gap-1 hover:underline underline-offset-2 transition-colors"
                        >
                          <span>#{p.order_id.slice(0, 8)}</span>
                          <ExternalLink className="h-3 w-3 text-zinc-500" />
                        </Link>
                      </td>
                      <td className="px-4 py-3 font-mono uppercase text-[11px] text-zinc-400">
                        {p.payment_method}
                      </td>
                      <td className="px-4 py-3 font-mono font-semibold text-zinc-100 tabular-nums">
                        {formatInr(p.amount)}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-medium ${style.badge}`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
                          {style.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-zinc-400 text-[11px]">
                        {p.error_code ? (
                          <div className="text-rose-400">
                            <span className="font-mono font-semibold">{p.error_code}</span>:{" "}
                            <span className="text-rose-300/80">{p.error_message}</span>
                          </div>
                        ) : p.status === "SUCCESSFUL" ? (
                          <span className="text-zinc-400">Gateway Authorised</span>
                        ) : (
                          <span className="text-zinc-600">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {p.status === "SUCCESSFUL" && (
                          <button
                            onClick={() => {
                              setActiveRefundPayment(p);
                              setRefundAmount(p.amount.toString());
                              setRefundReason("Customer return authorization");
                            }}
                            className="inline-flex items-center gap-1 rounded border border-purple-500/25 bg-purple-500/10 px-2 py-1 text-[11px] font-medium text-purple-300 hover:bg-purple-500/20 transition-colors"
                          >
                            <RotateCcw className="h-3 w-3" />
                            <span>Refund</span>
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between border-t border-white/[0.06] bg-[#0a0b10] px-4 py-3 text-xs text-zinc-400">
          <div>
            Showing <span className="font-mono text-zinc-200 tabular-nums">{payments.length}</span> of{" "}
            <span className="font-mono text-zinc-200 tabular-nums">{total}</span> transactions
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0 || loading}
              className="inline-flex items-center gap-1 rounded border border-white/[0.08] bg-[#0c0d14] px-2.5 py-1 text-zinc-300 hover:bg-zinc-800 disabled:opacity-40 transition-colors"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Previous</span>
            </button>
            <span className="font-mono text-xs text-zinc-500 px-1">
              Page {page + 1} of {Math.max(1, Math.ceil(total / pageSize))}
            </span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={(page + 1) * pageSize >= total || loading}
              className="inline-flex items-center gap-1 rounded border border-white/[0.08] bg-[#0c0d14] px-2.5 py-1 text-zinc-300 hover:bg-zinc-800 disabled:opacity-40 transition-colors"
            >
              <span>Next</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Refund Modal */}
      {activeRefundPayment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <form
            onSubmit={handleRefundSubmit}
            className="w-full max-w-md rounded-xl border border-white/[0.12] bg-[#0c0d14] p-6 space-y-4 shadow-2xl"
          >
            <div className="flex items-center gap-2.5 text-purple-300">
              <RotateCcw className="h-5 w-5" />
              <h3 className="text-sm font-semibold text-zinc-100">Process Refund: {activeRefundPayment.payment_reference}</h3>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Submit a policy-governed refund request. Requests above policy threshold will require supervisor intervention through the Human Approval Queue.
            </p>

            <div>
              <label className="block text-[11px] font-medium text-zinc-400 uppercase tracking-wider mb-1.5">
                Refund Amount (INR)
              </label>
              <input
                type="number"
                step="0.01"
                max={activeRefundPayment.amount}
                value={refundAmount}
                onChange={(e) => setRefundAmount(e.target.value)}
                className="w-full rounded-lg border border-white/[0.08] bg-[#090a0f] p-2.5 text-xs font-mono text-zinc-200 placeholder-zinc-600 focus:border-zinc-500 focus:outline-none transition-colors"
                required
              />
              <span className="text-[10px] text-zinc-500 font-mono mt-1 block">
                Max capturable: {formatInr(activeRefundPayment.amount)}
              </span>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-zinc-400 uppercase tracking-wider mb-1.5">
                Justification &amp; Policy Reason
              </label>
              <textarea
                value={refundReason}
                onChange={(e) => setRefundReason(e.target.value)}
                rows={3}
                placeholder="Reason for refund (return, damage, customer courtesy)..."
                className="w-full rounded-lg border border-white/[0.08] bg-[#090a0f] p-2.5 text-xs text-zinc-200 placeholder-zinc-600 focus:border-zinc-500 focus:outline-none transition-colors"
                required
              />
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-white/[0.06]">
              <button
                type="button"
                onClick={() => setActiveRefundPayment(null)}
                className="rounded-md px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
              >
                Dismiss
              </button>
              <button
                type="submit"
                disabled={refunding}
                className="rounded-md bg-purple-500/20 border border-purple-500/30 px-3.5 py-1.5 text-xs font-medium text-purple-300 hover:bg-purple-500/30 transition-colors disabled:opacity-40"
              >
                {refunding ? "Authorizing..." : "Submit Refund"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
