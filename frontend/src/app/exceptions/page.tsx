"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  RefreshCw,
  Clock,
  CreditCard,
  Truck,
  ShieldAlert,
  LifeBuoy,
  ArrowRight,
  CheckCircle2,
} from "lucide-react";
import { fetchJson } from "@/lib/api";

interface ExceptionItem {
  id: string;
  category: "LOGISTICS" | "PAYMENT" | "APPROVAL" | "SUPPORT" | string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string;
  title: string;
  description: string;
  entity_type: string;
  entity_id: string;
  status: string;
  recommended_action: string;
  first_detected: string;
}

interface ExceptionsResponse {
  total: number;
  exceptions: ExceptionItem[];
}

const CATEGORIES = ["ALL", "LOGISTICS", "PAYMENT", "APPROVAL", "SUPPORT"];

export default function ExceptionsPage() {
  const [exceptions, setExceptions] = useState<ExceptionItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState("ALL");

  const loadExceptions = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchJson<ExceptionsResponse>("/operations/exceptions");
      setExceptions(data.exceptions || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      setError(err.message || "Failed to load operational exceptions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadExceptions();
  }, [loadExceptions]);

  const filtered = exceptions.filter(
    (e) => selectedCategory === "ALL" || e.category === selectedCategory
  );

  const getSeverityBadge = (sev: string) => {
    switch (sev) {
      case "CRITICAL":
        return "bg-rose-500/20 text-rose-400 border-rose-500/30";
      case "HIGH":
        return "bg-amber-500/20 text-amber-400 border-amber-500/30";
      default:
        return "bg-sky-500/20 text-sky-400 border-sky-500/30";
    }
  };

  const getCategoryIcon = (cat: string) => {
    switch (cat) {
      case "LOGISTICS":
        return <Truck className="h-4 w-4 text-sky-400" />;
      case "PAYMENT":
        return <CreditCard className="h-4 w-4 text-amber-400" />;
      case "APPROVAL":
        return <ShieldAlert className="h-4 w-4 text-purple-400" />;
      case "SUPPORT":
        return <LifeBuoy className="h-4 w-4 text-rose-400" />;
      default:
        return <AlertTriangle className="h-4 w-4 text-slate-400" />;
    }
  };

  const getResolveLink = (e: ExceptionItem) => {
    switch (e.category) {
      case "APPROVAL":
        return "/approvals";
      case "LOGISTICS":
        return "/shipments?is_delayed=true";
      case "PAYMENT":
        return "/payments?status=FAILED";
      case "SUPPORT":
        return "/tickets";
      default:
        return "/";
    }
  };

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <AlertTriangle className="h-6 w-6 text-rose-400" />
            Operational Exceptions Queue
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Prioritized work queue for transit delays, payment gateway failures, SLA breaches, and gated supervisor approvals.
          </p>
        </div>

        <button
          onClick={loadExceptions}
          disabled={loading}
          className="self-start sm:self-auto flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-800 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-sky-400" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Category Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
        {CATEGORIES.map((cat) => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors shrink-0 ${
              selectedCategory === cat
                ? "bg-sky-500 text-white font-semibold"
                : "bg-slate-900 text-slate-400 hover:text-slate-200 hover:bg-slate-800"
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Exceptions Cards List */}
      <div className="space-y-3">
        {loading && exceptions.length === 0 ? (
          <div className="py-16 text-center text-slate-500">
            <RefreshCw className="mx-auto h-6 w-6 animate-spin text-sky-400 mb-2" />
            Scanning for active operational exceptions...
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-12 text-center text-slate-400">
            <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-400 mb-2" />
            <h3 className="text-sm font-semibold text-white">No active exceptions detected</h3>
            <p className="text-xs text-slate-500 mt-1">
              All logistics, payments, and SLA criteria are operating within normal tolerances.
            </p>
          </div>
        ) : (
          filtered.map((item) => (
            <div
              key={item.id}
              className="rounded-xl border border-slate-800 bg-slate-900/40 p-4.5 hover:border-slate-700 transition-colors"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                <div className="flex items-center gap-2">
                  <div className="rounded-lg bg-slate-800 p-1.5">{getCategoryIcon(item.category)}</div>
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                    {item.category}
                  </span>
                  <span
                    className={`rounded border px-2 py-0.5 text-[10px] font-bold ${getSeverityBadge(
                      item.severity
                    )}`}
                  >
                    {item.severity}
                  </span>
                </div>

                <div className="text-[11px] text-slate-500 font-mono">
                  Detected {new Date(item.first_detected).toLocaleTimeString()}
                </div>
              </div>

              <h3 className="text-sm font-bold text-white mb-1">{item.title}</h3>
              <p className="text-xs text-slate-300 mb-3">{item.description}</p>

              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-slate-800/80 bg-slate-950/40 -mx-4.5 -mb-4.5 p-3 rounded-b-xl">
                <div className="text-xs text-slate-400">
                  <span className="font-semibold text-slate-300">Action: </span>
                  {item.recommended_action}
                </div>

                <Link
                  href={getResolveLink(item)}
                  className="inline-flex items-center gap-1 rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-semibold text-sky-400 hover:bg-slate-700 transition-colors shrink-0"
                >
                  <span>Resolve in Queue</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

