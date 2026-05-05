import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import AdminDashboardLayout from "../AdminDashboardLayout.jsx";

describe("AdminDashboardLayout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
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

  it("rendert ohne Fehler", async () => {
    mockAllOk();
    render(<AdminDashboardLayout apiBase="" />);
    expect(await screen.findByTestId("admin-dashboard-layout")).toBeInTheDocument();
  });

  it("alle drei Wrapper sind vorhanden", async () => {
    mockAllOk();
    render(<AdminDashboardLayout apiBase="" />);
    expect(await screen.findByTestId("ranking-display-wrapper")).toBeInTheDocument();
    expect(screen.getByTestId("agent-sync-wrapper")).toBeInTheDocument();
    expect(screen.getByTestId("db-status-wrapper")).toBeInTheDocument();
  });

  it("Status-Bar unten sichtbar", async () => {
    mockAllOk();
    render(<AdminDashboardLayout apiBase="" />);
    expect(await screen.findByTestId("admin-status-bar")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("health-ok")).toBeInTheDocument();
    });
  });

  it("API-Fehler bei Ranking blockiert andere Bereiche nicht", async () => {
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
        return Promise.resolve({ ok: false, status: 500 });
      }
      if (u.includes("/api/rules/score-batch")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ ranked_rules: [] }) });
      }
      if (u.includes("/api/sync/agents")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ agents: [{ id: "a1", connected: true }] }),
        });
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
    render(<AdminDashboardLayout apiBase="" />);
    expect(await screen.findByTestId("wrapper-rules-error")).toBeInTheDocument();
    expect(await screen.findByTestId("agent-row-a1")).toBeInTheDocument();
    expect(screen.getByTestId("db-status-wrapper")).toBeInTheDocument();
  });

  it("Grid nutzt responsive Klassen", async () => {
    mockAllOk();
    const { container } = render(<AdminDashboardLayout apiBase="" />);
    const grid = await screen.findByTestId("admin-dashboard-grid");
    expect(grid.className).toContain("admin-dashboard-root");
    expect(container.querySelector(".admin-dashboard-root")).toBeTruthy();
  });
});
