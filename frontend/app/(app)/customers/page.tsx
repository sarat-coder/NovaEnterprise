"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { customersApi, ApiError } from "@/lib/api-client";
import type { CustomerSummary } from "@/lib/types";

const TIER_COLORS: Record<string, string> = {
  platinum: "bg-violet-100 text-violet-700",
  gold: "bg-yellow-100 text-yellow-700",
  silver: "bg-slate-100 text-slate-600",
};

const SEG_COLORS: Record<string, string> = {
  enterprise: "bg-blue-100 text-blue-700",
  "mid-market": "bg-green-100 text-green-700",
  smb: "bg-orange-100 text-orange-700",
};

export default function CustomersPage() {
  const [customers, setCustomers] = useState<CustomerSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    customersApi
      .list()
      .then(setCustomers)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-900">Customers</h1>

      {loading && <p className="text-slate-500 text-sm">Loading…</p>}
      {error && <p className="text-red-600 text-sm">{error}</p>}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {customers.map((c) => (
          <Link
            key={c.id}
            href={`/customers/${c.id}`}
            className="bg-white border border-slate-200 rounded-xl p-4 hover:shadow-md transition-shadow space-y-2"
          >
            <div className="flex items-start justify-between gap-2">
              <p className="font-semibold text-slate-900 text-sm">{c.name}</p>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full shrink-0 ${TIER_COLORS[c.contract_tier] ?? "bg-slate-100 text-slate-600"}`}>
                {c.contract_tier}
              </span>
            </div>
            <p className="text-xs text-slate-500">{c.industry}</p>
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full inline-block ${SEG_COLORS[c.segment] ?? "bg-slate-100 text-slate-600"}`}>
              {c.segment}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
