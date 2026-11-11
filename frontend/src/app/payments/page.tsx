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
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
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
const METHOD_FILTERS = ["ALL", "UPI", "CARD", "NET_BANKING", "COD", "WALLET"];

export default function PaymentsPage() {
  const [payments, setPayments] = useState<PaymentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedStatus, setSelectedStatus] = useState("ALL");
  const [selectedMethod, setSelectedMethod] = useState("ALL");
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
      setError(null);
      let query = `/payments?limit=${pageSize}&offset=${page * pageSize}`;
      if (selectedStatus !== "ALL") {
        query += `&status=${selectedStatus}`;
      }
      if (selectedMethod !== "ALL") {
        query += `&payment_method=${selectedMethod}`;
      }
      if (searchTerm.trim()) {
        query += `&search=${encodeURIComponent(searchTerm.trim())}`;
      }

      const res = await fetchJson<PaymentListResponse>(query);
      setPayments(res.items || res.payments || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      setError(err.message || "Failed to load payment ledger");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, selectedStatus, selectedMethod, searchTerm]);

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
        `Refund successfully processed for payment ${activeRefundPayment.payment_reference}.`
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
    }).format(val);
  };

  const getStatusBadge = (st: string) => {
    switch (st) {
      case "SUCCESSFUL":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
      case "PENDING":
        return "bg-amber-500/10 text-amber-400 border-amber-500/20";
      case "FAILED":
        return "bg-rose-500/10 text-rose-400 border-rose-500/20";
      case "REFUNDED":
        return "bg-purple-500/10 text-purple-400 border-purple-500/20";
      default:
        return "bg-slate-800 text-slate-300 border-slate-700";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <CreditCard className="h-6 w-6 text-sky-400" />
            Payments &amp; Settlement Ledger
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Audit-logged payment transactions, gateway authorizations, failures, and policy refunds.
          </p>
        </div>

        <button
          onClick={loadPayments}
          disabled={loading}
          className="self-start sm:self-auto flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-800 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-sky-400" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {actionSuccess && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/20 p-3 text-xs text-emerald-400 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* Filter Bar */}
      <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4">
        {/* Status filters */}
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

        {/* Search */}
        <div className="relative w-full lg:w-80">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search reference, order ID..."
            className="w-full rounded-lg border border-slate-800 bg-slate-900/80 pl-9 pr-4 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden shadow">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 bg-slate-900/80 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-4 py-3">Reference</th>
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3">Order Link</th>
                <th className="px-4 py-3">Method</th>
                <th className="px-4 py-3">Amount</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Gateway Diagnostic</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {loading && payments.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500">
                    <RefreshCw className="mx-auto h-6 w-6 animate-spin text-sky-400 mb-2" />
                    Loading payments...
                  </td>
                </tr>
              ) : payments.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500">
                    No payment records found.
                  </td>
                </tr>
              ) : (
                payments.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="px-4 py-3 font-mono font-semibold text-slate-200">
                      {p.payment_reference}
                    </td>
                    <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                      {new Date(p.created_at).toLocaleDateString("en-IN", {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="px-4 py-3 font-mono text-sky-400">
                      <Link href={`/orders/${p.order_id}`} className="hover:underline">
                        Order #{p.order_id.slice(0, 8)}...
                      </Link>
                    </td>
                    <td className="px-4 py-3 font-mono uppercase text-slate-300">
                      {p.payment_method}
                    </td>
                    <td className="px-4 py-3 font-semibold text-white">
                      {formatInr(p.amount)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-semibold ${getStatusBadge(
                          p.status
                        )}`}
                      >
                        {p.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-400">
                      {p.error_code ? (
                        <div className="text-rose-400">
                          <span className="font-mono font-semibold">{p.error_code}</span>:{" "}
                          <span className="text-[11px] text-rose-300">{p.error_message}</span>
                        </div>
                      ) : p.status === "SUCCESSFUL" ? (
                        <span className="text-emerald-400 text-[11px]">Capture Verified</span>
                      ) : (
                        <span className="text-slate-500 text-[11px]">N/A</span>
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
                          className="inline-flex items-center gap-1 rounded bg-slate-800 px-2 py-1 text-[11px] font-medium text-purple-300 hover:bg-purple-950/60 hover:text-purple-200 border border-purple-900/40 transition-colors"
                        >
                          <RotateCcw className="h-3 w-3" />
                          <span>Refund</span>
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between border-t border-slate-800 bg-slate-900/60 px-4 py-3 text-xs text-slate-400">
          <div>
            Showing <span className="font-semibold text-white">{payments.length}</span> of{" "}
            <span className="font-semibold text-white">{total}</span> transactions
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

      {/* Refund Modal */}
      {activeRefundPayment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <form
            onSubmit={handleRefundSubmit}
            className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900 p-6 space-y-4"
          >
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <RotateCcw className="h-4 w-4 text-purple-400" />
              Process Refund: {activeRefundPayment.payment_reference}
            </h3>
            <p className="text-xs text-slate-400">
              Submit a policy-governed refund request. Requests above policy threshold will trigger
              the Human Approval Queue.
            </p>

            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Refund Amount (INR)
              </label>
              <input
                type="number"
                step="0.01"
                max={activeRefundPayment.amount}
                value={refundAmount}
                onChange={(e) => setRefundAmount(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 p-2 text-xs text-white focus:border-sky-500 focus:outline-none"
                required
              />
              <span className="text-[10px] text-slate-500">
                Max capturable: {formatInr(activeRefundPayment.amount)}
              </span>
            </div>

            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Justification / Reason
              </label>
              <textarea
                value={refundReason}
                onChange={(e) => setRefundReason(e.target.value)}
                rows={3}
                placeholder="Reason for refund (return, damage, customer courtesy)..."
                className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 p-2 text-xs text-white focus:border-sky-500 focus:outline-none"
                required
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setActiveRefundPayment(null)}
                className="rounded-lg px-3 py-1.5 text-xs text-slate-400 hover:text-white"
              >
                Dismiss
              </button>
              <button
                type="submit"
                disabled={refunding}
                className="rounded-lg bg-purple-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-purple-500 disabled:opacity-50"
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

