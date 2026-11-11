"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  History,
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  FileCode,
  X,
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
  const [error, setError] = useState<string | null>(null);
  const [eventTypeFilter, setEventTypeFilter] = useState("");
  const [actorFilter, setActorFilter] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 20;

  const [inspectEvent, setInspectEvent] = useState<AuditEventItem | null>(null);

  const loadEvents = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
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
      setError(err.message || "Failed to load audit events");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, eventTypeFilter, actorFilter]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <History className="h-6 w-6 text-sky-400" />
            Audit &amp; Compliance Trail
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Immutable, cryptographically verifiable record of all automated, human, and policy-driven mutations.
          </p>
        </div>

        <button
          onClick={loadEvents}
          disabled={loading}
          className="self-start sm:self-auto flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-800 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-sky-400" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <input
          type="text"
          value={eventTypeFilter}
          onChange={(e) => {
            setEventTypeFilter(e.target.value);
            setPage(0);
          }}
          placeholder="Filter by event type (e.g. ORDER_PLACED, REFUND_REQUESTED)"
          className="rounded-lg border border-slate-800 bg-slate-900/80 px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-sky-500 focus:outline-none flex-1"
        />

        <input
          type="text"
          value={actorFilter}
          onChange={(e) => {
            setActorFilter(e.target.value);
            setPage(0);
          }}
          placeholder="Filter by actor (e.g. system, operator, agent)"
          className="rounded-lg border border-slate-800 bg-slate-900/80 px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-sky-500 focus:outline-none w-full sm:w-64"
        />
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden shadow">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 bg-slate-900/80 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3">Event Type</th>
                <th className="px-4 py-3">Actor</th>
                <th className="px-4 py-3">Target Entity</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3 text-right">Payload</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {loading && events.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-500">
                    <RefreshCw className="mx-auto h-6 w-6 animate-spin text-sky-400 mb-2" />
                    Loading audit events...
                  </td>
                </tr>
              ) : events.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-500">
                    No audit records match the filter query.
                  </td>
                </tr>
              ) : (
                events.map((ev) => (
                  <tr key={String(ev.id || ev.event_id)} className="hover:bg-slate-800/30 transition-colors">
                    <td className="px-4 py-3 text-slate-400 whitespace-nowrap font-mono">
                      {new Date(ev.created_at || ev.timestamp || Date.now()).toLocaleString("en-IN")}
                    </td>
                    <td className="px-4 py-3 font-semibold text-sky-400 font-mono">
                      {ev.event_type}
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] font-semibold text-slate-300 uppercase">
                        {ev.actor}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-300">
                      {ev.entity_type} ({String(ev.entity_id || "").slice(0, 8)}...)
                    </td>
                    <td className="px-4 py-3 text-slate-200">{ev.action || ev.operation || "SYSTEM"}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => setInspectEvent(ev)}
                        className="inline-flex items-center gap-1 rounded bg-slate-800 px-2 py-1 text-[11px] font-medium text-slate-300 hover:bg-slate-700 transition-colors"
                      >
                        <FileCode className="h-3 w-3" />
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
        <div className="flex items-center justify-between border-t border-slate-800 bg-slate-900/60 px-4 py-3 text-xs text-slate-400">
          <div>
            Showing <span className="font-semibold text-white">{events.length}</span> of{" "}
            <span className="font-semibold text-white">{total}</span> audit entries
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

      {/* Payload Modal */}
      {inspectEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-lg rounded-xl border border-slate-800 bg-slate-900 p-5 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-white font-mono">{inspectEvent.event_type}</h3>
                <p className="text-[11px] text-slate-400 font-mono">ID: {inspectEvent.id}</p>
              </div>
              <button
                onClick={() => setInspectEvent(null)}
                className="rounded-lg p-1 text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
                Sanitized Payload Data
              </div>
              <pre className="max-h-64 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950 p-3 text-[11px] font-mono text-emerald-400 scrollbar-thin">
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

            <div className="text-right">
              <button
                onClick={() => setInspectEvent(null)}
                className="rounded-lg bg-slate-800 px-4 py-1.5 text-xs text-white hover:bg-slate-700"
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

