import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OpsWingman | Intelligent Operations Platform",
  description: "Deterministic runtime & Intelligent Operations Platform for modern businesses",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-slate-950 text-slate-100 antialiased">
        {children}
      </body>
    </html>
  );
}
