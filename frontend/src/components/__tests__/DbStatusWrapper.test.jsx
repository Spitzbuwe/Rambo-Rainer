import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import DbStatusWrapper from "../DbStatusWrapper.jsx";

describe("DbStatusWrapper", () => {
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
    render(<DbStatusWrapper apiBase="" />);
    expect(await screen.findByTestId("db-status-wrapper")).toBeInTheDocument();
  });

  it("GET /api/db/status beim Mount", async () => {
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
    render(<DbStatusWrapper apiBase="" />);
    await waitFor(() => {
      expect(global.fetch.mock.calls.some((c) => String(c[0]).includes("/api/db/status"))).toBe(true);
    });
  });

  it("Backup-Button triggert POST /api/db/backup", async () => {
    global.fetch = vi.fn((url, opts) => {
      const u = String(url);
      if (u.includes("/api/db/status")) {
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
      if (u.includes("/api/db/backup")) {
        return Promise.resolve({ ok: true, json: () => ({}) });
      }
      return Promise.resolve({ ok: true, json: () => ({}) });
    });
    render(<DbStatusWrapper apiBase="" />);
    await screen.findByTestId("db-backup-btn");
    fireEvent.click(screen.getByTestId("db-backup-btn"));
    await waitFor(() => {
      expect(global.fetch.mock.calls.some((c) => String(c[0]).includes("/api/db/backup"))).toBe(true);
    });
  });
});
