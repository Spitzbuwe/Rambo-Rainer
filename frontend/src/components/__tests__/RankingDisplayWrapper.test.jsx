import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import RankingDisplayWrapper from "../RankingDisplayWrapper.jsx";

describe("RankingDisplayWrapper", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("rendert ohne Fehler", async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes("/api/rules/list")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ success: true, rules: [] }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ ranked_rules: [] }),
      });
    });
    render(<RankingDisplayWrapper apiBase="" />);
    expect(await screen.findByTestId("ranking-display-wrapper")).toBeInTheDocument();
  });

  it("GET /api/rules/list beim Mount", async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes("/api/rules/list")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ success: true, rules: [{ fingerprint: "a", text: "t" }] }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ ranked_rules: [{ rule_id: "a", score: 0.5, reason: "", heuristics: {} }] }),
      });
    });
    render(<RankingDisplayWrapper apiBase="" />);
    await waitFor(() => {
      expect(global.fetch.mock.calls.some((c) => String(c[0]).includes("/api/rules/list"))).toBe(true);
    });
  });

  it("Context-Input triggert debounced score-batch", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes("/api/rules/list")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ success: true, rules: [{ fingerprint: "f1", text: "hello" }] }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ ranked_rules: [] }),
      });
    });
    render(<RankingDisplayWrapper apiBase="" />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    const batchBefore = global.fetch.mock.calls.filter((c) => String(c[0]).includes("score-batch")).length;
    fireEvent.change(screen.getByTestId("context-input"), { target: { value: "hello scoring" } });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    const batchAfter = global.fetch.mock.calls.filter((c) => String(c[0]).includes("score-batch")).length;
    expect(batchAfter).toBeGreaterThan(batchBefore);
    vi.useRealTimers();
  });

  it("zeigt Fehler bei Rules-Fetch", async () => {
    global.fetch = vi.fn((url) => {
      const u = String(url);
      if (u.includes("/api/rules/list")) {
        return Promise.resolve({ ok: false, status: 500 });
      }
      if (u.includes("/api/rules/score-batch")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ ranked_rules: [] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
    render(<RankingDisplayWrapper apiBase="" />);
    expect(await screen.findByTestId("wrapper-rules-error")).toBeInTheDocument();
  });
});
