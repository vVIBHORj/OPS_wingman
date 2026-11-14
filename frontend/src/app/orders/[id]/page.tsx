"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  CreditCard,
  Truck,
  User,
  MapPin,
  Calendar,
  AlertTriangle,
  RefreshCw,
  Ban,
  CheckCircle2,
  Package,
  Clock,
  ChevronRight,
  ShieldAlert,
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

const statusConfig: Record<string, { label: string; dot: string; badge: string }> = {
  DELIVERED: {
    label: "Delivered",
    dot: "bg-emerald-400",
    badge: "border-emerald-500/20 bg-emerald-500/10 text-emerald-300",
  },
  SHIPPED: {
    label: "In Transit",
    dot: "bg-sky-400",
    badge: "border-sky-500/20 bg-sky-500/10 text-sky-300",
  },
  PROCESSING: {
    label: "Processing",
    dot: "bg-amber-400",
    badge: "border-amber-500/20 bg-amber-500/10 text-amber-300",
  },
  CONFIRMED: {
    label: "Confirmed",
    dot: "bg-blue-400",
    badge: "border-blue-500/20 bg-blue-500/10 text-blue-300",
  },
  CANCELLED: {
    label: "Cancelled",
    dot: "bg-rose-400",
    badge: "border-rose-500/20 bg-rose-500/10 text-rose-300",
  },
  PENDING: {
    label: "Pending",
    dot: "bg-zinc-400",
    badge: "border-zinc-700 bg-zinc-800 text-zinc-300",
  },
};

