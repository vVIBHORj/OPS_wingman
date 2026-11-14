"use client";

import React, { useState } from "react";
import {
  Bot,
  ShieldCheck,
  AlertTriangle,
  Play,
  Clock,
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

const stateStyles: Record<string, { label: string; dot: string; badge: string }> = {
  COMPLETED: {
    label: "Completed",
    dot: "bg-emerald-400",
    badge: "border-emerald-500/20 bg-emerald-500/10 text-emerald-300",
  },
  PAUSED_FOR_APPROVAL: {
    label: "Paused for Approval",
    dot: "bg-amber-400",
    badge: "border-amber-500/20 bg-amber-500/10 text-amber-300",
  },
  FAILED: {
    label: "Failed",
    dot: "bg-rose-400",
    badge: "border-rose-500/20 bg-rose-500/10 text-rose-300",
  },
};

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
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-zinc-400" />
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">AI Operations Console</h1>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Deterministic runtime execution: Intent parsing, RAG policy gates, ML risk assessment, and orchestrated tool dispatch.
          </p>
        </div>
      </div>

      {/* Input Deck */}
      <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-5 space-y-4">
        <form onSubmit={handleExecute} className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="md:col-span-3">
              <label className="block text-[11px] font-medium uppercase tracking-wider text-zinc-500 mb-1.5 font-mono">
                Operational Directive (Natural Language)
              </label>
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="e.g. Process refund for customer return on order ORD-2026-1005..."
                className="w-full rounded-md border border-white/[0.08] bg-[#090a0f] px-3.5 py-2 text-xs text-zinc-200 placeholder-zinc-600 focus:border-zinc-500 focus:outline-none transition-colors"
                required
              />
            </div>

            <div>
              <label className="block text-[11px] font-medium uppercase tracking-wider text-zinc-500 mb-1.5 font-mono">
                Target Order (Optional)
              </label>
              <input
                type="text"
                value={orderNumber}
                onChange={(e) => setOrderNumber(e.target.value)}
                placeholder="e.g. ORD-2026-1001"
                className="w-full rounded-md border border-white/[0.08] bg-[#090a0f] px-3.5 py-2 text-xs text-zinc-200 placeholder-zinc-600 focus:border-zinc-500 focus:outline-none font-mono transition-colors"
              />
            </div>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 scrollbar-none">
              <span className="text-[11px] text-zinc-500 shrink-0 font-mono">Examples:</span>
              {SAMPLE_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => setInputText(prompt)}
                  className="rounded border border-white/[0.06] bg-[#090a0f] px-2.5 py-1 text-[11px] text-zinc-400 hover:text-zinc-200 hover:border-white/[0.14] whitespace-nowrap transition-colors"
                >
                  {prompt}
                </button>
              ))}
            </div>

            <button
              type="submit"
              disabled={executing || !inputText.trim()}
              className="inline-flex items-center gap-2 rounded-md border border-white/[0.12] bg-white/[0.08] px-4 py-2 text-xs font-medium text-zinc-100 hover:bg-white/[0.14] transition-colors disabled:opacity-40 shrink-0"
            >
              {executing ? (
                <>
                  <RefreshCw className="h-3.5 w-3.5 animate-spin text-zinc-400" />
                  <span>Evaluating Policies...</span>
                </>
              ) : (
                <>
                  <Play className="h-3.5 w-3.5 text-zinc-300" />
                  <span>Execute Directive</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/20 bg-rose-950/10 p-4 text-xs text-rose-300 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Execution Results Viewport */}
      {runResult && (
        <div className="space-y-6">
          {/* Top Status & Risk Banner */}
          <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.06] pb-4">
              <div>
                <div className="flex items-center gap-2 text-xs font-mono text-zinc-500 mb-1">
                  <span>Run ID:</span>
                  <span className="text-zinc-300">{runResult.run_id}</span>
                </div>
                <div className="flex items-center gap-3">
                  <h3 className="text-sm font-semibold text-zinc-100">Workflow Execution State</h3>
                  {(() => {
                    const st = stateStyles[runResult.state] || {
                      label: runResult.state,
                      dot: "bg-zinc-400",
                      badge: "border-zinc-700 bg-zinc-800 text-zinc-300",
                    };
                    return (
                      <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${st.badge}`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${st.dot}`} />
                        {st.label}
                      </span>
                    );
                  })()}
                </div>
              </div>

              {/* Pause for Approval Banner / Action */}
              {runResult.state === "PAUSED_FOR_APPROVAL" && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleResumeApproval(true)}
                    disabled={resuming}
                    className="inline-flex items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/20 px-3.5 py-1.5 text-xs font-medium text-emerald-300 hover:bg-emerald-500/30 disabled:opacity-40 transition-colors"
                  >
                    <ShieldCheck className="h-3.5 w-3.5" />
                    <span>Authorize &amp; Resume</span>
                  </button>
                  <button
                    onClick={() => handleResumeApproval(false)}
                    disabled={resuming}
                    className="inline-flex items-center gap-1.5 rounded-md border border-rose-500/30 bg-rose-500/10 px-3.5 py-1.5 text-xs font-medium text-rose-300 hover:bg-rose-500/20 disabled:opacity-40 transition-colors"
                  >
                    <span>Reject Action</span>
                  </button>
                </div>
              )}
            </div>

            {/* Risk Telemetry Strip */}
            {runResult.risk_assessment && (
              <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="rounded-lg border border-white/[0.06] bg-[#090a0f] p-3">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                    Calculated Risk Score
                  </div>
                  <div className="text-lg font-mono font-semibold text-zinc-100 tabular-nums mt-0.5">
                    {runResult.risk_assessment.risk_score}
                  </div>
                </div>

                <div className="rounded-lg border border-white/[0.06] bg-[#090a0f] p-3">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                    Risk Classification
                  </div>
                  <div
                    className={`text-sm font-semibold mt-1 font-mono uppercase ${
                      runResult.risk_assessment.risk_level === "CRITICAL" ||
                      runResult.risk_assessment.risk_level === "HIGH"
                        ? "text-rose-300"
                        : "text-emerald-300"
                    }`}
                  >
                    {runResult.risk_assessment.risk_level}
                  </div>
                </div>

                <div className="rounded-lg border border-white/[0.06] bg-[#090a0f] p-3">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                    Policy Evaluation
                  </div>
                  <div className="text-xs text-zinc-300 mt-1 font-mono">
                    {runResult.risk_assessment.gated_by_policy
                      ? `Gated by ${runResult.risk_assessment.policy_id || "POL-REF-001"}`
                      : "Direct execution permitted"}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Agent Narrative & Steps */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Terminal Console Output */}
            <div className="lg:col-span-2 rounded-xl border border-white/[0.08] bg-[#0c0d14] p-5 space-y-3">
              <div className="flex items-center gap-2 border-b border-white/[0.06] pb-3">
                <Terminal className="h-4 w-4 text-zinc-400" />
                <h4 className="text-xs font-semibold text-zinc-100 tracking-wide">Operations Agent Output</h4>
              </div>
              <div className="rounded-lg border border-white/[0.06] bg-[#08090d] p-4 font-mono text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap">
                {runResult.response_text || "Workflow completed successfully."}
              </div>
            </div>

            {/* Execution Timeline */}
            <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-5 space-y-3">
              <div className="flex items-center gap-2 border-b border-white/[0.06] pb-3">
                <Clock className="h-4 w-4 text-zinc-400" />
                <h4 className="text-xs font-semibold text-zinc-100 tracking-wide">Execution Timeline</h4>
              </div>

              <div className="space-y-2 text-xs">
                {runResult.steps && runResult.steps.length > 0 ? (
                  runResult.steps.map((st, i) => (
                    <div
                      key={i}
                      className="rounded-lg border border-white/[0.06] bg-[#090a0f] p-3 space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-medium text-zinc-200">
                          {st.tool_name}
                        </span>
                        <span className="text-[10px] font-mono uppercase text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded">
                          {st.status}
                        </span>
                      </div>
                      {st.duration_ms && (
                        <div className="text-[10px] text-zinc-500 font-mono">
                          Latency: {st.duration_ms}ms
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="text-zinc-500 text-xs py-4 text-center font-mono">
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
