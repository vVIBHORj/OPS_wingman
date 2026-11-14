"use client";

import React, { useEffect } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Application error boundary caught:", error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center px-4">
      <div className="rounded-2xl border border-rose-500/20 bg-[#0c0d14] p-8 max-w-md w-full shadow-2xl space-y-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-rose-500/20 bg-rose-500/10 text-rose-400 mx-auto">
          <AlertTriangle className="h-6 w-6" />
        </div>
        <div>
          <span className="font-mono text-xs uppercase tracking-wider text-rose-400">Application Error</span>
          <h1 className="text-xl font-semibold tracking-tight text-zinc-100 mt-1">Operational Fault</h1>
          <p className="text-xs text-zinc-400 mt-2 leading-relaxed">
            {error.message || "An unexpected error occurred while rendering the operations console."}
          </p>
        </div>
        <div className="pt-2">
          <button
            onClick={() => reset()}
            className="inline-flex items-center gap-2 rounded-md border border-white/[0.08] bg-zinc-900 px-4 py-2 text-xs font-medium text-zinc-200 hover:bg-zinc-800 hover:text-white transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Retry Operation</span>
          </button>
        </div>
      </div>
    </div>
  );
}

