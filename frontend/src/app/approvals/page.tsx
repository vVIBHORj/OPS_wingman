"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Clock,
  BookOpen,
  ArrowRight,
  ChevronRight,
} from "lucide-react";
import { fetchJson, API_BASE_URL } from "@/lib/api";

interface Citation {
  document_id: string;
  title: string;
  chunk_index: number;
  text: string;
  version: string;
  similarity_score?: number;
}

interface PolicyDecision {
  allowed: boolean;
  requires_approval: boolean;
  decision: string;
  policy_id: string;
  policy_version: string;
  matched_rules: string[];
}

interface ApprovalRecord {
  id: string;
  workflow_id: string;
  action_name: string;
  target_entity: string | null;
  parameters: Record<string, any>;
  risk_level: string;
  reason: string;
  policy_decision: PolicyDecision | null;
  policy_version: string | null;
  citations: Citation[];
  status: "PENDING" | "APPROVED" | "REJECTED" | "EXPIRED";
  approver_identity: string | null;
  rejection_reason: string | null;
  requested_at: string;
  decided_at: string | null;
}

const statusConfig: Record<string, { label: string; dot: string; badge: string }> = {
  PENDING: {
    label: "Pending Review",
    dot: "bg-amber-400",
    badge: "border-amber-500/20 bg-amber-500/10 text-amber-300",
  },
  APPROVED: {
    label: "Approved",
    dot: "bg-emerald-400",
    badge: "border-emerald-500/20 bg-emerald-500/10 text-emerald-300",
  },
  REJECTED: {
    label: "Rejected",
    dot: "bg-rose-400",
    badge: "border-rose-500/20 bg-rose-500/10 text-rose-300",
  },
  EXPIRED: {
    label: "Expired",
    dot: "bg-zinc-400",
    badge: "border-zinc-700 bg-zinc-800 text-zinc-300",
  },
};

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("PENDING");
  const [rejectionReasons, setRejectionReasons] = useState<Record<string, string>>({});
  const [submittingId, setSubmittingId] = useState<string | null>(null);

  const fetchApprovals = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const endpoint = statusFilter
        ? `/approvals?status=${statusFilter}`
        : `/approvals`;
      const data = await fetchJson<ApprovalRecord[]>(endpoint);
      setApprovals(Array.isArray(data) ? data : []);
    } catch (err: any) {
      setError(err.message || "An error occurred fetching approvals");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchApprovals();
  }, [fetchApprovals]);

  const handleApprove = async (id: string) => {
    try {
      setSubmittingId(id);
      const res = await fetch(`${API_BASE_URL}/approvals/${id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approver_identity: "supervisor@opswingman.local" }),
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to approve request");
      }
      await fetchApprovals();
    } catch (err: any) {
      alert(`Approval error: ${err.message}`);
    } finally {
      setSubmittingId(null);
    }
  };

  const handleReject = async (id: string) => {
    const reason = rejectionReasons[id] || "Rejected by supervisor";
    try {
      setSubmittingId(id);
      const res = await fetch(`${API_BASE_URL}/approvals/${id}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approver_identity: "supervisor@opswingman.local",
          rejection_reason: reason,
        }),
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to reject request");
      }
      await fetchApprovals();
    } catch (err: any) {
      alert(`Rejection error: ${err.message}`);
    } finally {
      setSubmittingId(null);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-zinc-400" />
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">Governance &amp; Approvals</h1>
            <span className="text-xs font-mono text-zinc-500 tabular-nums">({approvals.length})</span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Gated human-in-the-loop authorization queue for high-risk operations and policy overrides.
          </p>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1.5 self-start sm:self-auto overflow-x-auto">
          {["PENDING", "APPROVED", "REJECTED", ""].map((f) => {
            const isSelected = statusFilter === f;
            return (
              <button
                key={f}
                onClick={() => setStatusFilter(f)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors shrink-0 ${
                  isSelected
                    ? "bg-white/[0.12] text-zinc-100 border border-white/[0.16]"
                    : "border border-white/[0.06] bg-[#0c0d14] text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60"
                }`}
              >
                {f === "" ? "ALL" : f}
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Content */}
      {loading ? (
        <div className="flex h-72 flex-col items-center justify-center gap-3 text-zinc-400">
          <RefreshCw className="h-6 w-6 animate-spin text-zinc-500" />
          <p className="text-xs font-mono">Loading approval ledger...</p>
        </div>
      ) : error ? (
        <div className="p-4 rounded-xl border border-rose-500/20 bg-rose-950/10 text-xs text-rose-300 space-y-2">
          <div className="flex items-center gap-2 font-medium">
            <AlertTriangle className="h-4 w-4 text-rose-400" />
            <span>Failed to query approval queue</span>
          </div>
          <p className="text-zinc-400 font-mono">{error}</p>
          <button
            onClick={fetchApprovals}
            className="inline-flex items-center gap-1.5 rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-1 text-xs font-medium text-rose-200 hover:bg-rose-500/20 transition-colors"
          >
            Retry Request
          </button>
        </div>
      ) : approvals.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/[0.08] bg-[#0c0d14]/40 p-12 text-center">
          <ShieldCheck className="mx-auto h-8 w-8 text-zinc-600 mb-2" />
          <p className="text-xs font-medium text-zinc-300">No {statusFilter ? statusFilter.toLowerCase() : ""} approval requests in queue.</p>
          <p className="text-[11px] text-zinc-500 mt-1 max-w-sm mx-auto">
            High-risk operations or policy threshold violations will automatically be held here awaiting supervisor sign-off.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {approvals.map((item) => {
            const statusStyle = statusConfig[item.status] || {
              label: item.status,
              dot: "bg-zinc-400",
              badge: "border-zinc-700 bg-zinc-800 text-zinc-300",
            };

            const isHighRisk = item.risk_level === "HIGH" || item.risk_level === "CRITICAL";

            return (
              <div
                key={item.id}
                className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-5 space-y-4 hover:border-white/[0.14] transition-colors"
              >
                {/* Header row */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.06] pb-3">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <span className="font-mono text-xs font-semibold text-zinc-100">
                      {item.action_name}
                    </span>
                    {item.target_entity && (
                      <span className="rounded border border-white/[0.06] bg-white/[0.03] px-2 py-0.5 text-[11px] font-mono text-zinc-400">
                        Target: {item.target_entity}
                      </span>
                    )}
                    <span
                      className={`inline-flex items-center rounded border px-2 py-0.5 text-[10px] font-mono uppercase ${
                        isHighRisk
                          ? "border-rose-500/25 bg-rose-500/10 text-rose-300"
                          : "border-amber-500/25 bg-amber-500/10 text-amber-300"
                      }`}
                    >
                      {item.risk_level} Risk
                    </span>
                  </div>

                  <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${statusStyle.badge}`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${statusStyle.dot}`} />
                    {statusStyle.label}
                  </span>
                </div>

                {/* 2-Column Details: Context & Policy */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div>
                    <div className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">
                      Operational Context
                    </div>
                    <div className="rounded-lg border border-white/[0.06] bg-[#090a0f] p-3 text-zinc-300 font-mono text-xs leading-relaxed">
                      {item.reason}
                    </div>
                  </div>

                  <div>
                    <div className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">
                      Policy Verification
                    </div>
                    <div className="rounded-lg border border-white/[0.06] bg-[#090a0f] p-3 space-y-1.5 text-zinc-300 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-zinc-400">Framework:</span>
                        <span className="font-mono text-zinc-200">
                          {item.policy_version ? `${item.policy_decision?.policy_id || "POL-GOV"} (v${item.policy_version})` : "Standard Control"}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-zinc-400">Rule Evaluation:</span>
                        <span className="text-zinc-200">
                          {item.policy_decision?.decision || "Manual verification required"}
                        </span>
                      </div>
                      {item.policy_decision?.matched_rules && item.policy_decision.matched_rules.length > 0 && (
                        <div className="pt-1 border-t border-white/[0.06] text-[11px] text-zinc-300">
                          <span className="text-zinc-400">Matched Constraints:</span>{" "}
                          <span className="font-mono text-zinc-200">{item.policy_decision.matched_rules.join(", ")}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Metadata strip */}
                <div className="text-[11px] text-zinc-400 font-mono flex flex-wrap items-center gap-x-5 gap-y-1.5 pt-2 border-t border-white/[0.06]">
                  <div>
                    <span className="text-zinc-400">Workflow:</span> <span className="text-zinc-300 font-medium">{item.workflow_id}</span>
                  </div>
                  <div>
                    <span className="text-zinc-400">Requested:</span> <span className="text-zinc-300 font-medium">{new Date(item.requested_at).toLocaleString("en-IN")}</span>
                  </div>
                  {item.approver_identity && (
                    <div>
                      <span className="text-zinc-400">Decided by:</span> <span className="text-zinc-200">{item.approver_identity}</span>
                    </div>
                  )}
                  {item.rejection_reason && (
                    <div className="text-rose-400">
                      <span>Reason:</span> {item.rejection_reason}
                    </div>
                  )}
                </div>

                {/* Retrieved Knowledge Citations */}
                {item.citations && item.citations.length > 0 && (
                  <div className="pt-2">
                    <div className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <BookOpen className="h-3.5 w-3.5 text-zinc-400" />
                      Retrieved Knowledge Citations (RAG Provenance)
                    </div>
                    <div className="space-y-2">
                      {item.citations.map((c, idx) => (
                        <div
                          key={idx}
                          className="rounded-lg border border-white/[0.06] bg-[#090a0f] p-3 text-xs text-zinc-300"
                        >
                          <div className="font-medium text-zinc-200 flex items-center justify-between mb-1">
                            <span className="font-mono text-[11px]">
                              {c.document_id} — {c.title} (v{c.version})
                            </span>
                            {c.similarity_score !== undefined && (
                              <span className="text-[10px] text-zinc-400 font-mono tabular-nums">
                                Match: {(c.similarity_score * 100).toFixed(1)}%
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-zinc-400 leading-relaxed italic">
                            &quot;{c.text}&quot;
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Action Controls for PENDING requests */}
                {item.status === "PENDING" && (
                  <div className="pt-3 border-t border-white/[0.06] flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
                    <div className="flex-1">
                      <input
                        type="text"
                        placeholder="Rejection justification (required if declining)..."
                        value={rejectionReasons[item.id] || ""}
                        onChange={(e) =>
                          setRejectionReasons({
                            ...rejectionReasons,
                            [item.id]: e.target.value,
                          })
                        }
                        className="w-full text-xs px-3 py-1.5 bg-[#090a0f] border border-white/[0.08] rounded-md text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500 transition-colors"
                      />
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleReject(item.id)}
                        disabled={submittingId === item.id}
                        className="inline-flex items-center gap-1.5 rounded-md border border-rose-500/30 bg-rose-500/10 px-3.5 py-1.5 text-xs font-medium text-rose-300 hover:bg-rose-500/20 transition-colors disabled:opacity-50"
                      >
                        <XCircle className="h-3.5 w-3.5" />
                        <span>{submittingId === item.id ? "Processing..." : "Reject"}</span>
                      </button>
                      <button
                        onClick={() => handleApprove(item.id)}
                        disabled={submittingId === item.id}
                        className="inline-flex items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/20 px-4 py-1.5 text-xs font-medium text-emerald-300 hover:bg-emerald-500/30 transition-colors disabled:opacity-50"
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        <span>{submittingId === item.id ? "Authorizing..." : "Approve & Execute"}</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
