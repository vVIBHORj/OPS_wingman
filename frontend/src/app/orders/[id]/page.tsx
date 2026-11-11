"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  ShoppingCart,
  CreditCard,
  Truck,
  User,
  MapPin,
  Calendar,
  AlertTriangle,
  RefreshCw,
  Ban,
  CheckCircle2,
} from "lucide-react";
import { fetchJson, API_BASE_URL } from "@/lib/api";

interface OrderItemDetail {
  id: string;
  sku: string;
  product_name: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

interface OrderDetail {
  id: string;
  order_number: string;
  customer_id: string;
  status: string;
  currency: string;
  subtotal?: number;
  subtotal_amount: number;
  tax_amount: number;
  shipping_amount: number;
  discount_amount: number;
  total_amount: number;
  shipping_address_line1?: string;
  shipping_address_line2?: string;
  shipping_city?: string;
  shipping_state?: string;
  shipping_pincode?: string;
  shipping_country?: string;
  shipping_address?: Record<string, any>;
  billing_address?: Record<string, any>;
  created_at: string;
  updated_at: string;
  items: OrderItemDetail[];
  payments: Array<{
    id: string;
    payment_reference: string;
    amount: number;
    status: string;
    payment_method: string;
    created_at: string;
  }>;
  shipments: Array<{
    id: string;
    carrier: string;
    tracking_number: string;
    status: string;
    shipped_at?: string;
    estimated_delivery_date?: string;
  }>;
}

export default function OrderDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params?.id as string;

  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const loadOrder = useCallback(async () => {
    if (!id) return;
    try {
      setLoading(true);
      setError(null);
      const data = await fetchJson<OrderDetail>(`/orders/${id}`);
      setOrder(data);
    } catch (err: any) {
      setError(err.message || "Failed to load order");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadOrder();
  }, [loadOrder]);

  const handleCancelOrder = async () => {
    if (!cancelReason.trim()) return;
    try {
      setCancelling(true);
      const res = await fetch(`${API_BASE_URL}/orders/${id}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: cancelReason }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Cancellation failed");
      }
      setActionMessage("Order successfully cancelled.");
      setShowCancelModal(false);
      loadOrder();
    } catch (err: any) {
      alert(`Error cancelling order: ${err.message}`);
    } finally {
      setCancelling(false);
    }
  };

  const formatInr = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
    }).format(val);
  };

  if (loading && !order) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-3 text-slate-400">
        <RefreshCw className="h-8 w-8 animate-spin text-sky-400" />
        <p className="text-sm">Loading order details...</p>
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 p-6 text-center">
        <AlertTriangle className="mx-auto h-8 w-8 text-rose-400 mb-2" />
        <h3 className="text-lg font-bold text-rose-200">Order Not Found</h3>
        <p className="text-sm text-slate-400 mt-1">{error || "Could not retrieve order details."}</p>
        <Link
          href="/orders"
          className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-700"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Back to Orders</span>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Top Bar */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <Link
            href="/orders"
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-800 bg-slate-900 text-slate-400 hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-white font-mono">{order.order_number}</h1>
              <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-2.5 py-0.5 text-xs font-semibold text-sky-400">
                {order.status}
              </span>
            </div>
            <p className="text-xs text-slate-400 flex items-center gap-1.5 mt-0.5">
              <Calendar className="h-3 w-3" />
              Placed on {new Date(order.created_at).toLocaleString("en-IN")}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {order.status !== "CANCELLED" && order.status !== "DELIVERED" && (
            <button
              onClick={() => setShowCancelModal(true)}
              className="flex items-center gap-1.5 rounded-lg border border-rose-500/30 bg-rose-950/20 px-3 py-1.5 text-xs font-semibold text-rose-400 hover:bg-rose-950/40"
            >
              <Ban className="h-3.5 w-3.5" />
              <span>Cancel Order</span>
            </button>
          )}
        </div>
      </div>

      {actionMessage && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/20 p-3 text-xs text-emerald-400 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4" />
          <span>{actionMessage}</span>
        </div>
      )}

      {/* Grid: Details & Summaries */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (Line Items & Breakdown) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Line items table */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
            <h3 className="text-sm font-bold text-white mb-3">Order Items</h3>
            <div className="divide-y divide-slate-800/80">
              {order.items.map((item) => (
                <div key={item.id} className="py-3 flex items-center justify-between text-xs">
                  <div>
                    <div className="font-semibold text-slate-200">{item.product_name}</div>
                    <div className="text-[11px] font-mono text-slate-400">SKU: {item.sku}</div>
                    <div className="text-[11px] text-slate-400">Qty: {item.quantity}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-semibold text-white">{formatInr(item.total_price)}</div>
                    <div className="text-[10px] text-slate-400">
                      {formatInr(item.unit_price)} each
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Financial Totals */}
            <div className="mt-4 pt-4 border-t border-slate-800 space-y-1.5 text-xs">
              <div className="flex justify-between text-slate-400">
                <span>Subtotal</span>
                <span>{formatInr(order.subtotal_amount ?? order.subtotal ?? 0)}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Tax Amount (GST)</span>
                <span>{formatInr(order.tax_amount)}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Shipping Fee</span>
                <span>{formatInr(order.shipping_amount)}</span>
              </div>
              {order.discount_amount > 0 && (
                <div className="flex justify-between text-emerald-400">
                  <span>Discount Applied</span>
                  <span>-{formatInr(order.discount_amount)}</span>
                </div>
              )}
              <div className="flex justify-between text-sm font-bold text-white pt-2 border-t border-slate-800">
                <span>Total Amount</span>
                <span className="text-sky-400">{formatInr(order.total_amount)}</span>
              </div>
            </div>
          </div>

          {/* Fulfillment / Shipments */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
            <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
              <Truck className="h-4 w-4 text-sky-400" />
              Connected Logistics &amp; Shipments
            </h3>
            {order.shipments && order.shipments.length > 0 ? (
              <div className="space-y-3">
                {order.shipments.map((s) => (
                  <div
                    key={s.id}
                    className="rounded-lg border border-slate-800 bg-slate-950 p-3.5 flex items-center justify-between text-xs"
                  >
                    <div>
                      <div className="font-semibold text-slate-200">{s.carrier}</div>
                      <div className="font-mono text-sky-400 text-[11px]">
                        Tracking: {s.tracking_number}
                      </div>
                    </div>
                    <span className="rounded-full bg-slate-800 border border-slate-700 px-2.5 py-0.5 text-[10px] font-bold text-slate-300">
                      {s.status}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">No shipments registered for this order yet.</p>
            )}
          </div>
        </div>

        {/* Right Column (Customer, Addresses, Payment) */}
        <div className="space-y-6">
          {/* Customer & Addresses */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 space-y-4">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
                <User className="h-3.5 w-3.5" />
                Customer
              </h3>
              <Link
                href={`/customers/${order.customer_id}`}
                className="font-mono text-xs text-sky-400 hover:underline"
              >
                ID: {order.customer_id}
              </Link>
            </div>

            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1 flex items-center gap-1.5">
                <MapPin className="h-3.5 w-3.5" />
                Shipping Destination
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                {order.shipping_address_line1 || order.shipping_address?.address_line1 || "Address details on file"}
                {order.shipping_address_line2 ? `, ${order.shipping_address_line2}` : ""}
                <br />
                {order.shipping_city || order.shipping_address?.city || ""},{" "}
                {order.shipping_state || order.shipping_address?.state || ""}{" "}
                {order.shipping_pincode || order.shipping_address?.postal_code || ""}
                <br />
                {order.shipping_country || order.shipping_address?.country || "India"}
              </p>
            </div>
          </div>

          {/* Payment Details */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
            <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
              <CreditCard className="h-4 w-4 text-emerald-400" />
              Payment Ledger
            </h3>
            {order.payments && order.payments.length > 0 ? (
              <div className="space-y-3">
                {order.payments.map((p) => (
                  <div
                    key={p.id}
                    className="rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-slate-300 uppercase">{p.payment_method}</span>
                      <span className="font-bold text-white">{formatInr(p.amount)}</span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span className="font-mono">{p.payment_reference}</span>
                      <span className="rounded bg-emerald-500/20 text-emerald-400 px-1.5 py-0.5 text-[9px] font-bold">
                        {p.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">No payment transaction records found.</p>
            )}
          </div>
        </div>
      </div>

      {/* Cancel Modal */}
      {showCancelModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900 p-6 space-y-4">
            <h3 className="text-base font-bold text-white">Cancel Order {order.order_number}</h3>
            <p className="text-xs text-slate-400">
              Provide a verified reason for cancellation. Deterministic business rules will evaluate
              whether order cancellation is permitted for this state.
            </p>
            <textarea
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              placeholder="e.g., Customer requested cancellation prior to carrier handoff..."
              className="w-full rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs text-slate-200 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
              rows={3}
            />
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setShowCancelModal(false)}
                className="rounded-lg px-3 py-1.5 text-xs text-slate-400 hover:text-white"
              >
                Dismiss
              </button>
              <button
                onClick={handleCancelOrder}
                disabled={cancelling || !cancelReason.trim()}
                className="rounded-lg bg-rose-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-rose-500 disabled:opacity-50"
              >
                {cancelling ? "Processing..." : "Confirm Cancellation"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

