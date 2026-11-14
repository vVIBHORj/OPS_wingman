"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  User,
  Mail,
  Phone,
  MapPin,
  Calendar,
  ShoppingBag,
  RefreshCw,
  AlertTriangle,
  ExternalLink,
  ChevronRight,
  TrendingUp,
  Receipt,
  LifeBuoy,
  Clock,
  AlertCircle,
  Building2,
  UserCheck,
} from "lucide-react";
import { fetchJson } from "@/lib/api";

interface OrderItem {
  id: string;
  sku?: string;
  product_name?: string;
  quantity?: number;
  unit_price?: string | number;
  total_price?: string | number;
}

interface CustomerOrder {
  id: string;
  order_number: string;
  status: string;
  total_amount: number | string;
  created_at: string;
  cancellation_reason?: string | null;
  items?: OrderItem[];
}

interface CustomerTicket {
  id: string;
  ticket_number: string;
  customer_id?: string;
  order_id?: string | null;
  title: string;
  description?: string;
  channel?: string;
  status: string;
  priority: string;
  category?: string;
  created_at: string;
  resolved_at?: string | null;
}

interface CustomerDetail {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  company_name?: string | null;
  city?: string;
  state?: string;
  pincode?: string;
  postal_code?: string;
  country?: string;
  created_at: string;
  updated_at?: string;
  order_count: number;
  total_spend: number | string;
  orders?: CustomerOrder[];
  recent_orders?: CustomerOrder[];
  recent_tickets?: CustomerTicket[];
}

interface TimelineItem {
  id: string;
  type: "order" | "ticket" | "account_created";
  timestamp: string;
  title: string;
  subtitle?: string;
  status?: string;
  priority?: string;
  amount?: number;
  linkHref?: string;
  linkLabel?: string;
}

const orderStatusStyles: Record<string, string> = {
  DELIVERED: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  SHIPPED: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  PROCESSING: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  CONFIRMED: "border-blue-500/30 bg-blue-500/10 text-blue-300",
  CANCELLED: "border-rose-500/30 bg-rose-500/10 text-rose-300",
  PENDING: "border-zinc-700 bg-zinc-800 text-zinc-300",
};

const ticketPriorityStyles: Record<string, string> = {
  CRITICAL: "border-rose-500/30 bg-rose-500/10 text-rose-300",
  HIGH: "border-orange-500/30 bg-orange-500/10 text-orange-300",
  MEDIUM: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  LOW: "border-zinc-700 bg-zinc-800 text-zinc-300",
};

const ticketStatusStyles: Record<string, string> = {
  OPEN: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  IN_PROGRESS: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  RESOLVED: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  CLOSED: "border-zinc-700 bg-zinc-800 text-zinc-400",
};

