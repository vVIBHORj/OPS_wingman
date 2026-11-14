"use client";

import React, { useState } from "react";
import {
  PlayCircle,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Clock,
  ExternalLink,
} from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

interface ScenarioDefinition {
  id: string;
  name: string;
  category: string;
  description: string;
  testedMechanisms: string[];
}

const SCENARIOS: ScenarioDefinition[] = [
  {
    id: "1",
    name: "Normal Order Lifecycle Flow",
    category: "Full Lifecycle",
    description:
      "Simulates end-to-end checkout: order creation, payment capture, carrier dispatch, tracking generation, and final delivery verification.",
    testedMechanisms: [
      "Order creation & line items",
      "Payment capture",
      "Shipment creation & tracking",
      "Delivery state verification",
    ],
  },
  {
    id: "2",
    name: "Delayed Shipment & Operational Alert",
    category: "Logistics",
    description:
      "Dispatches an order via BlueDart, logs transit network disruption at Hubli Hub, updates ETA, and registers exception in Operations Queue.",
    testedMechanisms: [
      "Carrier transit tracking",
      "Network disruption logging",
      "Exception Queue ingestion",
      "ETA revision",
    ],
  },
  {
    id: "3",
    name: "High-Value Refund & Supervisor Approval",
    category: "Policy & Human-in-the-Loop",
    description:
      "Places high-value order (INR 6,500), requests refund via Agent, triggers ML risk evaluation (>0.80), gates in Approval Queue, simulates supervisor authorization, and verifies database state.",
    testedMechanisms: [
      "Deterministic policy evaluation",
      "ML risk assessment telemetry",
      "Human Approval Queue gating",
      "Live workflow resumption",
    ],
  },
  {
    id: "4",
    name: "Shipped Order Cancellation Rejection",
    category: "Policy & Exceptions",
    description:
      "Attempts to cancel an already dispatched order, pauses for supervisor review, simulates rejection under POL-CAN-001, and verifies order state remains intact in SHIPPED.",
    testedMechanisms: [
      "In-transit cancellation protection",
      "Policy rule POL-CAN-001",
      "Supervisor rejection workflow",
      "Database state invariance",
    ],
  },
  {
    id: "5",
    name: "Duplicate Request Protection (Idempotency)",
    category: "Resilience",
    description:
      "Dispatches two identical refund requests concurrently using the same idempotency key. Proves that the second request returns cached response without duplicate refunds or payments.",
    testedMechanisms: [
      "Idempotency cache layer",
      "Distributed lock / conflict guard",
      "Duplicate mutation prevention",
    ],
  },
  {
    id: "6",
    name: "Payment Failure & Safe Exception State",
    category: "Payments",
    description:
      "Simulates issuer card decline (ERR_CARD_DECLINED). Verifies that the order remains strictly PENDING (never marked PAID), and generates payment failure exception.",
    testedMechanisms: [
      "Gateway failure handling",
      "Safe state invariant (Order stays PENDING)",
      "Payment exception dispatch",
    ],
  },
  {
    id: "7",
    name: "Verification Engine Divergence Detection",
    category: "State Verification",
    description:
      "Simulates tool execution reporting ghost success while database remains unmutated. Verification engine inspects state, detects discrepancy, and halts false report.",
    testedMechanisms: [
      "State verification engine",
      "Ghost success detection",
      "Audit alert generation",
    ],
  },
];

interface ScenarioRunResult {
  scenario_id: string;
  name: string;
  success: boolean;
  summary: string;
  timeline: string[];
  entities: Record<string, any>;
}

