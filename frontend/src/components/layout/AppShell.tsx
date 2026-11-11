"use client";

import React from "react";
import Sidebar from "./Sidebar";
import Header from "./Header";

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex">
      {/* Persistent Left Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col pl-64 transition-all duration-300">
        <Header />
        <main className="flex-1 p-6 lg:p-8 bg-slate-950/60 overflow-x-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}

