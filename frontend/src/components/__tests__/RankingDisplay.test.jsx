import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import RankingDisplay from "../RankingDisplay.jsx";

describe("RankingDisplay", () => {
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
        json: () => Promise.resolve({ ranked_rules: [] }),
      })
    );
    render(<RankingDisplay apiBase="" adminToken="t" />);
    expect(await screen.findByTestId("ranking-display")).toBeInTheDocument();
  });

  it("sortiert nach Score (höchster zuerst)", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            ranked_rules: [
              { rule_id: "a", score: 0.2, reason: "r", heuristics: { keyword_match: 0.1 } },
              { rule_id: "b", score: 0.9, reason: "r2", heuristics: { keyword_match: 0.8 } },
            ],
          }),
      })
    );
    const { container } = render(<RankingDisplay apiBase="" adminToken="t" />);
    await waitFor(() => {
      const ul = container.querySelector('[data-testid="ranking-display"] ul');
      expect(ul).toBeTruthy();
      const rows = ul.querySelectorAll('[data-testid^="rank-row-"]');
      expect(rows[0].getAttribute("data-testid")).toBe("rank-row-b");
    });
  });

  it("Score-Balken: 0.5 ≈ 50% Breite", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            ranked_rules: [{ rule_id: "x", score: 0.5, reason: "", heuristics: {} }],
          }),
      })
    );
    render(<RankingDisplay apiBase="" adminToken="t" />);
    const bar = await screen.findByTestId("score-bar-x");
    const inner = bar.querySelector("div");
    expect(inner.style.width).toBe("50%");
  });

  it("View Details öffnet Heuristik-Block", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            ranked_rules: [
              {
                rule_id: "d1",
                score: 0.8,
                reason: "kw",
                heuristics: { keyword_match: 0.7, success_rate: 0.5 },
              },
            ],
          }),
      })
    );
    render(<RankingDisplay apiBase="" adminToken="t" />);
    await screen.findByTestId("rank-row-d1");
    fireEvent.click(screen.getByTestId("details-btn-d1"));
    expect(await screen.findByTestId("details-d1")).toHaveTextContent("keyword_match");
  });

  it("Details zeigen success_rate", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            ranked_rules: [
              {
                rule_id: "e1",
                score: 0.5,
                reason: "",
                heuristics: { keyword_match: 0, success_rate: 0.88 },
              },
            ],
          }),
      })
    );
    render(<RankingDisplay apiBase="" adminToken="t" />);
    await screen.findByTestId("rank-row-e1");
    fireEvent.click(screen.getByTestId("details-btn-e1"));
    expect(await screen.findByTestId("details-e1")).toHaveTextContent("success_rate");
  });

  it("Fetch nutzt POST mit Context-JSON", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ ranked_rules: [] }),
      })
    );
    const ctx = { text: "hello world" };
    render(<RankingDisplay apiBase="http://x" adminToken="tok" context={ctx} />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    const call = global.fetch.mock.calls.find((c) => String(c[0]).includes("score-batch"));
    expect(call).toBeTruthy();
    expect(call[1].method).toBe("POST");
    const body = JSON.parse(call[1].body);
    expect(body.context).toEqual(ctx);
    expect(call[1].headers["X-Rambo-Admin"]).toBe("tok");
  });
});
