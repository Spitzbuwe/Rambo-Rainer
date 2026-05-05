import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import AgentSync from "../AgentSync.jsx";

describe("AgentSync", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("rendert ohne Fehler", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ agents: [] }),
      })
    );
    render(<AgentSync apiBase="" adminToken="t" />);
    expect(await screen.findByTestId("agent-sync")).toBeInTheDocument();
  });

  it("zeigt registrierte Agenten", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            agents: [
              { id: "a1", url: "http://h", port: 1, connected: true, last_sync: "t" },
            ],
          }),
      })
    );
    render(<AgentSync apiBase="" adminToken="t" />);
    expect(await screen.findByTestId("agent-row-a1")).toBeInTheDocument();
  });

  it("Status-Indicator online vs offline", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            agents: [
              { id: "on", connected: true },
              { id: "off", connected: false },
            ],
          }),
      })
    );
    render(<AgentSync apiBase="" adminToken="t" />);
    expect(await screen.findByTestId("agent-status-on")).toHaveTextContent("🟢");
    expect(screen.getByTestId("agent-status-off")).toHaveTextContent("🔴");
  });

  it("Register öffnet Modal", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({ agents: [] }) })
    );
    render(<AgentSync apiBase="" adminToken="t" />);
    fireEvent.click(screen.getByRole("button", { name: /Register New Agent/i }));
    expect(await screen.findByTestId("register-modal")).toBeInTheDocument();
  });

  it("Sync-Button löst API-Call aus", async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes("/api/sync/agents")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              agents: [{ id: "s1", url: "http://x", port: 5, connected: true }],
            }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    render(<AgentSync apiBase="" adminToken="t" />);
    await screen.findByTestId("agent-row-s1");
    fireEvent.click(screen.getByTestId("sync-s1"));
    await waitFor(() => {
      const posts = global.fetch.mock.calls.filter((c) => c[1]?.method === "POST");
      expect(posts.some((c) => String(c[0]).includes("push-rules"))).toBe(true);
    });
  });

  it("Fehler zeigt Toast", async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes("/agents")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              agents: [{ id: "bad", url: "http://x", port: 9, connected: true }],
            }),
        });
      }
      return Promise.resolve({ ok: false, status: 500, json: () => ({}) });
    });
    render(<AgentSync apiBase="" adminToken="t" />);
    await screen.findByTestId("agent-row-bad");
    fireEvent.click(screen.getByTestId("sync-bad"));
    expect(await screen.findByTestId("agent-sync-toast")).toBeInTheDocument();
  });
});
