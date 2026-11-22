/**
 * Unit tests for auth utility functions.
 * These are pure functions (no DOM/API); they run in Node.js with jsdom.
 */

import {
  canStartResearch,
  canUpload,
  canRunCypher,
  isAdmin,
  saveToken,
  getToken,
  getRole,
  clearToken,
  isLoggedIn,
} from "./auth";
import type { Role } from "./types";

// ─── Role predicate tests ─────────────────────────────────────────────────────

describe("canStartResearch", () => {
  it("returns false for viewer", () => expect(canStartResearch("viewer")).toBe(false));
  it("returns true for analyst", () => expect(canStartResearch("analyst")).toBe(true));
  it("returns true for admin", () => expect(canStartResearch("admin")).toBe(true));
  it("returns false for null", () => expect(canStartResearch(null)).toBe(false));
});

describe("canUpload", () => {
  it("returns false for viewer", () => expect(canUpload("viewer")).toBe(false));
  it("returns true for analyst", () => expect(canUpload("analyst")).toBe(true));
  it("returns true for admin", () => expect(canUpload("admin")).toBe(true));
  it("returns false for null", () => expect(canUpload(null)).toBe(false));
});

describe("canRunCypher", () => {
  it("returns false for viewer", () => expect(canRunCypher("viewer")).toBe(false));
  it("returns true for analyst", () => expect(canRunCypher("analyst")).toBe(true));
  it("returns true for admin", () => expect(canRunCypher("admin")).toBe(true));
  it("returns false for null", () => expect(canRunCypher(null)).toBe(false));
});

describe("isAdmin", () => {
  it("returns false for viewer", () => expect(isAdmin("viewer")).toBe(false));
  it("returns false for analyst", () => expect(isAdmin("analyst")).toBe(false));
  it("returns true for admin", () => expect(isAdmin("admin")).toBe(true));
  it("returns false for null", () => expect(isAdmin(null)).toBe(false));
});

// ─── Token storage tests ──────────────────────────────────────────────────────

describe("token storage (sessionStorage)", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("isLoggedIn returns false when no token stored", () => {
    expect(isLoggedIn()).toBe(false);
  });

  it("saveToken persists token and role; getToken / getRole return them", () => {
    saveToken("test-jwt", "analyst");
    expect(getToken()).toBe("test-jwt");
    expect(getRole()).toBe("analyst");
    expect(isLoggedIn()).toBe(true);
  });

  it("clearToken removes token and role", () => {
    saveToken("test-jwt", "admin");
    clearToken();
    expect(getToken()).toBeNull();
    expect(getRole()).toBeNull();
    expect(isLoggedIn()).toBe(false);
  });

  it("saveToken works for all three roles", () => {
    const roles: Role[] = ["viewer", "analyst", "admin"];
    for (const role of roles) {
      saveToken("tok", role);
      expect(getRole()).toBe(role);
    }
  });
});
