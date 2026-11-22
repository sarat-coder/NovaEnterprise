"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isLoggedIn } from "@/lib/auth";
import Nav from "@/components/nav";
import HealthBanner from "@/components/health-banner";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
    }
  }, [router]);

  if (!isLoggedIn()) return null;

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Nav />
      <HealthBanner />
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6">{children}</main>
    </div>
  );
}