export default function CustomerDetailPage() {
  const params = useParams();
  const id = params?.id as string;

  const [customer, setCustomer] = useState<CustomerDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCustomer = useCallback(async () => {
    if (!id) return;
    try {
      setLoading(true);
      setError(null);
      const data = await fetchJson<CustomerDetail>(`/customers/${id}`);
      setCustomer(data);
    } catch (err: any) {
      setError(err.message || "Failed to load customer profile");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadCustomer();
  }, [loadCustomer]);

  const formatInr = (val: number | string | undefined) => {
    const num = typeof val === "number" ? val : parseFloat(val || "0") || 0;
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(num);
  };

  const orderHistory = useMemo(() => {
    return customer?.recent_orders || customer?.orders || [];
  }, [customer]);

  const ticketHistory = useMemo(() => {
    return customer?.recent_tickets || [];
  }, [customer]);

  const timelineEvents = useMemo(() => {
    if (!customer) return [];
    const events: TimelineItem[] = [];

    // Account creation event
    if (customer.created_at) {
      events.push({
        id: `created-${customer.id}`,
        type: "account_created",
        timestamp: customer.created_at,
        title: "Account Registered",
        subtitle: `Customer onboarded in ${customer.city || "India"}`,
      });
    }

    // Orders
    orderHistory.forEach((o) => {
      const itemsCount = o.items?.length || 1;
      const parsedAmount = typeof o.total_amount === "number" ? o.total_amount : parseFloat(o.total_amount) || 0;
      events.push({
        id: `order-${o.id}`,
        type: "order",
        timestamp: o.created_at,
        title: `Order ${o.order_number}`,
        subtitle: `${itemsCount} item${itemsCount > 1 ? "s" : ""}${
          o.cancellation_reason ? ` • Cancelled: ${o.cancellation_reason}` : ""
        }`,
        status: o.status,
        amount: parsedAmount,
        linkHref: `/orders/${o.id}`,
        linkLabel: "View Order",
      });
    });

    // Support Tickets
    ticketHistory.forEach((t) => {
      events.push({
        id: `ticket-${t.id}`,
        type: "ticket",
        timestamp: t.created_at,
        title: `Ticket ${t.ticket_number}`,
        subtitle: `${t.category ? `[${t.category}] ` : ""}${t.title}`,
        status: t.status,
        priority: t.priority,
        linkHref: `/tickets`,
        linkLabel: "View Tickets",
      });
    });

    // Sort descending by timestamp
    events.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
    return events;
  }, [customer, orderHistory, ticketHistory]);

  if (loading && !customer) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-3 text-zinc-300">
        <RefreshCw className="h-6 w-6 animate-spin text-zinc-400" />
        <p className="text-xs font-mono font-medium">Loading customer profile...</p>
      </div>
    );
  }

  if (error || !customer) {
    return (
      <div className="rounded-xl border border-rose-500/20 bg-rose-950/10 p-8 text-center max-w-lg mx-auto mt-12">
        <AlertTriangle className="mx-auto h-8 w-8 text-rose-400 mb-3" />
        <h3 className="text-sm font-semibold text-zinc-100">Customer Profile Unavailable</h3>
        <p className="text-xs text-zinc-300 mt-1 mb-5">{error || "Customer record could not be loaded."}</p>
        <Link
          href="/customers"
          className="inline-flex items-center gap-2 rounded-md border border-white/[0.08] bg-zinc-900 px-3.5 py-1.5 text-xs font-medium text-zinc-200 hover:bg-zinc-800 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Return to Customers</span>
        </Link>
      </div>
    );
  }

  const lifetimeSpend = typeof customer.total_spend === "number" ? customer.total_spend : parseFloat(customer.total_spend) || 0;
  const avgOrderValue = customer.order_count > 0 ? lifetimeSpend / customer.order_count : 0;
  const postalCode = customer.pincode || customer.postal_code || "";
  const openTicketsCount = ticketHistory.filter((t) => t.status === "OPEN" || t.status === "IN_PROGRESS").length;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header & Breadcrumb */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-zinc-400 mb-1.5">
            <Link href="/customers" className="hover:text-zinc-200 transition-colors flex items-center gap-1">
              <ArrowLeft className="h-3 w-3" /> Customers
            </Link>
            <ChevronRight className="h-3 w-3 text-zinc-500" />
            <span className="font-mono text-zinc-300 font-medium">{customer.id}</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-zinc-800 border border-white/[0.1] text-xs font-semibold text-zinc-100 uppercase tracking-wider">
              {customer.first_name?.[0] || "U"}
              {customer.last_name?.[0] || ""}
            </div>
            <div>
              <h1 className="text-xl font-semibold text-zinc-100 tracking-tight flex items-center gap-2.5">
                <span>
                  {customer.first_name} {customer.last_name}
                </span>
                {customer.city && (
                  <span className="rounded border border-white/[0.12] bg-white/[0.04] px-2 py-0.5 text-xs font-normal text-zinc-300">
                    {customer.city}
                  </span>
                )}
                {openTicketsCount > 0 && (
                  <span className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-300">
                    {openTicketsCount} Active {openTicketsCount === 1 ? "Ticket" : "Tickets"}
                  </span>
                )}
              </h1>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/customers"
            className="inline-flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-[#0c0d14] px-3 py-1.5 text-xs font-medium text-zinc-200 hover:bg-zinc-800 hover:text-white transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Customer Directory</span>
          </Link>
        </div>
      </div>

      {/* Metric Strip (4 Cards) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-4">
          <div className="flex items-center justify-between text-xs font-medium text-zinc-400 mb-2">
            <span>Lifetime Spend</span>
            <TrendingUp className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-xl font-semibold font-mono tracking-tight text-zinc-100 tabular-nums">
            {formatInr(lifetimeSpend)}
          </div>
          <p className="text-xs text-zinc-400 mt-1">Aggregated verified orders</p>
        </div>

        <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-4">
          <div className="flex items-center justify-between text-xs font-medium text-zinc-400 mb-2">
            <span>Order Frequency</span>
            <ShoppingBag className="h-4 w-4 text-zinc-300" />
          </div>
          <div className="text-xl font-semibold font-mono tracking-tight text-zinc-100 tabular-nums">
            {customer.order_count}
          </div>
          <p className="text-xs text-zinc-400 mt-1">Completed checkout cycles</p>
        </div>

        <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-4">
          <div className="flex items-center justify-between text-xs font-medium text-zinc-400 mb-2">
            <span>Average Order Value</span>
            <Receipt className="h-4 w-4 text-zinc-300" />
          </div>
          <div className="text-xl font-semibold font-mono tracking-tight text-zinc-100 tabular-nums">
            {formatInr(avgOrderValue)}
          </div>
          <p className="text-xs text-zinc-400 mt-1">Mean basket per order</p>
        </div>

        <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-4">
          <div className="flex items-center justify-between text-xs font-medium text-zinc-400 mb-2">
            <span>Support Tickets</span>
            <LifeBuoy className="h-4 w-4 text-sky-400" />
          </div>
          <div className="text-xl font-semibold font-mono tracking-tight text-zinc-100 tabular-nums">
            {ticketHistory.length}
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            {openTicketsCount > 0 ? (
              <span className="text-amber-400 font-medium">{openTicketsCount} currently pending</span>
            ) : (
              "All tickets resolved"
            )}
          </p>
        </div>
      </div>

      {/* Main Grid: Left Column (Profile & Tickets) | Right Column (Timeline & Order History) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column */}
        <div className="space-y-6">
          {/* Customer Profile & Contact Card */}
          <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-4 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
              <div className="flex items-center gap-2">
                <User className="h-4 w-4 text-zinc-300" />
                <h3 className="text-xs font-semibold text-zinc-100 uppercase tracking-wider">Contact & Account</h3>
              </div>
            </div>

            <div className="space-y-3.5 text-xs">
              <div>
                <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">Email Address</div>
                <div className="flex items-center gap-2 text-zinc-200">
                  <Mail className="h-3.5 w-3.5 text-zinc-400 shrink-0" />
                  <a href={`mailto:${customer.email}`} className="truncate hover:text-white hover:underline transition-colors">
                    {customer.email}
                  </a>
                </div>
              </div>

              <div>
                <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">Phone Number</div>
                <div className="flex items-center gap-2 text-zinc-200">
                  <Phone className="h-3.5 w-3.5 text-zinc-400 shrink-0" />
                  <span className="font-mono">{customer.phone || "No phone listed"}</span>
                </div>
              </div>

              {customer.company_name && (
                <div>
                  <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">Company / Organization</div>
                  <div className="flex items-center gap-2 text-zinc-200">
                    <Building2 className="h-3.5 w-3.5 text-zinc-400 shrink-0" />
                    <span>{customer.company_name}</span>
                  </div>
                </div>
              )}

              <div>
                <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">Primary Address</div>
                <div className="flex items-start gap-2 text-zinc-200 leading-relaxed">
                  <MapPin className="h-3.5 w-3.5 text-zinc-400 shrink-0 mt-0.5" />
                  <div>
                    {customer.city ? `${customer.city}, ` : ""}
                    {customer.state ? `${customer.state} ` : ""}
                    {postalCode && <span className="font-mono text-zinc-300">({postalCode})</span>}
                    <div className="text-zinc-400 mt-0.5">{customer.country || "India"}</div>
                  </div>
                </div>
              </div>

              <div className="pt-3 border-t border-white/[0.06]">
                <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">Account Created</div>
                <div className="flex items-center gap-2 text-zinc-300 font-mono text-xs">
                  <Calendar className="h-3.5 w-3.5 text-zinc-400" />
                  <span>
                    {new Date(customer.created_at).toLocaleDateString("en-IN", {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Recent Support Tickets Section */}
          <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] overflow-hidden">
            <div className="p-4 border-b border-white/[0.06] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <LifeBuoy className="h-4 w-4 text-sky-400" />
                <h3 className="text-xs font-semibold text-zinc-100 uppercase tracking-wider">Support Tickets</h3>
              </div>
              <span className="text-xs font-mono font-medium text-zinc-400">
                {ticketHistory.length} recorded
              </span>
            </div>

            <div className="divide-y divide-white/[0.06]">
              {ticketHistory.length > 0 ? (
                ticketHistory.map((t) => {
                  const prioStyle = ticketPriorityStyles[t.priority] || "border-zinc-700 bg-zinc-800 text-zinc-300";
                  const statStyle = ticketStatusStyles[t.status] || "border-zinc-700 bg-zinc-800 text-zinc-300";

                  return (
                    <div key={t.id} className="p-4 space-y-2 hover:bg-white/[0.01] transition-colors">
                      <div className="flex items-center justify-between gap-2">
                        <Link
                          href="/tickets"
                          className="font-mono text-xs font-medium text-zinc-200 hover:text-white flex items-center gap-1.5 transition-colors"
                        >
                          <span>{t.ticket_number}</span>
                          <ExternalLink className="h-3 w-3 text-zinc-400" />
                        </Link>
                        <div className="flex items-center gap-1.5">
                          <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-mono uppercase font-medium ${prioStyle}`}>
                            {t.priority}
                          </span>
                          <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-mono uppercase font-medium ${statStyle}`}>
                            {t.status}
                          </span>
                        </div>
                      </div>

                      <p className="text-xs text-zinc-200 leading-snug line-clamp-2">
                        {t.title}
                      </p>

                      <div className="flex items-center justify-between text-xs text-zinc-400 pt-1">
                        <span className="rounded bg-white/[0.04] px-1.5 py-0.5 text-[11px] text-zinc-300 border border-white/[0.06]">
                          {t.category || "General"}
                        </span>
                        <span className="font-mono text-[11px] text-zinc-400">
                          {new Date(t.created_at).toLocaleDateString("en-IN", {
                            month: "short",
                            day: "numeric",
                          })}
                        </span>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="p-6 text-center text-xs text-zinc-400">
                  <LifeBuoy className="mx-auto h-6 w-6 text-zinc-500 mb-2 opacity-60" />
                  <p className="font-medium text-zinc-300">No support tickets</p>
                  <p className="text-zinc-400 mt-0.5">This customer has not filed any support requests.</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column (2 Cols) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Customer Activity Timeline */}
          <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-4">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.06] mb-4">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-zinc-300" />
                <h3 className="text-xs font-semibold text-zinc-100 uppercase tracking-wider">Activity Timeline</h3>
              </div>
              <span className="text-xs text-zinc-400 font-mono font-medium">
                {timelineEvents.length} chronological events
              </span>
            </div>

            <div className="relative pl-6 space-y-6 before:absolute before:left-[11px] before:top-2 before:bottom-2 before:w-[2px] before:bg-white/[0.08]">
              {timelineEvents.map((evt) => {
                let icon = <ShoppingBag className="h-3 w-3 text-zinc-300" />;
                let dotBorder = "border-zinc-700 bg-zinc-900";

                if (evt.type === "ticket") {
                  icon = <AlertCircle className="h-3 w-3 text-amber-400" />;
                  dotBorder = "border-amber-500/40 bg-zinc-900";
                } else if (evt.type === "account_created") {
                  icon = <UserCheck className="h-3 w-3 text-emerald-400" />;
                  dotBorder = "border-emerald-500/40 bg-zinc-900";
                } else if (evt.status === "DELIVERED") {
                  icon = <ShoppingBag className="h-3 w-3 text-emerald-400" />;
                  dotBorder = "border-emerald-500/40 bg-zinc-900";
                } else if (evt.status === "CANCELLED") {
                  icon = <ShoppingBag className="h-3 w-3 text-rose-400" />;
                  dotBorder = "border-rose-500/40 bg-zinc-900";
                }

                return (
                  <div key={evt.id} className="relative group">
                    {/* Timeline Node Dot */}
                    <div
                      className={`absolute -left-[30px] top-0.5 flex h-5 w-5 items-center justify-center rounded-full border ${dotBorder} shadow-sm`}
                    >
                      {icon}
                    </div>

                    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-1 sm:gap-4">
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-semibold text-zinc-100 font-mono">
                            {evt.title}
                          </span>
                          {evt.status && (
                            <span
                              className={`inline-flex items-center rounded border px-1.5 py-0.2 text-[10px] font-mono uppercase font-medium ${
                                orderStatusStyles[evt.status] || ticketStatusStyles[evt.status] || "border-zinc-700 bg-zinc-800 text-zinc-300"
                              }`}
                            >
                              {evt.status}
                            </span>
                          )}
                          {evt.priority && (
                            <span
                              className={`inline-flex items-center rounded border px-1.5 py-0.2 text-[10px] font-mono uppercase font-medium ${
                                ticketPriorityStyles[evt.priority] || "border-zinc-700 bg-zinc-800 text-zinc-300"
                              }`}
                            >
                              {evt.priority}
                            </span>
                          )}
                        </div>

                        {evt.subtitle && (
                          <p className="text-xs text-zinc-300 mt-0.5 leading-relaxed">
                            {evt.subtitle}
                          </p>
                        )}
                      </div>

                      <div className="flex items-center gap-3 shrink-0 sm:text-right mt-1 sm:mt-0">
                        {evt.amount !== undefined && (
                          <span className="font-mono text-xs font-semibold text-zinc-100 tabular-nums">
                            {formatInr(evt.amount)}
                          </span>
                        )}
                        <span className="font-mono text-xs text-zinc-400 whitespace-nowrap tabular-nums">
                          {new Date(evt.timestamp).toLocaleDateString("en-IN", {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })}
                        </span>
                        {evt.linkHref && (
                          <Link
                            href={evt.linkHref}
                            className="text-xs font-medium text-zinc-400 hover:text-white flex items-center gap-1 transition-colors"
                          >
                            <ExternalLink className="h-3 w-3" />
                          </Link>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Full Order History Section */}
          <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] overflow-hidden">
            <div className="p-4 border-b border-white/[0.06] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShoppingBag className="h-4 w-4 text-zinc-300" />
                <h3 className="text-xs font-semibold text-zinc-100 uppercase tracking-wider">Order History</h3>
              </div>
              <span className="text-xs font-mono font-medium text-zinc-400 tabular-nums">
                {orderHistory.length} recorded orders
              </span>
            </div>

            <div className="divide-y divide-white/[0.06]">
              {orderHistory.length > 0 ? (
                orderHistory.map((o) => {
                  const badgeStyle = orderStatusStyles[o.status] || "border-zinc-700 bg-zinc-800 text-zinc-300";
                  const parsedAmount = typeof o.total_amount === "number" ? o.total_amount : parseFloat(o.total_amount) || 0;
                  return (
                    <div key={o.id} className="p-4 flex items-center justify-between gap-4 hover:bg-white/[0.01] transition-colors">
                      <div>
                        <Link
                          href={`/orders/${o.id}`}
                          className="font-mono text-xs font-semibold text-zinc-100 hover:text-white flex items-center gap-1.5 transition-colors"
                        >
                          <span>{o.order_number}</span>
                          <ExternalLink className="h-3 w-3 text-zinc-400" />
                        </Link>
                        <div className="text-xs font-mono text-zinc-400 mt-0.5">
                          {new Date(o.created_at).toLocaleDateString("en-IN", {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })}
                          {o.items && o.items.length > 0 && ` • ${o.items.length} item${o.items.length > 1 ? "s" : ""}`}
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        <span className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium font-mono uppercase ${badgeStyle}`}>
                          {o.status}
                        </span>
                        <span className="font-mono font-semibold text-xs text-zinc-100 tabular-nums">
                          {formatInr(parsedAmount)}
                        </span>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="p-8 text-center text-xs text-zinc-400">
                  <ShoppingBag className="mx-auto h-6 w-6 text-zinc-500 mb-2 opacity-60" />
                  <p className="font-medium text-zinc-300">No previous orders on record</p>
                  <p className="text-zinc-400 mt-0.5">Orders placed by this customer will appear here.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
