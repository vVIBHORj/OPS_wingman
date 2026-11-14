"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Users,
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  MapPin,
  Mail,
} from "lucide-react";
import { fetchJson } from "@/lib/api";

interface CustomerItem {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  city?: string;
  created_at: string;
  order_count: number;
  total_spend: number | string;
}

interface CustomerListResponse {
  total: number;
  limit: number;
  offset: number;
  items: CustomerItem[];
  customers?: CustomerItem[];
}

export default function CustomersPage() {
  const [customers, setCustomers] = useState<CustomerItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [cityFilter, setCityFilter] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 15;

  const loadCustomers = useCallback(async () => {
    try {
      setLoading(true);
      let query = `/customers?limit=${pageSize}&offset=${page * pageSize}`;
      if (cityFilter.trim()) {
        query += `&city=${encodeURIComponent(cityFilter.trim())}`;
      }
      if (searchTerm.trim()) {
        query += `&search=${encodeURIComponent(searchTerm.trim())}`;
      }

      const res = await fetchJson<CustomerListResponse>(query);
      setCustomers(res.items || res.customers || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      console.error("Failed to load customers:", err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, cityFilter, searchTerm]);

  useEffect(() => {
    loadCustomers();
  }, [loadCustomers]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(0);
    loadCustomers();
  };

  const formatInr = (val: number | string) => {
    const num = typeof val === "number" ? val : parseFloat(val || "0") || 0;
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(num);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <Users className="h-5 w-5 text-zinc-400" />
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">Customers</h1>
            <span className="text-xs font-mono text-zinc-500 tabular-nums">({total})</span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Accounts directory, verified order frequencies, lifetime value, and regional delivery metrics.
          </p>
        </div>

        <button
          onClick={loadCustomers}
          disabled={loading}
          className="self-start sm:self-auto inline-flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-[#0c0d14] px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-zinc-400" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <form onSubmit={handleSearchSubmit} className="relative w-full sm:w-80">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-500" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search by name, email, phone..."
            className="w-full rounded-md border border-white/[0.08] bg-[#0c0d14] pl-9 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 focus:border-zinc-500 focus:outline-none transition-colors"
          />
        </form>

        <div className="flex items-center gap-2">
          <div className="relative">
            <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-500" />
            <input
              type="text"
              value={cityFilter}
              onChange={(e) => {
                setCityFilter(e.target.value);
                setPage(0);
              }}
              placeholder="Filter by city (e.g. Mumbai)"
              className="w-full sm:w-56 rounded-md border border-white/[0.08] bg-[#0c0d14] pl-8 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 focus:border-zinc-500 focus:outline-none transition-colors"
            />
          </div>
        </div>
      </div>

      {/* Customer Directory Table */}
      <div className="rounded-xl border border-white/[0.08] bg-[#0c0d14] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-white/[0.06] bg-[#0a0b10] text-[11px] font-medium text-zinc-400 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3">Contact</th>
                <th className="px-4 py-3">Location</th>
                <th className="px-4 py-3">Orders</th>
                <th className="px-4 py-3">Total Spend</th>
                <th className="px-4 py-3">Registered</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.06] text-zinc-300">
              {loading && customers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-zinc-500 font-mono text-xs">
                    <RefreshCw className="mx-auto h-5 w-5 animate-spin text-zinc-600 mb-2" />
                    Querying customer database...
                  </td>
                </tr>
              ) : customers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-zinc-500 text-xs">
                    No customer accounts match the current filter criteria.
                  </td>
                </tr>
              ) : (
                customers.map((c) => (
                  <tr key={c.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-3">
                      <Link
                        href={`/customers/${c.id}`}
                        className="font-medium text-zinc-100 hover:text-white flex items-center gap-2.5 transition-colors"
                      >
                        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-zinc-800 text-[10px] font-medium text-zinc-300 uppercase">
                          {c.first_name?.[0] || "U"}
                          {c.last_name?.[0] || ""}
                        </div>
                        <span className="truncate max-w-[160px]">
                          {c.first_name} {c.last_name}
                        </span>
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-zinc-200 flex items-center gap-1.5 truncate max-w-[200px]">
                        <Mail className="h-3 w-3 text-zinc-400 shrink-0" />
                        <span>{c.email}</span>
                      </div>
                      <div className="text-[11px] text-zinc-400 font-mono mt-0.5">{c.phone || "No phone listed"}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center rounded border border-white/[0.06] bg-white/[0.02] px-2 py-0.5 text-[11px] text-zinc-300">
                        {c.city || "India"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-zinc-200 tabular-nums">
                        {c.order_count} {c.order_count === 1 ? "order" : "orders"}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono font-medium text-zinc-100 tabular-nums">
                      {formatInr(c.total_spend || 0)}
                    </td>
                    <td className="px-4 py-3 text-zinc-400 whitespace-nowrap text-[11px] font-mono">
                      {new Date(c.created_at).toLocaleDateString("en-IN", {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                      })}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/customers/${c.id}`}
                        className="inline-flex items-center gap-1 rounded border border-white/[0.08] bg-[#090a0f] px-2.5 py-1 text-[11px] font-medium text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors"
                      >
                        <span>Profile</span>
                        <ExternalLink className="h-3 w-3 text-zinc-500" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="flex items-center justify-between border-t border-white/[0.06] bg-[#0a0b10] px-4 py-3 text-xs text-zinc-400">
          <div>
            Showing <span className="font-mono text-zinc-200 tabular-nums">{customers.length}</span> of{" "}
            <span className="font-mono text-zinc-200 tabular-nums">{total}</span> customers
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
