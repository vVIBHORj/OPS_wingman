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
  IndianRupee,
  ShoppingBag,
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
  total_spend: number;
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
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [cityFilter, setCityFilter] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 15;

  const loadCustomers = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
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
      setError(err.message || "Failed to load customers");
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

  const formatInr = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Users className="h-6 w-6 text-sky-400" />
            Customer Directory
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Customer lifetime value, order frequency, geographic segments, and unified support records.
          </p>
        </div>

        <button
          onClick={loadCustomers}
          disabled={loading}
          className="self-start sm:self-auto flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-800 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-sky-400" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filters & Search */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        <form onSubmit={handleSearchSubmit} className="relative w-full sm:w-96">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search customer name, email, phone..."
            className="w-full rounded-lg border border-slate-800 bg-slate-900/80 pl-9 pr-4 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
          />
        </form>

        <div className="flex items-center gap-2">
          <MapPin className="h-3.5 w-3.5 text-slate-500" />
          <input
            type="text"
            value={cityFilter}
            onChange={(e) => {
              setCityFilter(e.target.value);
              setPage(0);
            }}
            placeholder="Filter by city (e.g. Mumbai, Bengaluru)"
            className="rounded-lg border border-slate-800 bg-slate-900/80 px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Customer Directory Table */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden shadow">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 bg-slate-900/80 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-4 py-3">Customer Name</th>
                <th className="px-4 py-3">Contact Details</th>
                <th className="px-4 py-3">City</th>
                <th className="px-4 py-3">Orders Count</th>
                <th className="px-4 py-3">Lifetime Value</th>
                <th className="px-4 py-3">Member Since</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {loading && customers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    <RefreshCw className="mx-auto h-6 w-6 animate-spin text-sky-400 mb-2" />
                    Loading customers...
                  </td>
                </tr>
              ) : customers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    No customers found matching the search criteria.
                  </td>
                </tr>
              ) : (
                customers.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="px-4 py-3">
                      <Link
                        href={`/customers/${c.id}`}
                        className="font-semibold text-slate-100 hover:text-sky-400 flex items-center gap-2"
                      >
                        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-800 text-[11px] font-bold text-sky-400">
                          {c.first_name[0]}
                          {c.last_name[0]}
                        </div>
                        <span>
                          {c.first_name} {c.last_name}
                        </span>
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-slate-300">{c.email}</div>
                      <div className="text-[10px] text-slate-500 font-mono">{c.phone || "No phone"}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] text-slate-300">
                        {c.city || "India"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-slate-200">
                        {c.order_count} order{c.order_count !== 1 ? "s" : ""}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-semibold text-emerald-400">
                      {formatInr(c.total_spend)}
                    </td>
                    <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                      {new Date(c.created_at).toLocaleDateString("en-IN", {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                      })}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/customers/${c.id}`}
                        className="inline-flex items-center gap-1 rounded bg-slate-800 px-2 py-1 text-[11px] font-medium text-slate-300 hover:bg-sky-600 hover:text-white transition-colors"
                      >
                        <span>Profile</span>
                        <ExternalLink className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        <div className="flex items-center justify-between border-t border-slate-800 bg-slate-900/60 px-4 py-3 text-xs text-slate-400">
          <div>
            Showing <span className="font-semibold text-white">{customers.length}</span> of{" "}
            <span className="font-semibold text-white">{total}</span> customers
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

