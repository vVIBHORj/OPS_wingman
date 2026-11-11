"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Package,
  Search,
  RefreshCw,
  Tag,
  AlertTriangle,
  CheckCircle2,
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
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("ALL");

  const loadProducts = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchJson<ProductItem[]>("/products");
      setProducts(Array.isArray(data) ? data : [data]);
    } catch (err: any) {
      setError(err.message || "Failed to load products");
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Package className="h-6 w-6 text-sky-400" />
            Product Catalog &amp; Inventory
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            SKU registry, live stock levels, categorized catalog, and unit pricing.
          </p>
        </div>

        <button
          onClick={loadProducts}
          disabled={loading}
          className="self-start sm:self-auto flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-800 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin text-sky-400" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Search and Category Pills */}
      <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4">
        {/* Category Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 lg:pb-0 scrollbar-thin">
          {categories.map((cat) => (
            <button
              key={cat as string}
              onClick={() => setSelectedCategory(cat as string)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors shrink-0 ${
                selectedCategory === cat
                  ? "bg-sky-500 text-white font-semibold"
                  : "bg-slate-900 text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              }`}
            >
              {cat as string}
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
            placeholder="Search product SKU or name..."
            className="w-full rounded-lg border border-slate-800 bg-slate-900/80 pl-9 pr-4 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Catalog Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {loading && products.length === 0 ? (
          <div className="col-span-full py-16 text-center text-slate-500">
            <RefreshCw className="mx-auto h-6 w-6 animate-spin text-sky-400 mb-2" />
            Loading catalog items...
          </div>
        ) : filteredProducts.length === 0 ? (
          <div className="col-span-full py-16 text-center text-slate-500">
            No products match the selected criteria.
          </div>
        ) : (
          filteredProducts.map((p) => {
            const isLowStock = p.inventory_count < 20;
            const isOutOfStock = p.inventory_count === 0;

            return (
              <div
                key={p.id}
                className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 flex flex-col justify-between hover:border-slate-700 transition-colors"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-[11px] font-semibold text-sky-400">
                      {p.sku}
                    </span>
                    <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-400 font-medium">
                      {p.category || "General"}
                    </span>
                  </div>

                  <h3 className="text-sm font-bold text-white line-clamp-1">{p.name}</h3>
                  <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                    {p.description || "Enterprise SKU registered in OpsWingman catalog."}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between">
                  <div>
                    <div className="text-base font-bold text-white">{formatInr(p.unit_price)}</div>
                    <div className="text-[10px] text-slate-500 font-mono">Tax inclusive</div>
                  </div>

                  <div className="text-right">
                    <div className="flex items-center gap-1.5 justify-end">
                      <Boxes className="h-3.5 w-3.5 text-slate-400" />
                      <span className="text-xs font-semibold text-slate-200">
                        {p.inventory_count}
                      </span>
                    </div>
                    <span
                      className={`text-[9px] font-bold uppercase ${
                        isOutOfStock
                          ? "text-rose-400"
                          : isLowStock
                          ? "text-amber-400"
                          : "text-emerald-400"
                      }`}
                    >
                      {isOutOfStock ? "Out of Stock" : isLowStock ? "Low Stock" : "In Stock"}
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

