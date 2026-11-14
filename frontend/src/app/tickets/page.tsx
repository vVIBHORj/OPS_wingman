"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  LifeBuoy,
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { fetchJson, API_BASE_URL } from "@/lib/api";

interface TicketItem {
  id: string;
  ticket_number: string;
  customer_id: string;
  order_id?: string;
  title: string;
  description: string;
  priority: string;
  status: string;
  assigned_to?: string;
  created_at: string;
  updated_at: string;
  resolved_at?: string;
}

interface TicketListResponse {
  total: number;
  limit: number;
  offset: number;
  items: TicketItem[];
  tickets?: TicketItem[];
}

const STATUS_FILTERS = ["ALL", "OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"];
const PRIORITY_FILTERS = ["ALL", "LOW", "MEDIUM", "HIGH", "URGENT"];

const priorityStyles: Record<string, string> = {
  URGENT: "border-rose-500/25 bg-rose-500/10 text-rose-300",
  HIGH: "border-amber-500/25 bg-amber-500/10 text-amber-300",
  MEDIUM: "border-sky-500/25 bg-sky-500/10 text-sky-300",
  LOW: "border-zinc-700 bg-zinc-800 text-zinc-300",
};

const statusConfig: Record<string, { label: string; dot: string; badge: string }> = {
  OPEN: {
    label: "Open",
    dot: "bg-amber-400",
    badge: "border-amber-500/20 bg-amber-500/10 text-amber-300",
  },
  IN_PROGRESS: {
    label: "In Progress",
    dot: "bg-sky-400",
    badge: "border-sky-500/20 bg-sky-500/10 text-sky-300",
  },
  RESOLVED: {
    label: "Resolved",
    dot: "bg-emerald-400",
    badge: "border-emerald-500/20 bg-emerald-500/10 text-emerald-300",
  },
  CLOSED: {
    label: "Closed",
    dot: "bg-zinc-400",
    badge: "border-zinc-700 bg-zinc-800 text-zinc-300",
  },
};

