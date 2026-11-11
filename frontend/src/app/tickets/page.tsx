"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  LifeBuoy,
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  CheckCircle2,
  Clock,
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

export default function TicketsPage() {
  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedStatus, setSelectedStatus] = useState("ALL");
  const [selectedPriority, setSelectedPriority] = useState("ALL");
  const [searchTerm, setSearchTerm] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 15;
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const loadTickets = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
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
      setError(err.message || "Failed to load support tickets");
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
      setActionSuccess(`Ticket updated to ${newStatus}.`);
      loadTickets();
    } catch (err: any) {
      alert(`Error updating ticket status: ${err.message}`);
    }
  };

  const getPriorityBadge = (p: string) => {
    switch (p) {
      case "URGENT":
        return "bg-rose-500/20 text-rose-400 border-rose-500/40";
      case "HIGH":
        return "bg-amber-500/20 text-amber-400 border-amber-500/40";
      case "MEDIUM":
        return "bg-sky-500/20 text-sky-400 border-sky-500/40";
      default:
        return "bg-slate-800 text-slate-400 border-slate-700";
    }
  };

  const getStatusBadge = (s: string) => {
    switch (s) {
      case "RESOLVED":
      case "CLOSED":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
      case "IN_PROGRESS":
        return "bg-sky-500/10 text-sky-400 border-sky-500/20";
      case "OPEN":
        return "bg-amber-500/10 text-amber-400 border-amber-500/20";
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
            <LifeBuoy className="h-6 w-6 text-sky-400" />
            Support Ticket Queue
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Customer inquiries, return requests, escalations, priority triage, and resolution SLA tracking.
          </p>
        </div>

        <button
          onClick={loadTickets}
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

      {/* Filters and Search */}
      <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4">
        {/* Status Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 lg:pb-0 scrollbar-thin">
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => {
                setSelectedStatus(s);
                setPage(0);
              }}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors shrink-0 ${
                selectedStatus === s
                  ? "bg-sky-500 text-white font-semibold"
                  : "bg-slate-900 text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Priority Filter */}
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-500 uppercase font-semibold">Priority:</span>
          {PRIORITY_FILTERS.map((p) => (
            <button
              key={p}
              onClick={() => {
                setSelectedPriority(p);
                setPage(0);
              }}
              className={`rounded px-2 py-1 text-[11px] font-semibold transition-colors ${
                selectedPriority === p
                  ? "bg-slate-700 text-white"
                  : "bg-slate-900 text-slate-500 hover:text-slate-300"
              }`}
            >
              {p}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative w-full lg:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search ticket #, subject..."
            className="w-full rounded-lg border border-slate-800 bg-slate-900/80 pl-9 pr-4 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Tickets Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden shadow">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 bg-slate-900/80 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-4 py-3">Ticket #</th>
                <th className="px-4 py-3">Priority</th>
                <th className="px-4 py-3">Subject / Issue</th>
                <th className="px-4 py-3">Customer ID</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {loading && tickets.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    <RefreshCw className="mx-auto h-6 w-6 animate-spin text-sky-400 mb-2" />
                    Loading support tickets...
                  </td>
                </tr>
              ) : tickets.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    No tickets found matching criteria.
                  </td>
                </tr>
              ) : (
                tickets.map((t) => {
                  const isSlaBreach =
                    (t.priority === "HIGH" || t.priority === "URGENT") &&
                    (t.status === "OPEN" || t.status === "IN_PROGRESS") &&
                    Date.now() - new Date(t.created_at).getTime() > 48 * 3600 * 1000;

                  return (
                    <tr key={t.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-4 py-3 font-mono font-semibold text-sky-400">
                        {t.ticket_number}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`rounded border px-2 py-0.5 text-[10px] font-bold ${getPriorityBadge(
                            t.priority
                          )}`}
                        >
                          {t.priority}
                        </span>
                      </td>
                      <td className="px-4 py-3 max-w-md">
                        <div className="font-semibold text-slate-100 flex items-center gap-1.5">
                          <span>{t.title}</span>
                          {isSlaBreach && (
                            <span className="rounded bg-rose-500/20 text-rose-400 border border-rose-500/30 px-1.5 py-0.2 text-[9px] font-bold">
                              SLA BREACH
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-slate-400 truncate mt-0.5">{t.description}</p>
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-400">
                        <Link href={`/customers/${t.customer_id}`} className="hover:underline text-sky-400">
                          {t.customer_id.slice(0, 8)}...
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                        {new Date(t.created_at).toLocaleDateString("en-IN", {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-semibold ${getStatusBadge(
                            t.status
                          )}`}
                        >
                          {t.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {t.status !== "RESOLVED" && t.status !== "CLOSED" ? (
                          <button
                            onClick={() => handleUpdateStatus(t.id, "RESOLVED")}
                            className="inline-flex items-center gap-1 rounded bg-slate-800 px-2.5 py-1 text-[11px] font-medium text-emerald-400 hover:bg-emerald-950/60 border border-emerald-900/40 transition-colors"
                          >
                            <CheckCircle2 className="h-3 w-3" />
                            <span>Resolve</span>
                          </button>
                        ) : (
                          <span className="text-[11px] text-slate-500">Resolved</span>
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
        <div className="flex items-center justify-between border-t border-slate-800 bg-slate-900/60 px-4 py-3 text-xs text-slate-400">
          <div>
            Showing <span className="font-semibold text-white">{tickets.length}</span> of{" "}
            <span className="font-semibold text-white">{total}</span> tickets
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

