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
const STATUS_FILTERS = [
  "ALL",
  "LABEL_CREATED",
  "PICKED_UP",
  "IN_TRANSIT",
  "OUT_FOR_DELIVERY",
  "DELIVERED",
  "DELAYED",
  "FAILED_DELIVERY",
  "RETURNED_TO_ORIGIN",
];

export default function ShipmentsPage() {
  const [shipments, setShipments] = useState<ShipmentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCarrier, setSelectedCarrier] = useState("ALL");
  const [selectedStatus, setSelectedStatus] = useState("ALL");
  const [delayedOnly, setDelayedOnly] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 15;
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const loadShipments = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      let query = `/shipments?limit=${pageSize}&offset=${page * pageSize}`;
      if (selectedCarrier !== "ALL") {
        query += `&carrier=${encodeURIComponent(selectedCarrier)}`;
      }
      if (selectedStatus !== "ALL") {
        query += `&status=${selectedStatus}`;
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
      setError(err.message || "Failed to load logistics records");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, selectedCarrier, selectedStatus, delayedOnly, searchTerm]);

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
      setActionSuccess(`Shipment ${trackingNumber} verified delivered.`);
      loadShipments();
    } catch (err: any) {
      alert(`Error updating delivery status: ${err.message}`);
    }
  };

  const getStatusBadge = (st: string) => {
    switch (st) {
      case "DELIVERED":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
      case "IN_TRANSIT":
      case "OUT_FOR_DELIVERY":
        return "bg-sky-500/10 text-sky-400 border-sky-500/20";
      case "DELAYED":
        return "bg-rose-500/10 text-rose-400 border-rose-500/20";
      case "FAILED_DELIVERY":
      case "RETURNED_TO_ORIGIN":
        return "bg-orange-500/10 text-orange-400 border-orange-500/20";
      default:
        return "bg-slate-800 text-slate-300 border-slate-700";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Truck className="h-6 w-6 text-sky-400" />
            Logistics &amp; Fulfillment
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Carrier tracking, hub departures, estimated ETAs, SLA delay tracking, and delivery confirmations.
          </p>
        </div>

        <button
          onClick={loadShipments}
          disabled={loading}
          className="self-start sm:self-auto flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-800 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-sky-400" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {actionSuccess && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/20 p-3 text-xs text-emerald-400 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* Filter and Controls */}
      <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4">
        {/* Carriers & Delayed Toggle */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 lg:pb-0 scrollbar-thin">
          <button
            onClick={() => {
              setDelayedOnly(!delayedOnly);
              setPage(0);
            }}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold flex items-center gap-1.5 border transition-colors shrink-0 ${
              delayedOnly
                ? "bg-rose-500/20 text-rose-400 border-rose-500/40"
                : "bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200"
            }`}
          >
            <Clock className="h-3.5 w-3.5" />
            <span>Delayed Only</span>
          </button>

          {CARRIER_FILTERS.map((c) => (
            <button
              key={c}
              onClick={() => {
                setSelectedCarrier(c);
                setPage(0);
              }}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors shrink-0 ${
                selectedCarrier === c
                  ? "bg-sky-500 text-white font-semibold"
                  : "bg-slate-900 text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              }`}
            >
              {c}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative w-full lg:w-80">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search tracking #, order ID..."
            className="w-full rounded-lg border border-slate-800 bg-slate-900/80 pl-9 pr-4 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden shadow">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 bg-slate-900/80 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-4 py-3">Tracking Number</th>
                <th className="px-4 py-3">Carrier</th>
                <th className="px-4 py-3">Order Link</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Estimated ETA</th>
                <th className="px-4 py-3">Logistics Diagnostics</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {loading && shipments.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    <RefreshCw className="mx-auto h-6 w-6 animate-spin text-sky-400 mb-2" />
                    Loading logistics records...
                  </td>
                </tr>
              ) : shipments.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    No shipments match the filter criteria.
                  </td>
                </tr>
              ) : (
                shipments.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="px-4 py-3 font-mono font-semibold text-sky-400">
                      {s.tracking_number}
                    </td>
                    <td className="px-4 py-3 font-semibold text-slate-200">{s.carrier}</td>
                    <td className="px-4 py-3 font-mono text-slate-400">
                      <Link href={`/orders/${s.order_id}`} className="hover:underline text-sky-400">
                        Order #{s.order_id.slice(0, 8)}...
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-semibold ${getStatusBadge(
                          s.status
                        )}`}
                      >
                        {s.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                      {s.estimated_delivery_date
                        ? new Date(s.estimated_delivery_date).toLocaleDateString("en-IN", {
                            month: "short",
                            day: "numeric",
                          })
                        : "Pending ETA"}
                    </td>
                    <td className="px-4 py-3">
                      {s.delay_reason ? (
                        <div className="flex items-center gap-1.5 text-rose-400">
                          <AlertTriangle className="h-3 w-3 shrink-0" />
                          <span className="text-[11px] font-medium">{s.delay_reason}</span>
                        </div>
                      ) : s.status === "DELIVERED" ? (
                        <span className="text-emerald-400 text-[11px]">
                          Delivered on{" "}
                          {s.actual_delivery_date
                            ? new Date(s.actual_delivery_date).toLocaleDateString("en-IN", {
                                month: "short",
                                day: "numeric",
                              })
                            : "record"}
                        </span>
                      ) : (
                        <span className="text-slate-500 text-[11px]">On Schedule</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {s.status !== "DELIVERED" && (
                        <button
                          onClick={() => handleConfirmDelivery(s.id, s.tracking_number)}
                          className="inline-flex items-center gap-1 rounded bg-slate-800 px-2 py-1 text-[11px] font-medium text-emerald-400 hover:bg-emerald-950/60 border border-emerald-900/40 transition-colors"
                        >
                          <CheckCircle2 className="h-3 w-3" />
                          <span>Confirm Delivery</span>
                        </button>
                      )}
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
            Showing <span className="font-semibold text-white">{shipments.length}</span> of{" "}
            <span className="font-semibold text-white">{total}</span> shipments
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
    </div>
  );
}

