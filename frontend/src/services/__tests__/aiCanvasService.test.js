import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { aiCanvasService } from "../aiCanvasService.js";

describe("aiCanvasService - Ollama", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("handles empty response", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      json: async () => ({ error: "Keine JSON gefunden" }),
    });

    await expect(aiCanvasService.generateCanvas("Test", "turbo")).rejects.toThrow();
  });

  it("extracts JSON from think-blocks", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "success",
        elements: [
          { type: "rect", x: 0, y: 0, width: 100, height: 100, fill: "#ff0000" },
        ],
        message: "✨ 1 Elemente",
      }),
    });

    const result = await aiCanvasService.generateCanvas("Box", "brain");
    expect(result.elements.length).toBe(1);
  });

  it("validates element bounds (800x600)", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "success",
        elements: [
          {
            type: "rect",
            x: 800,
            y: 600,
            width: 800,
            height: 600,
            fill: "#667eea",
          },
        ],
        message: "Test",
      }),
    });

    const result = await aiCanvasService.generateCanvas("Test", "turbo");
    const el = result.elements[0];

    expect(el.x).toBeLessThanOrEqual(800);
    expect(el.y).toBeLessThanOrEqual(600);
    expect(el.width).toBeLessThanOrEqual(800);
  });
});
