"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  PlayCircle,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  ShieldAlert,
  Clock,
  RotateCcw,
  Ban,
  Search,
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
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <div className="border-b border-slate-800 pb-5">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-600 text-white shadow">
            <PlayCircle className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">
              Operations Scenario Runner
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Live end-to-end demonstrations of deterministic policies, state verification, idempotency, and supervisor gating.
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 p-4 text-xs text-rose-300 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Scenarios Grid */}
      <div className="grid grid-cols-1 gap-5">
        {SCENARIOS.map((sc) => {
          const isRunning = runningId === sc.id;
          const result = results[sc.id];

          return (
            <div
              key={sc.id}
              className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 space-y-4 hover:border-slate-700 transition-colors"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] font-mono text-slate-400">
                      Scenario #{sc.id}
                    </span>
                    <span className="rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 px-2 py-0.5 text-[10px] font-semibold">
                      {sc.category}
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-white mt-1">{sc.name}</h3>
                </div>

                <button
                  onClick={() => handleRunScenario(sc.id)}
                  disabled={isRunning}
                  className="flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-xs font-semibold text-white hover:bg-sky-500 disabled:opacity-50 transition-colors shrink-0"
                >
                  {isRunning ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                      <span>Executing Workflow...</span>
                    </>
                  ) : (
                    <>
                      <PlayCircle className="h-4 w-4" />
                      <span>Run Scenario</span>
                    </>
                  )}
                </button>
              </div>

              <p className="text-xs text-slate-300 leading-relaxed">{sc.description}</p>

              {/* Tested Mechanisms Pills */}
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <span className="text-[10px] text-slate-500 uppercase font-semibold">Verifies:</span>
                {sc.testedMechanisms.map((mech) => (
                  <span
                    key={mech}
                    className="rounded-md border border-slate-800 bg-slate-950 px-2 py-0.5 text-[10px] text-slate-400 font-mono"
                  >
                    {mech}
                  </span>
                ))}
              </div>

              {/* Run Result Output View */}
              {result && (
                <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/80 p-4 space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                    <div className="flex items-center gap-2">
                      {result.success ? (
                        <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                      ) : (
                        <AlertTriangle className="h-4 w-4 text-rose-400" />
                      )}
                      <span
                        className={`text-xs font-bold ${
                          result.success ? "text-emerald-400" : "text-rose-400"
                        }`}
                      >
                        {result.success
                          ? "Scenario Completed & Invariants Verified"
                          : "Execution Invariant Divergence"}
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-slate-300 font-medium">{result.summary}</p>

                  {/* Step Timeline */}
                  <div className="space-y-1.5 pt-1">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                      Execution Step Timeline:
                    </div>
                    {result.timeline.map((step, idx) => (
                      <div
                        key={idx}
                        className="flex items-center gap-2 text-xs font-mono text-slate-300"
                      >
                        <span className="text-sky-400">[{idx + 1}]</span>
                        <span>{step}</span>
                      </div>
                    ))}
                  </div>

                  {/* Entity State Link */}
                  {result.entities && Object.keys(result.entities).length > 0 && (
                    <div className="pt-2 border-t border-slate-800/60 flex flex-wrap gap-2 text-[11px] font-mono">
                      {Object.entries(result.entities).map(([k, v]) => (
                        <span
                          key={k}
                          className="rounded bg-slate-900 border border-slate-800 px-2 py-0.5 text-slate-400"
                        >
                          <strong className="text-slate-300">{k}:</strong> {String(v)}
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

