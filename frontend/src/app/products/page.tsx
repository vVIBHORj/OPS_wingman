"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Package,
  Search,
  RefreshCw,
  Boxes,
} from "lucide-react";
import { fetchJson } from "@/lib/api";

interface ProductItem {
  id: string;
  sku: string;
  name: string;
  description?: string;
  category?: string;
  unit_price: number;
  currency: string;
  inventory_count: number;
  is_active: boolean;
}

export default function ProductsPage() {
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("ALL");

  const loadProducts = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchJson<ProductItem[]>("/products");
      setProducts(Array.isArray(data) ? data : [data]);
    } catch (err: any) {
      console.error("Failed to load products:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  const categories = [
    "ALL",
    ...Array.from(new Set(products.map((p) => p.category).filter(Boolean))),
  ];

  const filteredProducts = products.filter((p) => {
    const matchesCat =
      selectedCategory === "ALL" || p.category === selectedCategory;
    const matchesSearch =
      searchTerm.trim() === "" ||
      p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.sku.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesCat && matchesSearch;
  });

  const formatInr = (val: number) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <Package className="h-5 w-5 text-zinc-400" />
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">Products &amp; Inventory</h1>
            <span className="text-xs font-mono text-zinc-500 tabular-nums">({filteredProducts.length})</span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            SKU catalog, available inventory counts, unit pricing, and product classification.
          </p>
        </div>

        <button
          onClick={loadProducts}
          disabled={loading}
          className="self-start sm:self-auto inline-flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-[#0c0d14] px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-zinc-400" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter and Category Strip */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Category Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 scrollbar-none">
          {categories.map((cat) => {
            const isSelected = selectedCategory === cat;
            return (
              <button
                key={cat as string}
                onClick={() => setSelectedCategory(cat as string)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors shrink-0 ${
                  isSelected
                    ? "bg-white/[0.12] text-zinc-100 border border-white/[0.16]"
                    : "border border-white/[0.06] bg-[#0c0d14] text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60"
                }`}
              >
                {cat as string}
              </button>
            );
          })}
        </div>

        {/* Search */}
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-500" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search SKU or name..."
            className="w-full rounded-md border border-white/[0.08] bg-[#0c0d14] pl-9 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 focus:border-zinc-500 focus:outline-none transition-colors"
          />
        </div>
      </div>

      {/* Product Catalog Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {loading && products.length === 0 ? (
          <div className="col-span-full py-16 text-center text-zinc-500 font-mono text-xs">
            <RefreshCw className="mx-auto h-5 w-5 animate-spin text-zinc-600 mb-2" />
            Loading catalog inventory...
          </div>
        ) : filteredProducts.length === 0 ? (
          <div className="col-span-full py-16 text-center text-zinc-500 text-xs">
            No products match the selected criteria.
          </div>
        ) : (
          filteredProducts.map((p) => {
            const isLowStock = p.inventory_count < 20 && p.inventory_count > 0;
            const isOutOfStock = p.inventory_count === 0;

            const stockBadge = isOutOfStock
              ? "border-rose-500/20 bg-rose-500/10 text-rose-300"
              : isLowStock
              ? "border-amber-500/20 bg-amber-500/10 text-amber-300"
              : "border-emerald-500/20 bg-emerald-500/10 text-emerald-300";

            const stockText = isOutOfStock ? "Out of Stock" : isLowStock ? "Low Stock" : "In Stock";

            return (
              <div
                key={p.id}
                className="rounded-xl border border-white/[0.08] bg-[#0c0d14] p-4 flex flex-col justify-between hover:border-white/[0.16] transition-colors"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="font-mono text-[11px] font-medium text-zinc-400">
                      {p.sku}
                    </span>
                    <span className="rounded border border-white/[0.06] bg-white/[0.02] px-1.5 py-0.5 text-[10px] text-zinc-400">
                      {p.category || "General"}
                    </span>
                  </div>

                  <h3 className="text-xs font-semibold text-zinc-100 line-clamp-1">{p.name}</h3>
                  <p className="text-[11px] text-zinc-400 mt-1 line-clamp-2 leading-relaxed">
                    {p.description || "Enterprise SKU registered in OpsWingman catalog."}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-center justify-between">
                  <div>
                    <div className="text-xs font-semibold font-mono text-zinc-100 tabular-nums">
                      {formatInr(p.unit_price)}
                    </div>
                    <div className="text-[10px] text-zinc-500 font-mono">Tax incl.</div>
                  </div>

                  <div className="text-right">
                    <div className="flex items-center gap-1 justify-end font-mono text-xs text-zinc-200 tabular-nums">
                      <Boxes className="h-3 w-3 text-zinc-500" />
                      <span>{p.inventory_count}</span>
                    </div>
                    <span className={`inline-block mt-0.5 rounded border px-1.5 py-0.5 text-[9px] font-mono uppercase ${stockBadge}`}>
                      {stockText}
                    </span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
