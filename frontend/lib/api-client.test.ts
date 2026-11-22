/**
 * Unit tests for the API client utilities.
 * Uses fetch mocking; verifies Authorization header injection and error mapping.
 */

import { ApiError } from "./api-client";

// Minimal saveToken stub so getToken() returns a known value
jest.mock("./auth", () => ({
  getToken: jest.fn().mockReturnValue("mock-jwt"),
}));

const { researchApi, healthApi } = jest.requireActual<
  typeof import("./api-client")
>("./api-client");

function mockFetch(status: number, body: unknown, headers: Record<string, string> = {}) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (k: string) => headers[k] ?? null },
    json: () => Promise.resolve(body),
  } as unknown as Response);
}

describe("ApiError", () => {
  it("carries status and message", () => {
    const e = new ApiError(404, "Not found", "req-1");
    expect(e.status).toBe(404);
    expect(e.message).toBe("Not found");
    expect(e.requestId).toBe("req-1");
  });
});

describe("healthApi.ready", () => {
  it("returns health payload on 200", async () => {
    const payload = { status: "ok", checks: {} };
    mockFetch(200, payload);
    const result = await healthApi.ready();
    expect(result).toEqual(payload);
  });
});

describe("researchApi.get", () => {
  it("sends Authorization header with stored token", async () => {
    mockFetch(200, { session_id: "s1", status: "running", sub_questions: [], evidence: [], strategies_used: [] });
    await researchApi.get("s1");
    const calls = (global.fetch as jest.Mock).mock.calls;
    expect(calls[0][1].headers["Authorization"]).toBe("Bearer mock-jwt");
  });

  it("throws ApiError on 404", async () => {
    mockFetch(404, { detail: "Session not found" });
    await expect(researchApi.get("missing")).rejects.toMatchObject({
      status: 404,
      message: "Session not found",
    });
  });
});
