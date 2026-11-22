import type { Role } from "./types";

const TOKEN_KEY = "nova_token";
const ROLE_KEY = "nova_role";

export function saveToken(token: string, role: Role): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(TOKEN_KEY, token);
  sessionStorage.setItem(ROLE_KEY, role);
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(TOKEN_KEY);
}

export function getRole(): Role | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(ROLE_KEY) as Role | null;
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(ROLE_KEY);
}

export function isLoggedIn(): boolean {
  return getToken() !== null;
}

export function canStartResearch(role: Role | null): boolean {
  return role === "analyst" || role === "admin";
}

export function canUpload(role: Role | null): boolean {
  return role === "analyst" || role === "admin";
}

export function canRunCypher(role: Role | null): boolean {
  return role === "analyst" || role === "admin";
}

export function isAdmin(role: Role | null): boolean {
  return role === "admin";
}
