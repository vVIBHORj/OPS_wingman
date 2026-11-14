"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  RefreshCw,
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
  const [selectedCategory, setSelectedCategory] = useState("ALL");

  const loadExceptions = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchJson<ExceptionsResponse>("/operations/exceptions");
      setExceptions(data.exceptions || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      console.error("Failed to load exceptions:", err);
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
        return "border-rose-500/25 bg-rose-500/10 text-rose-300";
      case "HIGH":
        return "border-amber-500/25 bg-amber-500/10 text-amber-300";
      default:
        return "border-sky-500/25 bg-sky-500/10 text-sky-300";
    }
  };

  const getCategoryIcon = (cat: string) => {
    switch (cat) {
      case "LOGISTICS":
        return <Truck className="h-4 w-4 text-zinc-400" />;
      case "PAYMENT":
        return <CreditCard className="h-4 w-4 text-amber-400/80" />;
      case "APPROVAL":
        return <ShieldAlert className="h-4 w-4 text-purple-400/80" />;
      case "SUPPORT":
        return <LifeBuoy className="h-4 w-4 text-rose-400/80" />;
      default:
        return <AlertTriangle className="h-4 w-4 text-zinc-400" />;
    }
  };

  const getResolveLink = (e: ExceptionItem) => {
    switch (e.category) {
      case "APPROVAL":
        return "/approvals";
      case "LOGISTICS":
        return "/shipments";
      case "PAYMENT":
        return "/payments";
      case "SUPPORT":
        return "/tickets";
      default:
        return "/";
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-rose-400" />
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">Operational Exceptions</h1>
            <span className="text-xs font-mono text-zinc-500 tabular-nums">({filtered.length})</span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Prioritized work queue for transit delays, gateway failures, SLA breaches, and gated approval holds.
          </p>
        </div>

        <button
          onClick={loadExceptions}
          disabled={loading}
          className="self-start sm:self-auto inline-flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-[#0c0d14] px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-zinc-400" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Category Pills */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
        {CATEGORIES.map((cat) => {
          const isSelected = selectedCategory === cat;
          return (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors shrink-0 ${
                isSelected
                  ? "bg-white/[0.12] text-zinc-100 border border-white/[0.16]"
                  : "border border-white/[0.06] bg-[#0c0d14] text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60"
              }`}
            >
              {cat}
            </button>
          );
        })}
      </div>

      {/* Exceptions Cards List */}
      <div className="space-y-3">
        {loading && exceptions.length === 0 ? (
          <div className="py-16 text-center text-zinc-500 font-mono text-xs">
            <RefreshCw className="mx-auto h-5 w-5 animate-spin text-zinc-600 mb-2" />
            Scanning for active anomalies and policy breaches...
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-xl border border-dashed border-white/[0.08] bg-[#0c0d14]/40 p-12 text-center">
            <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-400/80 mb-2" />
            <h3 className="text-xs font-semibold text-zinc-100">Zero Active Exceptions</h3>
            <p className="text-[11px] text-zinc-500 mt-1">
              All fulfillment, payment gateways, and support SLA queues are operating within standard tolerances.
            </p>
          </div>
        ) : (
          filtered.map((item) => (
            <div
              key={item.id}
              className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-4.5 hover:border-white/[0.14] transition-colors overflow-hidden"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                <div className="flex items-center gap-2">
                  <div className="rounded border border-white/[0.08] bg-white/[0.02] p-1.5">{getCategoryIcon(item.category)}</div>
                  <span className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">
                    {item.category}
                  </span>
                  <span
                    className={`rounded border px-2 py-0.5 text-[10px] font-mono uppercase ${getSeverityBadge(
                      item.severity
                    )}`}
                  >
                    {item.severity}
                  </span>
                </div>

                <div className="text-[11px] text-zinc-500 font-mono">
                  Detected {new Date(item.first_detected).toLocaleTimeString()}
                </div>
              </div>

              <h3 className="text-xs font-semibold text-zinc-100 mb-1">{item.title}</h3>
              <p className="text-xs text-zinc-400 mb-3 leading-relaxed">{item.description}</p>

              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-white/[0.06] bg-[#090a0f] -mx-4.5 -mb-4.5 px-4.5 py-3 rounded-b-xl">
                <div className="text-xs text-zinc-400">
                  <span className="text-zinc-500 font-medium">Recommended: </span>
                  <span className="text-zinc-300 font-mono text-[11px]">{item.recommended_action}</span>
                </div>

                <Link
                  href={getResolveLink(item)}
                  className="inline-flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-[#0c0d14] px-3 py-1.5 text-xs font-medium text-zinc-200 hover:bg-zinc-800 hover:text-white transition-colors shrink-0"
                >
                  <span>Resolve in Queue</span>
                  <ArrowRight className="h-3.5 w-3.5 text-zinc-400" />
                </Link>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
