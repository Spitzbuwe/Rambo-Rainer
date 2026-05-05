import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import AdminDashboardWrapper from "../AdminDashboardWrapper.jsx";

vi.mock("../../hooks/useSocketIO.js", () => ({
  defaultSocketAdminToken: () => "test-token",
  resolveSocketUrl: (u) => u || "http://test",
  useSocketIO: vi.fn(() => ({ isConnected: false })),
}));

describe("AdminDashboardWrapper", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  function mockAllOk() {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes("/api/health")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({ status: "healthy", db: "ok", timestamp: "2026-01-01T00:00:00Z" }),
        });
      }
      if (u.includes("/api/rules/list")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ success: true, rules: [] }),
        });
      }
      if (u.includes("/api/rules/score-batch")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ ranked_rules: [] }),
        });
      }
      if (u.includes("/api/sync/agents")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ agents: [] }) });
      }
      if (u.includes("/api/db/status")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              db_size: "1 KB",
              rule_count: 0,
              history_count: 0,
              last_backup: null,
            }),
        });
      }
      return Promise.resolve({ ok: true, json: () => ({}) });
    });
  }

  it('rendert "Open Admin Dashboard" Button', () => {
    mockAllOk();
    render(<AdminDashboardWrapper apiBase="" />);
    expect(screen.getByRole("button", { name: /Open Admin Dashboard/i })).toBeInTheDocument();
    expect(screen.getByTestId("admin-ws-status")).toHaveTextContent("Offline");
  });

  it("Klick auf Button zeigt AdminDashboardLayout", async () => {
    mockAllOk();
    render(<AdminDashboardWrapper apiBase="" />);
    fireEvent.click(screen.getByRole("button", { name: /Open Admin Dashboard/i }));
    expect(await screen.findByTestId("admin-dashboard-layout")).toBeInTheDocument();
    expect(screen.getByTestId("admin-modal-overlay")).toBeInTheDocument();
  });

  it('Klick auf "Close" schließt Modal', async () => {
    mockAllOk();
    render(<AdminDashboardWrapper apiBase="" />);
    fireEvent.click(screen.getByRole("button", { name: /Open Admin Dashboard/i }));
    await screen.findByTestId("admin-dashboard-layout");
    fireEvent.click(screen.getByTestId("admin-modal-close"));
    await waitFor(() => {
      expect(screen.queryByTestId("admin-modal-overlay")).not.toBeInTheDocument();
    });
  });
});
