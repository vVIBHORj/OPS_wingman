"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Truck,
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ExternalLink,
} from "lucide-react";
import { fetchJson, API_BASE_URL } from "@/lib/api";

interface ShipmentItem {
  id: string;
  order_id: string;
  shipment_number: string;
  carrier: string;
  tracking_number: string;
  status: string;
  shipped_at?: string;
  estimated_delivery_date?: string;
  actual_delivery_date?: string;
  delay_reason?: string;
  created_at: string;
}

interface ShipmentListResponse {
  total: number;
  limit: number;
  offset: number;
  items: ShipmentItem[];
  shipments?: ShipmentItem[];
}

const CARRIER_FILTERS = ["ALL", "Delhivery", "BlueDart", "DTDC", "Xpressbees", "Shadowfax"];

const statusConfig: Record<string, { label: string; dot: string; badge: string }> = {
  DELIVERED: {
    label: "Delivered",
    dot: "bg-emerald-400",
    badge: "border-emerald-500/20 bg-emerald-500/10 text-emerald-300",
  },
  IN_TRANSIT: {
    label: "In Transit",
    dot: "bg-sky-400",
    badge: "border-sky-500/20 bg-sky-500/10 text-sky-300",
  },
  OUT_FOR_DELIVERY: {
    label: "Out for Delivery",
    dot: "bg-sky-400",
    badge: "border-sky-500/20 bg-sky-500/10 text-sky-300",
  },
  DELAYED: {
    label: "Delayed",
    dot: "bg-rose-400",
    badge: "border-rose-500/20 bg-rose-500/10 text-rose-300",
  },
  FAILED_DELIVERY: {
    label: "Failed Delivery",
    dot: "bg-amber-400",
    badge: "border-amber-500/20 bg-amber-500/10 text-amber-300",
  },
  RETURNED_TO_ORIGIN: {
    label: "RTO",
    dot: "bg-purple-400",
    badge: "border-purple-500/20 bg-purple-500/10 text-purple-300",
  },
  PICKED_UP: {
    label: "Picked Up",
    dot: "bg-blue-400",
    badge: "border-blue-500/20 bg-blue-500/10 text-blue-300",
  },
  LABEL_CREATED: {
    label: "Manifested",
    dot: "bg-zinc-400",
    badge: "border-zinc-700 bg-zinc-800 text-zinc-300",
  },
};

