/**
 * Unit tests for the Search page.
 * Verifies role-aware rendering and form submission.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock Next.js router
const mockPush = jest.fn();
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: mockPush }) }));

// Mock auth helpers
jest.mock("@/lib/auth", () => ({
  canStartResearch: jest.fn(),
  getRole: jest.fn(),
}));

// Mock the research API
jest.mock("@/lib/api-client", () => ({
  researchApi: { start: jest.fn() },
  ApiError: class ApiError extends Error {
    constructor(public status: number, message: string) { super(message); }
  },
}));

import SearchPage from "./page";
import { canStartResearch, getRole } from "@/lib/auth";
import { researchApi } from "@/lib/api-client";

const mockCanStart = canStartResearch as jest.Mock;
const mockGetRole = getRole as jest.Mock;
const mockStart = researchApi.start as jest.Mock;

describe("SearchPage — viewer", () => {
  beforeEach(() => {
    mockGetRole.mockReturnValue("viewer");
    mockCanStart.mockReturnValue(false);
  });

  it("shows access denied notice", () => {
    render(<SearchPage />);
    expect(screen.getByText(/viewers cannot start research/i)).toBeTruthy();
  });

  it("disables the textarea", () => {
    render(<SearchPage />);
    const textarea = screen.getByRole("textbox");
    expect((textarea as HTMLTextAreaElement).disabled).toBe(true);
  });

  it("disables the Research button", () => {
    render(<SearchPage />);
    const btn = screen.getByRole("button", { name: /research/i });
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });
});

describe("SearchPage — analyst", () => {
  beforeEach(() => {
    mockGetRole.mockReturnValue("analyst");
    mockCanStart.mockReturnValue(true);
    mockPush.mockClear();
    mockStart.mockClear();
  });

  it("shows the search textarea enabled", () => {
    render(<SearchPage />);
    const textarea = screen.getByRole("textbox");
    expect((textarea as HTMLTextAreaElement).disabled).toBe(false);
  });

  it("redirects to /research/<id> on successful submit", async () => {
    mockStart.mockResolvedValueOnce({ session_id: "sess-abc", status: "running" });
    render(<SearchPage />);
    const textarea = screen.getByRole("textbox");
    await userEvent.type(textarea, "What services did the Payments team own?");
    const btn = screen.getByRole("button", { name: /research/i });
    await userEvent.click(btn);
    expect(mockStart).toHaveBeenCalledWith("What services did the Payments team own?");
    expect(mockPush).toHaveBeenCalledWith("/research/sess-abc");
  });

  it("shows 'Unexpected error' on generic failure", async () => {
    mockStart.mockRejectedValueOnce(new Error("Network fail"));
    render(<SearchPage />);
    await userEvent.type(screen.getByRole("textbox"), "Some question here");
    await userEvent.click(screen.getByRole("button", { name: /research/i }));
    expect(await screen.findByText(/unexpected error/i)).toBeTruthy();
  });
});
