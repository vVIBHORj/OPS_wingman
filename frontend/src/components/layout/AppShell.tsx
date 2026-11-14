"use client";

import React, { useState } from "react";
import Sidebar from "./Sidebar";
import Header from "./Header";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#08090d] text-zinc-100 flex">
      {/* Sidebar with responsive collapse & mobile overlay */}
      <Sidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed(!collapsed)}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      {/* Main Content Area */}
      <div
        className={`flex flex-1 flex-col min-w-0 transition-all duration-200 ease-out ${
          collapsed ? "md:pl-20" : "md:pl-64"
        }`}
      >
        <Header onOpenMobile={() => setMobileOpen(true)} />
        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-x-hidden max-w-[1600px] w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
