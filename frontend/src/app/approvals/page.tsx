"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";

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

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("PENDING");
  const [rejectionReasons, setRejectionReasons] = useState<Record<string, string>>({});
  const [submittingId, setSubmittingId] = useState<string | null>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const fetchApprovals = async () => {
    try {
      setLoading(true);
      setError(null);
      const url = statusFilter
        ? `${API_URL}/approvals?status=${statusFilter}`
        : `${API_URL}/approvals`;
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`Failed to fetch approvals: ${res.statusText}`);
      }
      const data = await res.json();
      setApprovals(data);
    } catch (err: any) {
      setError(err.message || "An error occurred fetching approvals");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApprovals();
  }, [statusFilter]);

  const handleApprove = async (id: string) => {
    try {
      setSubmittingId(id);
      const res = await fetch(`${API_URL}/approvals/${id}/approve`, {
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
      const res = await fetch(`${API_URL}/approvals/${id}/reject`, {
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
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-12 font-sans">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <div className="flex items-center gap-2">
              <Link
                href="/"
                className="text-xs text-sky-400 hover:text-sky-300 transition-colors"
              >
                &larr; Back to Home
              </Link>
              <span className="text-slate-600">•</span>
              <span className="text-xs text-slate-400 font-mono">Phase 3: D-12 Human Approval Queue</span>
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight mt-1 text-white">
              Operations Approval Queue
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Gated Human-in-the-Loop authorization for HIGH-risk state modifications.
            </p>
          </div>

          {/* Filter Pills */}
          <div className="flex items-center gap-2 bg-slate-900 p-1.5 rounded-lg border border-slate-800">
            {["PENDING", "APPROVED", "REJECTED", ""].map((f) => (
              <button
                key={f}
                onClick={() => setStatusFilter(f)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                  statusFilter === f
                    ? "bg-sky-500 text-white shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {f === "" ? "ALL" : f}
              </button>
            ))}
          </div>
        </div>

        {/* Content Section */}
        {loading ? (
          <div className="flex flex-col items-center justify-center p-16 space-y-3">
            <div className="w-8 h-8 border-4 border-sky-400 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-sm text-slate-400">Loading approval requests...</p>
          </div>
        ) : error ? (
          <div className="p-4 bg-red-950/40 border border-red-800/60 rounded-xl text-red-300 text-sm">
            <p className="font-semibold">Error loading approvals</p>
            <p className="text-xs mt-1 text-red-400">{error}</p>
            <button
              onClick={fetchApprovals}
              className="mt-3 px-3 py-1.5 bg-red-800/40 hover:bg-red-800/60 text-xs rounded-md border border-red-700"
            >
              Retry
            </button>
          </div>
        ) : approvals.length === 0 ? (
          <div className="text-center p-16 border border-dashed border-slate-800 rounded-2xl bg-slate-900/30">
            <p className="text-slate-400 text-sm">No {statusFilter || "matching"} approval requests found.</p>
            <p className="text-xs text-slate-500 mt-1">
              When an OpsAgent encounters a HIGH-risk policy gate, it will appear here for review.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {approvals.map((item) => (
              <div
                key={item.id}
                className="p-6 rounded-xl border border-slate-800 bg-slate-900/60 shadow-lg space-y-4 transition-all"
              >
                {/* Top Row: Action & Status Badge */}
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/60 pb-3">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm font-bold text-sky-400">
                      {item.action_name}
                    </span>
                    {item.target_entity && (
                      <span className="px-2 py-0.5 text-xs bg-slate-800 rounded text-slate-300 font-mono">
                        Target: {item.target_entity}
                      </span>
                    )}
                    <span
                      className={`text-xs px-2.5 py-0.5 rounded-full font-bold uppercase ${
                        item.risk_level === "HIGH"
                          ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                          : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                      }`}
                    >
                      {item.risk_level} Risk
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs px-3 py-1 rounded-full font-semibold uppercase ${
                        item.status === "PENDING"
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                          : item.status === "APPROVED"
                          ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                          : "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                      }`}
                    >
                      {item.status}
                    </span>
                  </div>
                </div>

                {/* Details Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-slate-300">
                  <div>
                    <span className="text-slate-500 uppercase tracking-wider block font-semibold mb-1">
                      Reason / Business Context
                    </span>
                    <p className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/80 font-mono">
                      {item.reason}
                    </p>
                  </div>

                  <div>
                    <span className="text-slate-500 uppercase tracking-wider block font-semibold mb-1">
                      Policy Evaluation Decision
                    </span>
                    <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/80 space-y-1">
                      <p>
                        <strong className="text-slate-400">Policy:</strong>{" "}
                        {item.policy_version ? `${item.policy_decision?.policy_id || "POL"} (v${item.policy_version})` : "N/A"}
                      </p>
                      <p>
                        <strong className="text-slate-400">Rule Decision:</strong>{" "}
                        {item.policy_decision?.decision || "Manual verification required"}
                      </p>
                      {item.policy_decision?.matched_rules && (
                        <p>
                          <strong className="text-slate-400">Matched Rules:</strong>{" "}
                          {item.policy_decision.matched_rules.join(", ")}
                        </p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Parameters & Metadata */}
                <div className="text-xs text-slate-400 flex flex-wrap items-center gap-x-6 gap-y-2 pt-2 border-t border-slate-800/40">
                  <span>
                    <strong>Workflow ID:</strong> <code className="text-sky-300">{item.workflow_id}</code>
                  </span>
                  <span>
                    <strong>Requested At:</strong> {new Date(item.requested_at).toLocaleString()}
                  </span>
                  {item.approver_identity && (
                    <span>
                      <strong>Decided By:</strong> {item.approver_identity}
                    </span>
                  )}
                  {item.rejection_reason && (
                    <span className="text-rose-400">
                      <strong>Rejection Reason:</strong> {item.rejection_reason}
                    </span>
                  )}
                </div>

                {/* Citations Provenance (D-10) */}
                {item.citations && item.citations.length > 0 && (
                  <div className="pt-2">
                    <span className="text-xs text-slate-500 uppercase tracking-wider block font-semibold mb-1">
                      Retrieved Knowledge Citations (D-10 RAG Provenance)
                    </span>
                    <div className="space-y-1.5">
                      {item.citations.map((c, idx) => (
                        <div
                          key={idx}
                          className="text-xs bg-slate-950/40 border border-slate-800/60 p-2.5 rounded-lg text-slate-400"
                        >
                          <div className="font-semibold text-slate-300 flex items-center justify-between">
                            <span>
                              {c.document_id} — {c.title} (v{c.version})
                            </span>
                            {c.similarity_score !== undefined && (
                              <span className="text-[10px] text-sky-400 font-mono">
                                Match: {(c.similarity_score * 100).toFixed(1)}%
                              </span>
                            )}
                          </div>
                          <p className="mt-1 text-slate-300 text-[11px] line-clamp-2 italic">
                            "{c.text}"
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Action Controls for PENDING requests */}
                {item.status === "PENDING" && (
                  <div className="pt-4 border-t border-slate-800 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
                    <div className="flex-1">
                      <input
                        type="text"
                        placeholder="Rejection reason (required if rejecting)..."
                        value={rejectionReasons[item.id] || ""}
                        onChange={(e) =>
                          setRejectionReasons({
                            ...rejectionReasons,
                            [item.id]: e.target.value,
                          })
                        }
                        className="w-full text-xs px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500"
                      />
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleReject(item.id)}
                        disabled={submittingId === item.id}
                        className="px-4 py-2 text-xs font-semibold bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 rounded-lg transition-colors disabled:opacity-50"
                      >
                        {submittingId === item.id ? "Processing..." : "Reject Action"}
                      </button>
                      <button
                        onClick={() => handleApprove(item.id)}
                        disabled={submittingId === item.id}
                        className="px-5 py-2 text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md rounded-lg transition-colors disabled:opacity-50"
                      >
                        {submittingId === item.id ? "Processing..." : "Approve & Execute"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
