import type { Role } from "@/lib/types";

const COLORS: Record<Role, string> = {
  viewer: "bg-slate-100 text-slate-600",
  analyst: "bg-blue-100 text-blue-700",
  admin: "bg-purple-100 text-purple-700",
};

export default function RoleBadge({ role }: { role: Role | null }) {
  if (!role) return null;
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${COLORS[role]}`}>
      {role}
    </span>
  );
}
