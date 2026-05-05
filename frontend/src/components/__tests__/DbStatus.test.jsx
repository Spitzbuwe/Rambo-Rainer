import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import DbStatus from "../DbStatus.jsx";

describe("DbStatus", () => {
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
        json: () =>
          Promise.resolve({
            db_size: "1 KB",
            rule_count: 0,
            history_count: 0,
            last_backup: null,
          }),
      })
    );
    render(<DbStatus apiBase="" adminToken="t" />);
    expect(await screen.findByTestId("db-status")).toBeInTheDocument();
  });

  it("zeigt DB-Status", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            db_size: "2.5 MB",
            rule_count: 42,
            history_count: 100,
            last_backup: "2026-01-01",
          }),
      })
    );
    render(<DbStatus apiBase="" adminToken="t" />);
    expect(await screen.findByTestId("db-rules")).toHaveTextContent("42");
    expect(screen.getByTestId("db-history")).toHaveTextContent("100");
  });

  it("Backup-Button POST", async () => {
    global.fetch = vi.fn((url, opts) => {
      const u = String(url);
      if (u.includes("/status")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              db_size: "1 KB",
              rule_count: 1,
              history_count: 0,
              last_backup: null,
            }),
        });
      }
      return Promise.resolve({ ok: true, json: () => ({}) });
    });
    render(<DbStatus apiBase="" adminToken="t" />);
    await screen.findByTestId("db-status-body");
    fireEvent.click(screen.getByTestId("db-backup-btn"));
    await waitFor(() => {
      expect(global.fetch.mock.calls.some((c) => String(c[0]).includes("/api/db/backup"))).toBe(
        true
      );
    });
  });

  it("Restore-Modal öffnen und schließen", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            db_size: "1 KB",
            rule_count: 0,
            history_count: 0,
            last_backup: null,
          }),
      })
    );
    render(<DbStatus apiBase="" adminToken="t" />);
    await screen.findByTestId("db-status");
    fireEvent.click(screen.getByTestId("db-restore-open"));
    expect(await screen.findByTestId("restore-modal")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("restore-close"));
    await waitFor(() => {
      expect(screen.queryByTestId("restore-modal")).not.toBeInTheDocument();
    });
  });

  it("Fehler bei Status-API", async () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: false, json: () => ({ message: "x" }) }));
    render(<DbStatus apiBase="" adminToken="t" />);
    expect(await screen.findByTestId("db-error")).toBeInTheDocument();
  });
});