export default function OrderDetailPage() {
  const params = useParams();
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
      setActionMessage("Order successfully cancelled under strict operations protocol.");
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
      maximumFractionDigits: 0,
    }).format(val);
  };

  if (loading && !order) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-3 text-zinc-400">
        <RefreshCw className="h-6 w-6 animate-spin text-zinc-500" />
        <p className="text-xs font-mono">Loading order record...</p>
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="rounded-xl border border-rose-500/20 bg-rose-950/10 p-8 text-center max-w-lg mx-auto mt-12">
        <AlertTriangle className="mx-auto h-8 w-8 text-rose-400 mb-3" />
        <h3 className="text-sm font-semibold text-zinc-100">Order Not Located</h3>
        <p className="text-xs text-zinc-400 mt-1 mb-5">{error || "Could not retrieve order details from ledger."}</p>
        <Link
          href="/orders"
          className="inline-flex items-center gap-2 rounded-md border border-white/[0.08] bg-zinc-900 px-3.5 py-1.5 text-xs font-medium text-zinc-200 hover:bg-zinc-800 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Return to Orders</span>
        </Link>
      </div>
    );
  }

  const statusStyle = statusConfig[order.status] || {
    label: order.status,
    dot: "bg-zinc-400",
    badge: "border-zinc-700 bg-zinc-800 text-zinc-300",
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Breadcrumb & Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-zinc-400 mb-1">
            <Link href="/orders" className="hover:text-zinc-200 transition-colors flex items-center gap-1">
              <ArrowLeft className="h-3 w-3" /> Orders
            </Link>
            <ChevronRight className="h-3 w-3 text-zinc-600" />
            <span className="font-mono text-zinc-300">{order.order_number}</span>
          </div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-zinc-100 font-mono tracking-tight">{order.order_number}</h1>
            <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${statusStyle.badge}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${statusStyle.dot}`} />
              {statusStyle.label}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {order.status !== "CANCELLED" && order.status !== "DELIVERED" && (
            <button
              onClick={() => setShowCancelModal(true)}
              className="inline-flex items-center gap-1.5 rounded-md border border-rose-500/25 bg-rose-500/10 px-3 py-1.5 text-xs font-medium text-rose-300 hover:bg-rose-500/15 hover:border-rose-500/40 transition-colors"
            >
              <Ban className="h-3.5 w-3.5" />
              <span>Cancel Order</span>
            </button>
          )}
        </div>
      </div>

      {actionMessage && (
        <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/10 p-3.5 text-xs text-emerald-300 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
          <span>{actionMessage}</span>
        </div>
      )}

      {/* Main 2-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left (Line Items, Shipments, Totals) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Order Items Table */}
          <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] overflow-hidden">
            <div className="p-4 border-b border-white/[0.06] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Package className="h-4 w-4 text-zinc-400" />
                <h3 className="text-xs font-semibold text-zinc-100 tracking-wide">Line Items</h3>
              </div>
              <span className="text-[11px] text-zinc-400 tabular-nums">
                {order.items?.length || 0} {order.items?.length === 1 ? "item" : "items"}
              </span>
            </div>

            <div className="divide-y divide-white/[0.06]">
              {order.items && order.items.length > 0 ? (
                order.items.map((item) => (
                  <div key={item.id} className="p-4 flex items-center justify-between gap-4 hover:bg-white/[0.01] transition-colors">
                    <div className="min-w-0">
                      <div className="text-xs font-medium text-zinc-200">{item.product_name}</div>
                      <div className="text-[11px] font-mono text-zinc-400 mt-0.5 flex items-center gap-2">
                        <span>SKU: {item.sku}</span>
                        <span className="text-zinc-700">•</span>
                        <span>Qty: {item.quantity}</span>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-xs font-mono font-medium text-zinc-100 tabular-nums">{formatInr(item.total_price)}</div>
                      <div className="text-[11px] font-mono text-zinc-400 tabular-nums">{formatInr(item.unit_price)} each</div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-6 text-center text-xs text-zinc-400">No items recorded in this order.</div>
              )}
            </div>

            {/* Financial Ledger Breakdown */}
            <div className="border-t border-white/[0.08] bg-[#0a0b10] p-4 space-y-2 text-xs">
              <div className="flex justify-between text-zinc-400">
                <span>Subtotal</span>
                <span className="font-mono tabular-nums text-zinc-300">
                  {formatInr(order.subtotal_amount ?? order.subtotal ?? 0)}
                </span>
              </div>
              <div className="flex justify-between text-zinc-400">
                <span>GST Tax</span>
                <span className="font-mono tabular-nums text-zinc-300">{formatInr(order.tax_amount || 0)}</span>
              </div>
              <div className="flex justify-between text-zinc-400">
                <span>Fulfillment &amp; Shipping</span>
                <span className="font-mono tabular-nums text-zinc-300">{formatInr(order.shipping_amount || 0)}</span>
              </div>
              {order.discount_amount > 0 && (
                <div className="flex justify-between text-emerald-400">
                  <span>Applied Promotional Discount</span>
                  <span className="font-mono tabular-nums">-{formatInr(order.discount_amount)}</span>
                </div>
              )}
              <div className="flex justify-between text-xs font-semibold text-zinc-100 pt-2.5 border-t border-white/[0.08]">
                <span>Total Amount</span>
                <span className="font-mono tabular-nums text-sm text-zinc-50">{formatInr(order.total_amount)}</span>
              </div>
            </div>
          </div>

          {/* Fulfillment & Logistics */}
          <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-4">
            <div className="flex items-center justify-between mb-3 pb-3 border-b border-white/[0.06]">
              <div className="flex items-center gap-2">
                <Truck className="h-4 w-4 text-zinc-400" />
                <h3 className="text-xs font-semibold text-zinc-100 tracking-wide">Fulfillment &amp; Shipments</h3>
              </div>
              <span className="text-[11px] text-zinc-400 tabular-nums">
                {order.shipments?.length || 0} parcels
              </span>
            </div>

            {order.shipments && order.shipments.length > 0 ? (
              <div className="space-y-2.5">
                {order.shipments.map((s) => (
                  <div
                    key={s.id}
                    className="rounded-lg border border-white/[0.06] bg-[#090a0f] p-3.5 flex items-center justify-between text-xs"
                  >
                    <div>
                      <div className="font-medium text-zinc-200">{s.carrier}</div>
                      <div className="font-mono text-[11px] text-zinc-400 mt-0.5">
                        Waybill: <span className="text-zinc-300">{s.tracking_number}</span>
                      </div>
                      {s.estimated_delivery_date && (
                        <div className="text-[11px] text-zinc-400 mt-1 flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          Est. Delivery: {new Date(s.estimated_delivery_date).toLocaleDateString("en-IN")}
                        </div>
                      )}
                    </div>
                    <span className="rounded border border-white/[0.08] bg-white/[0.04] px-2 py-0.5 text-[10px] font-mono uppercase text-zinc-300">
                      {s.status}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-zinc-400 py-3">No shipments or tracking manifests registered for this order yet.</p>
            )}
          </div>
        </div>

        {/* Right (Customer, Destination, Payment Ledger) */}
        <div className="space-y-6">
          {/* Customer Metadata Card */}
          <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-4 space-y-4">
            <div>
              <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-400 uppercase tracking-wider mb-2">
                <User className="h-3.5 w-3.5 text-zinc-400" />
                Customer Account
              </div>
              <Link
                href={`/customers/${order.customer_id}`}
                className="font-mono text-xs text-zinc-200 hover:text-white underline underline-offset-4 decoration-zinc-700 hover:decoration-zinc-400 transition-colors"
              >
                {order.customer_id}
              </Link>
            </div>

            <div className="pt-3 border-t border-white/[0.06]">
              <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-400 uppercase tracking-wider mb-2">
                <MapPin className="h-3.5 w-3.5 text-zinc-400" />
                Delivery Address
              </div>
              <p className="text-xs text-zinc-300 leading-relaxed font-sans">
                {order.shipping_address_line1 || order.shipping_address?.address_line1 || "Standard address on profile"}
                {order.shipping_address_line2 ? `, ${order.shipping_address_line2}` : ""}
                <br />
                {order.shipping_city || order.shipping_address?.city || ""},{" "}
                {order.shipping_state || order.shipping_address?.state || ""}{" "}
                <span className="font-mono">{order.shipping_pincode || order.shipping_address?.postal_code || ""}</span>
                <br />
                {order.shipping_country || order.shipping_address?.country || "India"}
              </p>
            </div>

            <div className="pt-3 border-t border-white/[0.06]">
              <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-400 uppercase tracking-wider mb-1.5">
                <Calendar className="h-3.5 w-3.5 text-zinc-400" />
                Timeline
              </div>
              <div className="text-[11px] text-zinc-400 space-y-1 font-mono">
                <div>Placed: {new Date(order.created_at).toLocaleString("en-IN")}</div>
                <div>Updated: {new Date(order.updated_at).toLocaleString("en-IN")}</div>
              </div>
            </div>
          </div>

          {/* Payment Card */}
          <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-4">
            <div className="flex items-center justify-between mb-3 pb-3 border-b border-white/[0.06]">
              <div className="flex items-center gap-2">
                <CreditCard className="h-4 w-4 text-zinc-400" />
                <h3 className="text-xs font-semibold text-zinc-100 tracking-wide">Payment Records</h3>
              </div>
              <span className="text-[11px] text-zinc-400 tabular-nums">
                {order.payments?.length || 0}
              </span>
            </div>

            {order.payments && order.payments.length > 0 ? (
              <div className="space-y-2.5">
                {order.payments.map((p) => (
                  <div
                    key={p.id}
                    className="rounded-lg border border-white/[0.06] bg-[#090a0f] p-3 text-xs"
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-mono text-[11px] font-medium text-zinc-300 uppercase">
                        {p.payment_method}
                      </span>
                      <span className="font-mono tabular-nums font-semibold text-zinc-100">
                        {formatInr(p.amount)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-zinc-400">
                      <span className="font-mono text-zinc-400 truncate max-w-[140px]">{p.payment_reference}</span>
                      <span className="rounded border border-emerald-500/20 bg-emerald-500/10 text-emerald-300 px-1.5 py-0.5 text-[9px] font-mono uppercase">
                        {p.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-zinc-400 py-3">No payments recorded for this order.</p>
            )}
          </div>
        </div>
      </div>

      {/* Cancellation Modal */}
      {showCancelModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-xl border border-white/[0.12] bg-[#0c0d14] p-6 space-y-4 shadow-2xl">
            <div className="flex items-center gap-2.5 text-rose-300">
              <ShieldAlert className="h-5 w-5" />
              <h3 className="text-sm font-semibold text-zinc-100">Cancel Order {order.order_number}</h3>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Cancellation triggers deterministic state machine validation. If the order has already entered dispatch or carrier lock, this action will require supervisor intervention.
            </p>
            <div>
              <label className="block text-[11px] font-medium text-zinc-400 uppercase tracking-wider mb-1.5">
                Reason for cancellation
              </label>
              <textarea
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                placeholder="e.g., Customer requested pre-shipment cancellation via ticket #..."
                className="w-full rounded-lg border border-white/[0.08] bg-[#090a0f] p-3 text-xs text-zinc-200 placeholder-zinc-600 focus:border-zinc-500 focus:outline-none transition-colors"
                rows={3}
              />
            </div>
            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-white/[0.06]">
              <button
                onClick={() => setShowCancelModal(false)}
                className="rounded-md px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
              >
                Dismiss
              </button>
              <button
                onClick={handleCancelOrder}
                disabled={cancelling || !cancelReason.trim()}
                className="rounded-md bg-rose-500/20 border border-rose-500/30 px-3.5 py-1.5 text-xs font-medium text-rose-300 hover:bg-rose-500/30 transition-colors disabled:opacity-40"
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
