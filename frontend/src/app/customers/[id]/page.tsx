"use client";

import React, { useState, useEffect, useCallback } from "react";
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
  IndianRupee,
  RefreshCw,
  AlertTriangle,
  ExternalLink,
} from "lucide-react";
import { fetchJson } from "@/lib/api";

interface CustomerDetail {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  country?: string;
  created_at: string;
  order_count: number;
  total_spend: number;
  orders?: Array<{
    id: string;
    order_number: string;
    status: string;
    total_amount: number;
    created_at: string;
  }>;
  recent_orders?: Array<{
    id: string;
    order_number: string;
    status: string;
    total_amount: number;
    created_at: string;
  }>;
  recent_tickets?: Array<{
    id: string;
    ticket_number: string;
    title: string;
    status: string;
    priority: string;
    created_at: string;
  }>;
}

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

  const formatInr = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);
  };

  if (loading && !customer) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-3 text-slate-400">
        <RefreshCw className="h-8 w-8 animate-spin text-sky-400" />
        <p className="text-sm">Loading customer profile...</p>
      </div>
    );
  }

  if (error || !customer) {
    return (
      <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 p-6 text-center">
        <AlertTriangle className="mx-auto h-8 w-8 text-rose-400 mb-2" />
        <h3 className="text-lg font-bold text-rose-200">Customer Not Found</h3>
        <p className="text-sm text-slate-400 mt-1">{error || "Customer record could not be loaded."}</p>
        <Link
          href="/customers"
          className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-700"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Back to Directory</span>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Top Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <Link
            href="/customers"
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-800 bg-slate-900 text-slate-400 hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <span>
                {customer.first_name} {customer.last_name}
              </span>
              <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs font-mono text-slate-400">
                {customer.city || "India"}
              </span>
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Customer ID: <span className="font-mono text-slate-300">{customer.id}</span>
            </p>
          </div>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="text-xs font-medium text-slate-400 mb-1 flex items-center justify-between">
            <span>Lifetime Spend</span>
            <IndianRupee className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-xl font-bold text-emerald-400">{formatInr(customer.total_spend)}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">All settled orders</div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="text-xs font-medium text-slate-400 mb-1 flex items-center justify-between">
            <span>Orders Placed</span>
            <ShoppingBag className="h-4 w-4 text-sky-400" />
          </div>
          <div className="text-xl font-bold text-white">{customer.order_count}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Total transaction count</div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="text-xs font-medium text-slate-400 mb-1 flex items-center justify-between">
            <span>Average Order Value</span>
            <IndianRupee className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="text-xl font-bold text-indigo-300">
            {formatInr(customer.order_count > 0 ? customer.total_spend / customer.order_count : 0)}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Per-order basket size</div>
        </div>
      </div>

      {/* Grid: Contact Info & Order History */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Contact Info Card */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 space-y-4">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <User className="h-4 w-4 text-sky-400" />
            Contact Information
          </h3>

          <div className="space-y-3 text-xs">
            <div className="flex items-center gap-2.5 text-slate-300">
              <Mail className="h-4 w-4 text-slate-500 shrink-0" />
              <span>{customer.email}</span>
            </div>

            <div className="flex items-center gap-2.5 text-slate-300">
              <Phone className="h-4 w-4 text-slate-500 shrink-0" />
              <span className="font-mono">{customer.phone || "No phone registered"}</span>
            </div>

            <div className="flex items-center gap-2.5 text-slate-300">
              <MapPin className="h-4 w-4 text-slate-500 shrink-0" />
              <span>
                {customer.city}, {customer.state} {customer.postal_code}
                <br />
                {customer.country || "India"}
              </span>
            </div>

            <div className="flex items-center gap-2.5 text-slate-400 pt-2 border-t border-slate-800 text-[11px]">
              <Calendar className="h-3.5 w-3.5 text-slate-500" />
              <span>Joined {new Date(customer.created_at).toLocaleDateString("en-IN")}</span>
            </div>
          </div>
        </div>

        {/* Order History */}
        <div className="lg:col-span-2 rounded-xl border border-slate-800 bg-slate-900/40 p-5">
          <h3 className="text-sm font-bold text-white mb-3">Order History</h3>
          {(customer.recent_orders || customer.orders) && (customer.recent_orders || customer.orders)!.length > 0 ? (
            <div className="divide-y divide-slate-800/80">
              {(customer.recent_orders || customer.orders)!.map((o) => (
                <div key={o.id} className="py-3 flex items-center justify-between text-xs">
                  <div>
                    <Link
                      href={`/orders/${o.id}`}
                      className="font-mono font-semibold text-sky-400 hover:underline flex items-center gap-1.5"
                    >
                      <span>{o.order_number}</span>
                      <ExternalLink className="h-3 w-3" />
                    </Link>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      {new Date(o.created_at).toLocaleDateString("en-IN", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="rounded bg-slate-800 border border-slate-700 px-2 py-0.5 text-[10px] font-semibold text-slate-300">
                      {o.status}
                    </span>
                    <span className="font-bold text-white">{formatInr(o.total_amount)}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 py-6 text-center">No orders recorded for this customer.</p>
          )}
        </div>
      </div>
    </div>
  );
}

