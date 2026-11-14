import React from "react";
import Link from "next/link";
import { ArrowLeft, ShieldAlert } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center px-4">
      <div className="rounded-2xl border border-white/[0.08] bg-[#0c0d14] p-8 max-w-md w-full shadow-2xl space-y-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-rose-500/20 bg-rose-500/10 text-rose-400 mx-auto">
          <ShieldAlert className="h-6 w-6" />
        </div>
        <div>
          <span className="font-mono text-xs uppercase tracking-wider text-zinc-500">Error 404</span>
          <h1 className="text-xl font-semibold tracking-tight text-zinc-100 mt-1">Resource Not Found</h1>
          <p className="text-xs text-zinc-400 mt-2 leading-relaxed">
            The requested operations entity, record, or navigation route could not be located in the ledger.
          </p>
        </div>
        <div className="pt-2">
          <Link
            href="/"
            className="inline-flex items-center gap-2 rounded-md border border-white/[0.08] bg-zinc-900 px-4 py-2 text-xs font-medium text-zinc-200 hover:bg-zinc-800 hover:text-white transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Return to Dashboard</span>
          </Link>
        </div>
      </div>
    </div>
  );
}

