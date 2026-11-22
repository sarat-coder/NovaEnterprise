"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { customersApi, ApiError } from "@/lib/api-client";
import type { CustomerSummary } from "@/lib/types";

export default function CustomerDetailPage({ params }: { params: { id: string } }) {
  const [customer, setCustomer] = useState<CustomerSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    customersApi
      .get(Number(params.id))
      .then(setCustomer)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load"));
  }, [params.id]);

  if (error) return <div className="text-red-600 text-sm">{error}</div>;
  if (!customer) return <div className="text-slate-500 text-sm">Loading…</div>;

  return (
    <div className="max-w-xl space-y-4">
      <Link href="/customers" className="text-sm text-blue-600 hover:underline">← Customers</Link>
      <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-3">
        <h1 className="text-xl font-bold text-slate-900">{customer.name}</h1>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <dt className="text-slate-500">Segment</dt>
          <dd className="text-slate-900 capitalize">{customer.segment}</dd>
          <dt className="text-slate-500">Industry</dt>
          <dd className="text-slate-900">{customer.industry}</dd>
          <dt className="text-slate-500">Contract tier</dt>
          <dd className="text-slate-900 capitalize">{customer.contract_tier}</dd>
          <dt className="text-slate-500">Slug</dt>
          <dd className="text-slate-500 font-mono text-xs">{customer.slug}</dd>
        </dl>
      </div>
    </div>
  );
}
