import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import AgentSyncWrapper from "../AgentSyncWrapper.jsx";

describe("AgentSyncWrapper", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("rendert ohne Fehler", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({ agents: [] }) })
    );
    render(<AgentSyncWrapper apiBase="" refreshIntervalMs={60000} />);
    expect(await screen.findByTestId("agent-sync-wrapper")).toBeInTheDocument();
  });

  it("GET /api/sync/agents wird aufgerufen", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({ agents: [] }) })
    );
    render(<AgentSyncWrapper apiBase="" refreshIntervalMs={60000} />);
    await waitFor(() => {
      expect(global.fetch.mock.calls.some((c) => String(c[0]).includes("/api/sync/agents"))).toBe(true);
    });
  });

  it("Refresh-Interval lädt erneut", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({ agents: [] }) })
    );
    render(<AgentSyncWrapper apiBase="" refreshIntervalMs={5000} />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    const n1 = global.fetch.mock.calls.filter((c) => String(c[0]).includes("/api/sync/agents")).length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    const n2 = global.fetch.mock.calls.filter((c) => String(c[0]).includes("/api/sync/agents")).length;
    expect(n2).toBeGreaterThan(n1);
  });

  it("Register triggert API-Call", async () => {
    global.fetch = vi.fn((url, opts) => {
      const u = String(url);
      if (u.includes("/api/sync/agents")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ agents: [] }) });
      }
      if (u.includes("/api/sync/register-agent")) {
        return Promise.resolve({ ok: true, json: () => ({}) });
      }
      return Promise.resolve({ ok: true, json: () => ({}) });
    });
    render(<AgentSyncWrapper apiBase="" refreshIntervalMs={60000} />);
    await screen.findByTestId("agent-sync");
    fireEvent.click(screen.getByRole("button", { name: /Register New Agent/i }));
    fireEvent.change(screen.getByLabelText(/agent id/i), { target: { value: "agent-x" } });
    fireEvent.click(screen.getByRole("button", { name: /^Save$/i }));
    await waitFor(() => {
      expect(global.fetch.mock.calls.some((c) => String(c[0]).includes("/api/sync/register-agent"))).toBe(
        true
      );
    });
  });
});