export default function TicketsPage() {
  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedStatus, setSelectedStatus] = useState("ALL");
  const [selectedPriority, setSelectedPriority] = useState("ALL");
  const [searchTerm, setSearchTerm] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 15;
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const loadTickets = useCallback(async () => {
    try {
      setLoading(true);
      let query = `/tickets?limit=${pageSize}&offset=${page * pageSize}`;
      if (selectedStatus !== "ALL") {
        query += `&status=${selectedStatus}`;
      }
      if (selectedPriority !== "ALL") {
        query += `&priority=${selectedPriority}`;
      }
      if (searchTerm.trim()) {
        query += `&search=${encodeURIComponent(searchTerm.trim())}`;
      }

      const res = await fetchJson<TicketListResponse>(query);
      setTickets(res.items || res.tickets || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      console.error("Failed to load tickets:", err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, selectedStatus, selectedPriority, searchTerm]);

  useEffect(() => {
    loadTickets();
  }, [loadTickets]);

  const handleUpdateStatus = async (ticketId: string, newStatus: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/tickets/${ticketId}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Status update failed");
      }
      setActionSuccess(`Ticket state updated to ${newStatus}.`);
      loadTickets();
    } catch (err: any) {
      alert(`Error updating ticket status: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <LifeBuoy className="h-5 w-5 text-zinc-400" />
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">Support &amp; Inquiries</h1>
            <span className="text-xs font-mono text-zinc-500 tabular-nums">({total})</span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Customer inquiries, escalation dispatch, priority triage, and resolution SLA tracking.
          </p>
        </div>

        <button
          onClick={loadTickets}
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

      {/* Filter and Priority Bar */}
      <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3">
        {/* Status Tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 lg:pb-0 scrollbar-none">
          {STATUS_FILTERS.map((s) => {
            const isSelected = selectedStatus === s;
            return (
              <button
                key={s}
                onClick={() => {
                  setSelectedStatus(s);
                  setPage(0);
                }}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors shrink-0 ${
                  isSelected
                    ? "bg-white/[0.12] text-zinc-100 border border-white/[0.16]"
                    : "border border-white/[0.06] bg-[#0c0d14] text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60"
                }`}
              >
                {s}
              </button>
            );
          })}
        </div>

        {/* Priority Filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-zinc-400 uppercase tracking-wider mr-1">Priority:</span>
          {PRIORITY_FILTERS.map((p) => {
            const isSelected = selectedPriority === p;
            return (
              <button
                key={p}
                onClick={() => {
                  setSelectedPriority(p);
                  setPage(0);
                }}
                className={`rounded px-2 py-0.5 text-[11px] font-mono transition-colors ${
                  isSelected
                    ? "bg-white/[0.12] text-zinc-100 border border-white/[0.16]"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {p}
              </button>
            );
          })}
        </div>

        {/* Search */}
        <div className="relative w-full lg:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search ticket #, subject..."
            className="w-full rounded-md border border-white/[0.08] bg-[#0c0d14] pl-9 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-400 focus:border-zinc-500 focus:outline-none transition-colors"
          />
        </div>
      </div>

      {/* Ticket Queue Table */}
      <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-white/[0.06] bg-[#0a0b10] text-[11px] font-medium text-zinc-400 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3">Ticket</th>
                <th className="px-4 py-3">Priority</th>
                <th className="px-4 py-3">Subject / Details</th>
                <th className="px-4 py-3">Customer ID</th>
                <th className="px-4 py-3">Reported</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.06] text-zinc-300">
              {loading && tickets.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-zinc-500 font-mono text-xs">
                    <RefreshCw className="mx-auto h-5 w-5 animate-spin text-zinc-600 mb-2" />
                    Querying ticket queue...
                  </td>
                </tr>
              ) : tickets.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-zinc-500 text-xs">
                    No tickets found matching the selected filters.
                  </td>
                </tr>
              ) : (
                tickets.map((t) => {
                  const isSlaBreach =
                    (t.priority === "HIGH" || t.priority === "URGENT") &&
                    (t.status === "OPEN" || t.status === "IN_PROGRESS") &&
                    Date.now() - new Date(t.created_at).getTime() > 48 * 3600 * 1000;

                  const pStyle = priorityStyles[t.priority] || "border-zinc-700 bg-zinc-800 text-zinc-300";
                  const sStyle = statusConfig[t.status] || {
                    label: t.status,
                    dot: "bg-zinc-400",
                    badge: "border-zinc-700 bg-zinc-800 text-zinc-300",
                  };

                  return (
                    <tr key={t.id} className="hover:bg-white/[0.02] transition-colors">
                      <td className="px-4 py-3 font-mono font-medium text-zinc-200">
                        {t.ticket_number}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-block rounded border px-2 py-0.5 text-[10px] font-mono uppercase ${pStyle}`}>
                          {t.priority}
                        </span>
                      </td>
                      <td className="px-4 py-3 max-w-md">
                        <div className="font-medium text-zinc-100 flex items-center gap-2">
                          <span className="truncate">{t.title}</span>
                          {isSlaBreach && (
                            <span className="inline-flex items-center gap-1 rounded border border-rose-500/30 bg-rose-500/15 px-1.5 py-0.2 text-[9px] font-mono text-rose-300 uppercase shrink-0">
                              <AlertTriangle className="h-2.5 w-2.5" /> SLA Breach
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-zinc-400 truncate mt-0.5">{t.description}</p>
                      </td>
                      <td className="px-4 py-3 font-mono text-[11px]">
                        <Link
                          href={`/customers/${t.customer_id}`}
                          className="text-zinc-400 hover:text-white underline underline-offset-2 transition-colors"
                        >
                          {t.customer_id.slice(0, 8)}...
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-zinc-400 whitespace-nowrap text-[11px] font-mono">
                        {new Date(t.created_at).toLocaleDateString("en-IN", {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-medium ${sStyle.badge}`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${sStyle.dot}`} />
                          {sStyle.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {t.status !== "RESOLVED" && t.status !== "CLOSED" ? (
                          <button
                            onClick={() => handleUpdateStatus(t.id, "RESOLVED")}
                            className="inline-flex items-center gap-1 rounded border border-emerald-500/25 bg-emerald-500/10 px-2 py-1 text-[11px] font-medium text-emerald-300 hover:bg-emerald-500/20 transition-colors"
                          >
                            <CheckCircle2 className="h-3 w-3" />
                            <span>Resolve</span>
                          </button>
                        ) : (
                          <span className="text-[11px] font-mono text-zinc-500">Resolved</span>
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
            Showing <span className="font-mono text-zinc-200 tabular-nums">{tickets.length}</span> of{" "}
            <span className="font-mono text-zinc-200 tabular-nums">{total}</span> tickets
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
    </div>
  );
}
