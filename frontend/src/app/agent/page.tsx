"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Bot,
  Send,
  Sparkles,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Play,
  Clock,
  ArrowRight,
  RefreshCw,
  Terminal,
} from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

interface AgentExecutionStep {
  step_number: number;
  tool_name: string;
  input_payload: Record<string, any>;
  result_payload?: Record<string, any>;
  duration_ms?: number;
  status: string;
}

interface AgentRunResult {
  run_id: string;
  state: string;
  input_text: string;
  order_number?: string;
  extracted_intent?: string;
  risk_assessment?: {
    risk_score: number;
    risk_level: string;
    factors: string[];
    gated_by_policy?: boolean;
    policy_id?: string;
  };
  approval_request?: {
    id: string;
    action: string;
    reason: string;
  };
  steps: AgentExecutionStep[];
  response_text: string;
  completed_at?: string;
}

const SAMPLE_PROMPTS = [
  "Check status of order ORD-2026-1001",
  "Cancel order ORD-2026-1002 due to customer address change",
  "Process full refund for high-value order ORD-2026-1003",
  "Track shipment for carrier Delhivery",
];

export default function AgentConsolePage() {
  const [inputText, setInputText] = useState("");
  const [orderNumber, setOrderNumber] = useState("");
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<AgentRunResult | null>(null);
  const [resuming, setResuming] = useState(false);

  const handleExecute = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputText.trim()) return;

    try {
      setExecuting(true);
      setError(null);
      const res = await fetch(`${API_BASE_URL}/agent/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_text: inputText.trim(),
          order_number: orderNumber.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Agent execution failed");
      }

      const data = await res.json();
      setRunResult(data);
    } catch (err: any) {
      setError(err.message || "Failed to execute agent workflow");
    } finally {
      setExecuting(false);
    }
  };

  const handleResumeApproval = async (approved: boolean) => {
    if (!runResult?.run_id) return;
    try {
      setResuming(true);
      const res = await fetch(`${API_BASE_URL}/agent/runs/${runResult.run_id}/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approved,
          reason: approved
            ? "Approved by operator in live console"
            : "Rejected by operator in live console",
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Resume operation failed");
      }

      const updated = await res.json();
      setRunResult(updated);
    } catch (err: any) {
      alert(`Error resuming agent: ${err.message}`);
    } finally {
      setResuming(false);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <div className="border-b border-slate-800 pb-5">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white shadow">
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">
              AI Operations Agent Console
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Deterministic runtime: Intent parsing, RAG policy evaluation, ML risk gating, and tool dispatch.
            </p>
          </div>
        </div>
      </div>

      {/* Input / Control Deck */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5 space-y-4 shadow">
        <form onSubmit={handleExecute} className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="md:col-span-3">
              <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Natural Language Operational Directive
              </label>
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="e.g. Process refund for customer return on order ORD-2026-1005..."
                className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
                required
              />
            </div>

            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Target Order (Optional)
              </label>
              <input
                type="text"
                value={orderNumber}
                onChange={(e) => setOrderNumber(e.target.value)}
                placeholder="e.g. ORD-2026-1001"
                className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950 px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:border-indigo-500 focus:outline-none font-mono"
              />
            </div>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
            <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0 scrollbar-thin">
              <span className="text-[11px] text-slate-500 shrink-0 font-medium">Examples:</span>
              {SAMPLE_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => setInputText(prompt)}
                  className="rounded-full border border-slate-800 bg-slate-950 px-2.5 py-1 text-[10px] text-slate-400 hover:text-white hover:border-slate-700 whitespace-nowrap transition-colors"
                >
                  {prompt}
                </button>
              ))}
            </div>

            <button
              type="submit"
              disabled={executing || !inputText.trim()}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors disabled:opacity-50 shrink-0"
            >
              {executing ? (
                <>
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  <span>Evaluating Policies...</span>
                </>
              ) : (
                <>
                  <Play className="h-3.5 w-3.5" />
                  <span>Execute Workflow</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 p-4 text-xs text-rose-300 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Execution Results Viewport */}
      {runResult && (
        <div className="space-y-6">
          {/* Top Status & Risk Banner */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-slate-400">Run ID:</span>
                  <span className="font-mono text-xs font-semibold text-sky-400">
                    {runResult.run_id}
                  </span>
                </div>
                <h3 className="text-base font-bold text-white mt-1">
                  Workflow State:{" "}
                  <span
                    className={`font-mono ${
                      runResult.state === "COMPLETED"
                        ? "text-emerald-400"
                        : runResult.state === "PAUSED_FOR_APPROVAL"
                        ? "text-amber-400"
                        : "text-rose-400"
                    }`}
                  >
                    {runResult.state}
                  </span>
                </h3>
              </div>

              {/* Pause for Approval Banner / Action */}
              {runResult.state === "PAUSED_FOR_APPROVAL" && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleResumeApproval(true)}
                    disabled={resuming}
                    className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
                  >
                    <ShieldCheck className="h-4 w-4" />
                    <span>Authorize &amp; Resume</span>
                  </button>
                  <button
                    onClick={() => handleResumeApproval(false)}
                    disabled={resuming}
                    className="flex items-center gap-1.5 rounded-lg bg-rose-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-rose-500 disabled:opacity-50"
                  >
                    <span>Reject Action</span>
                  </button>
                </div>
              )}
            </div>

            {/* Risk Telemetry */}
            {runResult.risk_assessment && (
              <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="rounded-lg border border-slate-800 bg-slate-950 p-3">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    Calculated Risk Score
                  </div>
                  <div className="text-lg font-bold text-white mt-0.5">
                    {runResult.risk_assessment.risk_score}
                  </div>
                </div>

                <div className="rounded-lg border border-slate-800 bg-slate-950 p-3">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    Risk Classification
                  </div>
                  <div
                    className={`text-lg font-bold mt-0.5 ${
                      runResult.risk_assessment.risk_level === "CRITICAL" ||
                      runResult.risk_assessment.risk_level === "HIGH"
                        ? "text-amber-400"
                        : "text-emerald-400"
                    }`}
                  >
                    {runResult.risk_assessment.risk_level}
                  </div>
                </div>

                <div className="rounded-lg border border-slate-800 bg-slate-950 p-3">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    Policy Enforcement
                  </div>
                  <div className="text-sm font-semibold text-slate-200 mt-1">
                    {runResult.risk_assessment.gated_by_policy
                      ? `Gated by ${runResult.risk_assessment.policy_id || "POL-REF-001"}`
                      : "Direct execution permitted"}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Agent Response & Execution Steps */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Agent Narrative Output */}
            <div className="lg:col-span-2 rounded-xl border border-slate-800 bg-slate-900/40 p-5 space-y-3">
              <h4 className="text-sm font-bold text-white flex items-center gap-2">
                <Terminal className="h-4 w-4 text-sky-400" />
                Operations Agent Output
              </h4>
              <div className="rounded-lg border border-slate-800 bg-slate-950 p-4 font-mono text-xs text-slate-200 leading-relaxed whitespace-pre-wrap">
                {runResult.response_text || "Workflow completed successfully."}
              </div>
            </div>

            {/* Execution Steps Log */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 space-y-3">
              <h4 className="text-sm font-bold text-white flex items-center gap-2">
                <Clock className="h-4 w-4 text-indigo-400" />
                Execution Timeline
              </h4>

              <div className="space-y-2 text-xs">
                {runResult.steps && runResult.steps.length > 0 ? (
                  runResult.steps.map((st, i) => (
                    <div
                      key={i}
                      className="rounded-lg border border-slate-800/80 bg-slate-950 p-2.5 space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-300 font-mono">
                          {st.tool_name}
                        </span>
                        <span className="text-[9px] font-bold text-emerald-400 bg-emerald-500/10 px-1.5 py-0.2 rounded">
                          {st.status}
                        </span>
                      </div>
                      {st.duration_ms && (
                        <div className="text-[10px] text-slate-500 font-mono">
                          Latency: {st.duration_ms}ms
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="text-slate-500 text-xs py-4 text-center">
                    Workflow initialized and evaluated.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