export default function ScenariosPage() {
  const [runningId, setRunningId] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, ScenarioRunResult>>({});
  const [error, setError] = useState<string | null>(null);

  const handleRunScenario = async (scenarioId: string) => {
    try {
      setRunningId(scenarioId);
      setError(null);
      const res = await fetch(`${API_BASE_URL}/operations/scenarios/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario_id: scenarioId }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Scenario execution failed");
      }

      const data: ScenarioRunResult = await res.json();
      setResults((prev) => ({ ...prev, [scenarioId]: data }));
    } catch (err: any) {
      setError(`Scenario ${scenarioId} error: ${err.message}`);
    } finally {
      setRunningId(null);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <PlayCircle className="h-5 w-5 text-zinc-400" />
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">Operations Scenarios</h1>
            <span className="text-xs font-mono text-zinc-500 tabular-nums">({SCENARIOS.length})</span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            End-to-end verification tests demonstrating deterministic policies, idempotency guards, and state verification.
          </p>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/20 bg-rose-950/10 p-4 text-xs text-rose-300 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Scenarios Grid */}
      <div className="space-y-4">
        {SCENARIOS.map((sc) => {
          const isRunning = runningId === sc.id;
          const result = results[sc.id];

          return (
            <div
              key={sc.id}
              className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-5 space-y-4 hover:border-white/[0.14] transition-colors"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="rounded border border-white/[0.06] bg-white/[0.03] px-2 py-0.5 text-[10px] font-mono text-zinc-400">
                      Scenario #{sc.id}
                    </span>
                    <span className="rounded border border-white/[0.06] bg-white/[0.02] px-2 py-0.5 text-[10px] font-mono text-zinc-300">
                      {sc.category}
                    </span>
                  </div>
                  <h3 className="text-sm font-semibold text-zinc-100">{sc.name}</h3>
                </div>

                <button
                  onClick={() => handleRunScenario(sc.id)}
                  disabled={isRunning}
                  className="inline-flex items-center gap-2 rounded-md border border-white/[0.12] bg-white/[0.06] px-3.5 py-1.5 text-xs font-medium text-zinc-200 hover:bg-white/[0.12] hover:text-white disabled:opacity-40 transition-colors shrink-0"
                >
                  {isRunning ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin text-zinc-400" />
                      <span>Executing Workflow...</span>
                    </>
                  ) : (
                    <>
                      <PlayCircle className="h-3.5 w-3.5 text-zinc-400" />
                      <span>Execute Scenario</span>
                    </>
                  )}
                </button>
              </div>

              <p className="text-xs text-zinc-400 leading-relaxed">{sc.description}</p>

              {/* Tested Mechanisms Pills */}
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <span className="text-[10px] text-zinc-500 uppercase tracking-wider font-mono">Verifies:</span>
                {sc.testedMechanisms.map((mech) => (
                  <span
                    key={mech}
                    className="rounded border border-white/[0.06] bg-[#090a0f] px-2 py-0.5 text-[10px] text-zinc-400 font-mono"
                  >
                    {mech}
                  </span>
                ))}
              </div>

              {/* Run Result Output View */}
              {result && (
                <div className="mt-3 rounded-lg border border-white/[0.08] bg-[#090a0f] p-4 space-y-3">
                  <div className="flex items-center justify-between border-b border-white/[0.06] pb-2">
                    <div className="flex items-center gap-2">
                      {result.success ? (
                        <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                      ) : (
                        <AlertTriangle className="h-4 w-4 text-rose-400" />
                      )}
                      <span
                        className={`text-xs font-semibold ${
                          result.success ? "text-emerald-300" : "text-rose-300"
                        }`}
                      >
                        {result.success
                          ? "Execution Verified Under Policy Constraints"
                          : "State Invariant Divergence Detected"}
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-zinc-300 font-mono">{result.summary}</p>

                  {/* Step Timeline */}
                  <div className="space-y-1.5 pt-1">
                    <div className="text-[10px] font-medium uppercase tracking-wider text-zinc-500 font-mono">
                      Step Execution Trace:
                    </div>
                    {result.timeline.map((step, idx) => (
                      <div
                        key={idx}
                        className="flex items-start gap-2 text-[11px] font-mono text-zinc-300 leading-relaxed"
                      >
                        <span className="text-zinc-500 shrink-0">[{idx + 1}]</span>
                        <span>{step}</span>
                      </div>
                    ))}
                  </div>

                  {/* Entity State Link */}
                  {result.entities && Object.keys(result.entities).length > 0 && (
                    <div className="pt-2 border-t border-white/[0.06] flex flex-wrap gap-2 text-[10px] font-mono">
                      {Object.entries(result.entities).map(([k, v]) => (
                        <span
                          key={k}
                          className="rounded border border-white/[0.06] bg-[#0c0d14] px-2 py-0.5 text-zinc-400"
                        >
                          <span className="text-zinc-500">{k}:</span> {String(v)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
