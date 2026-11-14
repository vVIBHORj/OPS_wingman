"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  History,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  FileCode,
  X,
  Search,
} from "lucide-react";
import { fetchJson } from "@/lib/api";

interface AuditEventItem {
  id: string | number;
  event_id?: string;
  event_type: string;
  actor: string;
  actor_id?: string;
  entity_type: string;
  entity_id: string;
  action?: string;
  operation?: string;
  payload?: Record<string, any>;
  tool_arguments?: Record<string, any>;
  tool_result_summary?: Record<string, any>;
  metadata_provenance?: Record<string, any>;
  created_at?: string;
  timestamp?: string;
}

type AuditApiResponse =
  | AuditEventItem[]
  | {
      total?: number;
      limit?: number;
      offset?: number;
      events?: AuditEventItem[];
      items?: AuditEventItem[];
    };

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [eventTypeFilter, setEventTypeFilter] = useState("");
  const [actorFilter, setActorFilter] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 20;

  const [inspectEvent, setInspectEvent] = useState<AuditEventItem | null>(null);

  const loadEvents = useCallback(async () => {
    try {
      setLoading(true);
      let query = `/audit/events?limit=${pageSize}&offset=${page * pageSize}`;
      if (eventTypeFilter.trim()) {
        query += `&event_type=${encodeURIComponent(eventTypeFilter.trim())}`;
      }
      if (actorFilter.trim()) {
        query += `&actor=${encodeURIComponent(actorFilter.trim())}`;
      }

      const res = await fetchJson<AuditApiResponse>(query);
      let list: AuditEventItem[] = [];
      if (Array.isArray(res)) {
        list = res;
        setTotal(res.length >= pageSize ? (page + 2) * pageSize : page * pageSize + res.length);
      } else if (res && Array.isArray(res.events)) {
        list = res.events;
        setTotal(res.total ?? res.events.length);
      } else if (res && Array.isArray(res.items)) {
        list = res.items;
        setTotal(res.total ?? res.items.length);
      }
      setEvents(list);
    } catch (err: any) {
      console.error("Failed to load audit events:", err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, eventTypeFilter, actorFilter]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <History className="h-5 w-5 text-zinc-400" />
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">Audit &amp; Compliance Trail</h1>
            <span className="text-xs font-mono text-zinc-500 tabular-nums">({total})</span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Immutable, cryptographically verifiable log of all automated agents, human approvals, and policy-driven mutations.
          </p>
        </div>

        <button
          onClick={loadEvents}
          disabled={loading}
          className="self-start sm:self-auto inline-flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-[#0c0d14] px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-zinc-400" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-500" />
          <input
            type="text"
            value={eventTypeFilter}
            onChange={(e) => {
              setEventTypeFilter(e.target.value);
              setPage(0);
            }}
            placeholder="Filter by event type (e.g. ORDER_PLACED, REFUND_REQUESTED)..."
            className="w-full rounded-md border border-white/[0.08] bg-[#0c0d14] pl-9 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 focus:border-zinc-500 focus:outline-none transition-colors"
          />
        </div>

        <div className="relative w-full sm:w-64">
          <input
            type="text"
            value={actorFilter}
            onChange={(e) => {
              setActorFilter(e.target.value);
              setPage(0);
            }}
            placeholder="Filter by actor (e.g. system, agent)..."
            className="w-full rounded-md border border-white/[0.08] bg-[#0c0d14] px-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 focus:border-zinc-500 focus:outline-none transition-colors"
          />
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-white/[0.06] bg-[#0a0b10] text-[11px] font-medium text-zinc-400 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3">Event Type</th>
                <th className="px-4 py-3">Actor</th>
                <th className="px-4 py-3">Target Entity</th>
                <th className="px-4 py-3">Action / Operation</th>
                <th className="px-4 py-3 text-right">Payload</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.06] text-zinc-300">
              {loading && events.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-zinc-500 font-mono text-xs">
                    <RefreshCw className="mx-auto h-5 w-5 animate-spin text-zinc-600 mb-2" />
                    Querying immutable audit chain...
                  </td>
                </tr>
              ) : events.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-zinc-500 text-xs">
                    No audit records match the filter query.
                  </td>
                </tr>
              ) : (
                events.map((ev) => (
                  <tr key={String(ev.id || ev.event_id)} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-3 text-zinc-400 whitespace-nowrap font-mono text-[11px]">
                      {new Date(ev.created_at || ev.timestamp || Date.now()).toLocaleString("en-IN")}
                    </td>
                    <td className="px-4 py-3 font-mono font-medium text-zinc-100">
                      {ev.event_type}
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded border border-white/[0.06] bg-white/[0.02] px-2 py-0.5 text-[10px] font-mono text-zinc-400 uppercase">
                        {ev.actor}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-zinc-300 text-[11px]">
                      <span className="text-zinc-500">{ev.entity_type}</span> ({String(ev.entity_id || "").slice(0, 8)}...)
                    </td>
                    <td className="px-4 py-3 text-zinc-300 font-mono text-[11px]">
                      {ev.action || ev.operation || "SYSTEM"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => setInspectEvent(ev)}
                        className="inline-flex items-center gap-1 rounded border border-white/[0.08] bg-[#090a0f] px-2.5 py-1 text-[11px] font-medium text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors"
                      >
                        <FileCode className="h-3 w-3 text-zinc-500" />
                        <span>Payload</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between border-t border-white/[0.06] bg-[#0a0b10] px-4 py-3 text-xs text-zinc-400">
          <div>
            Showing <span className="font-mono text-zinc-200 tabular-nums">{events.length}</span> of{" "}
            <span className="font-mono text-zinc-200 tabular-nums">{total}</span> entries
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

      {/* Payload Modal */}
      {inspectEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-xl rounded-xl border border-white/[0.12] bg-[#0c0d14] p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
              <div>
                <h3 className="text-xs font-semibold text-zinc-100 font-mono">{inspectEvent.event_type}</h3>
                <p className="text-[10px] text-zinc-500 font-mono mt-0.5">ID: {String(inspectEvent.id)}</p>
              </div>
              <button
                onClick={() => setInspectEvent(null)}
                className="rounded-md p-1 text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.06] transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div>
              <div className="text-[10px] font-medium uppercase tracking-wider text-zinc-500 mb-1.5 font-mono">
                Cryptographic Sanitized Payload
              </div>
              <pre className="max-h-72 overflow-y-auto rounded-lg border border-white/[0.06] bg-[#08090d] p-3 text-[11px] font-mono text-zinc-300 leading-relaxed scrollbar-none">
                {JSON.stringify(
                  inspectEvent.payload ||
                    inspectEvent.tool_arguments ||
                    inspectEvent.tool_result_summary ||
                    inspectEvent.metadata_provenance ||
                    inspectEvent,
                  null,
                  2
                )}
              </pre>
            </div>

            <div className="text-right pt-2 border-t border-white/[0.06]">
              <button
                onClick={() => setInspectEvent(null)}
                className="rounded-md border border-white/[0.08] bg-zinc-900 px-4 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
