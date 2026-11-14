import type { Metadata } from "next";
import "./globals.css";
import AppShell from "@/components/layout/AppShell";

export const metadata: Metadata = {
  title: "OpsWingman | Operations Control Center",
  description:
    "Enterprise-grade deterministic operations management and AI execution control center",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark scroll-smooth">
      <body className="min-h-screen bg-[#090a0f] text-zinc-100 antialiased selection:bg-indigo-500/30 selection:text-white">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
