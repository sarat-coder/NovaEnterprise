"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { authApi, ApiError } from "@/lib/api-client";
import { saveToken } from "@/lib/auth";

const DEMO_USERS = [
  { label: "viewer / viewer123", username: "viewer", password: "viewer123" },
  { label: "analyst / analyst123", username: "analyst", password: "analyst123" },
  { label: "admin / admin123", username: "admin", password: "admin123" },
];

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("analyst");
  const [password, setPassword] = useState("analyst123");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await authApi.login({ username, password });
      saveToken(res.access_token, res.role);
      router.push("/search");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Login failed — is the backend running on :8001?");
      }
    } finally {
      setLoading(false);
    }
  }

  function fillDemo(u: string, p: string) {
    setUsername(u);
    setPassword(p);
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-lg p-8 space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-slate-900">NovaEnterprise</h1>
          <p className="text-sm text-slate-500 mt-1">Knowledge & Decision Intelligence Platform</p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium py-2 rounded-lg text-sm transition-colors"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="border-t border-slate-100 pt-4">
          <p className="text-xs text-slate-500 mb-2 font-medium">Demo accounts</p>
          <div className="flex gap-2 flex-wrap">
            {DEMO_USERS.map((u) => (
              <button
                key={u.username}
                type="button"
                onClick={() => fillDemo(u.username, u.password)}
                className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-2 py-1 rounded transition-colors"
              >
                {u.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
