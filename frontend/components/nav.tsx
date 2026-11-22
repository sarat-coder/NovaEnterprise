"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearToken, getRole } from "@/lib/auth";
import { canStartResearch } from "@/lib/auth";
import RoleBadge from "./role-badge";

const NAV_LINKS = [
  { href: "/search", label: "Search", analystOnly: true },
  { href: "/customers", label: "Customers", analystOnly: false },
  { href: "/incidents", label: "Incidents", analystOnly: false },
  { href: "/decisions", label: "Decisions", analystOnly: false },
  { href: "/documents", label: "Documents", analystOnly: false },
  { href: "/knowledge-graph", label: "Knowledge Graph", analystOnly: false },
];

export default function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const role = getRole();

  function handleLogout() {
    clearToken();
    router.push("/login");
  }

  return (
    <nav className="bg-white border-b border-slate-200 sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-4 flex items-center h-14 gap-6">
        <Link href="/search" className="font-bold text-slate-900 text-lg shrink-0">
          NovaEnterprise
        </Link>

        <div className="flex items-center gap-1 flex-1 overflow-x-auto">
          {NAV_LINKS.map((link) => {
            if (link.analystOnly && !canStartResearch(role)) return null;
            const active = pathname === link.href || pathname.startsWith(link.href + "/");
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`px-3 py-1.5 rounded-md text-sm font-medium whitespace-nowrap transition-colors ${
                  active
                    ? "bg-blue-50 text-blue-700"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <RoleBadge role={role} />
          <button
            onClick={handleLogout}
            className="text-xs text-slate-500 hover:text-slate-900 transition-colors"
          >
            Sign out
          </button>
        </div>
      </div>
    </nav>
  );
}
