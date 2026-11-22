"use client";

import { useEffect, useState } from "react";
import { healthApi } from "@/lib/api-client";
import type { HealthReady } from "@/lib/types";

export default function HealthBanner() {
  const [health, setHealth] = useState<HealthReady | null>(null);

  useEffect(() => {
    healthApi.ready().then(setHealth).catch(() => null);
  }, []);

  if (!health || health.status === "ok") return null;

  const degraded = Object.entries(health.checks)
    .filter(([, v]) => v.status !== "ok")
    .map(([k, v]) => `${k}: ${v.detail}`)
    .join(" · ");

  return (
    <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 text-sm text-amber-800">
      <strong>System degraded</strong> — {degraded}. Research on affected stores may return partial results.
    </div>
  );
}