export default function ShipmentsPage() {
  const [shipments, setShipments] = useState<ShipmentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedCarrier, setSelectedCarrier] = useState("ALL");
  const [delayedOnly, setDelayedOnly] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 15;
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const loadShipments = useCallback(async () => {
    try {
      setLoading(true);
      let query = `/shipments?limit=${pageSize}&offset=${page * pageSize}`;
      if (selectedCarrier !== "ALL") {
        query += `&carrier=${encodeURIComponent(selectedCarrier)}`;
      }
      if (delayedOnly) {
        query += `&is_delayed=true`;
      }
      if (searchTerm.trim()) {
        query += `&search=${encodeURIComponent(searchTerm.trim())}`;
      }

      const res = await fetchJson<ShipmentListResponse>(query);
      setShipments(res.items || res.shipments || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      console.error("Failed to load shipments:", err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, selectedCarrier, delayedOnly, searchTerm]);

  useEffect(() => {
    loadShipments();
  }, [loadShipments]);

  const handleConfirmDelivery = async (shipmentId: string, trackingNumber: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/shipments/${shipmentId}/deliver`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Delivery confirmation failed");
      }
      setActionSuccess(`Shipment ${trackingNumber} verified as delivered.`);
      loadShipments();
    } catch (err: any) {
      alert(`Error updating delivery status: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <Truck className="h-5 w-5 text-zinc-400" />
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">Logistics &amp; Shipments</h1>
            <span className="text-xs font-mono text-zinc-500 tabular-nums">({total})</span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Waybill tracking, carrier performance, SLA delay detection, and physical proof-of-delivery records.
          </p>
        </div>

        <button
          onClick={loadShipments}
          disabled={loading}
          className="self-start sm:self-auto inline-flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-[#0c0d14] px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-zinc-400" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {actionSuccess && (
        <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/10 p-3.5 text-xs text-emerald-300 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0 scrollbar-none">
          <button
            onClick={() => {
              setDelayedOnly(!delayedOnly);
              setPage(0);
            }}
            className={`rounded-md px-2.5 py-1 text-xs font-medium flex items-center gap-1.5 border transition-colors shrink-0 ${
              delayedOnly
                ? "bg-rose-500/15 text-rose-300 border-rose-500/30"
                : "border border-white/[0.06] bg-[#0c0d14] text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Clock className="h-3 w-3" />
            <span>Delayed Only</span>
          </button>

          {CARRIER_FILTERS.map((c) => {
            const isSelected = selectedCarrier === c;
            return (
              <button
                key={c}
                onClick={() => {
                  setSelectedCarrier(c);
                  setPage(0);
                }}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors shrink-0 ${
                  isSelected
                    ? "bg-white/[0.12] text-zinc-100 border border-white/[0.16]"
                    : "border border-white/[0.06] bg-[#0c0d14] text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60"
                }`}
              >
                {c}
              </button>
            );
          })}
        </div>

        {/* Search */}
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search tracking #, order ID..."
            className="w-full rounded-md border border-white/[0.08] bg-[#0c0d14] pl-9 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-400 focus:border-zinc-500 focus:outline-none transition-colors"
          />
        </div>
      </div>

      {/* Shipment Table */}
      <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-white/[0.06] bg-[#0a0b10] text-[11px] font-medium text-zinc-400 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3">Tracking / Waybill</th>
                <th className="px-4 py-3">Carrier</th>
                <th className="px-4 py-3">Linked Order</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Estimated ETA</th>
                <th className="px-4 py-3">Exceptions / Notes</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.06] text-zinc-300">
              {loading && shipments.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-zinc-500 font-mono text-xs">
                    <RefreshCw className="mx-auto h-5 w-5 animate-spin text-zinc-600 mb-2" />
                    Querying logistics networks...
                  </td>
                </tr>
              ) : shipments.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-zinc-500 text-xs">
                    No shipments match the current criteria.
                  </td>
                </tr>
              ) : (
                shipments.map((s) => {
                  const style = statusConfig[s.status] || {
                    label: s.status,
                    dot: "bg-zinc-400",
                    badge: "border-zinc-700 bg-zinc-800 text-zinc-300",
                  };

                  return (
                    <tr key={s.id} className="hover:bg-white/[0.02] transition-colors">
                      <td className="px-4 py-3 font-mono font-medium text-zinc-200">
                        {s.tracking_number}
                      </td>
                      <td className="px-4 py-3 font-medium text-zinc-300">
                        {s.carrier}
                      </td>
                      <td className="px-4 py-3 font-mono text-[11px]">
                        <Link
                          href={`/orders/${s.order_id}`}
                          className="text-zinc-300 hover:text-white inline-flex items-center gap-1 hover:underline underline-offset-2 transition-colors"
                        >
                          <span>#{s.order_id.slice(0, 8)}</span>
                          <ExternalLink className="h-3 w-3 text-zinc-500" />
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-medium ${style.badge}`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
                          {style.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-zinc-400 whitespace-nowrap text-[11px] font-mono">
                        {s.estimated_delivery_date
                          ? new Date(s.estimated_delivery_date).toLocaleDateString("en-IN", {
                              month: "short",
                              day: "numeric",
                            })
                          : "Pending ETA"}
                      </td>
                      <td className="px-4 py-3 text-zinc-400 text-[11px]">
                        {s.delay_reason ? (
                          <div className="flex items-center gap-1.5 text-rose-400">
                            <AlertTriangle className="h-3 w-3 shrink-0" />
                            <span className="font-medium text-rose-300/90">{s.delay_reason}</span>
                          </div>
                        ) : s.status === "DELIVERED" ? (
                          <span className="text-emerald-400/90 text-[11px]">
                            Delivered on{" "}
                            {s.actual_delivery_date
                              ? new Date(s.actual_delivery_date).toLocaleDateString("en-IN", {
                                  month: "short",
                                  day: "numeric",
                                })
                              : "record"}
                          </span>
                        ) : (
                          <span className="text-zinc-500">On Track</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {s.status !== "DELIVERED" && (
                          <button
                            onClick={() => handleConfirmDelivery(s.id, s.tracking_number)}
                            className="inline-flex items-center gap-1 rounded border border-emerald-500/25 bg-emerald-500/10 px-2 py-1 text-[11px] font-medium text-emerald-300 hover:bg-emerald-500/20 transition-colors"
                          >
                            <CheckCircle2 className="h-3 w-3" />
                            <span>Confirm Delivery</span>
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between border-t border-white/[0.06] bg-[#0a0b10] px-4 py-3 text-xs text-zinc-400">
          <div>
            Showing <span className="font-mono text-zinc-200 tabular-nums">{shipments.length}</span> of{" "}
            <span className="font-mono text-zinc-200 tabular-nums">{total}</span> shipments
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
    </div>
  );
}
