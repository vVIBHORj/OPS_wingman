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
    <html lang="en" className="dark">
      <body className="min-h-screen bg-slate-950 text-slate-100 antialiased font-sans">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
