import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { aiCanvasService } from "../aiCanvasService.js";

describe("aiCanvasService – Ollama", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("checks Ollama status", async () => {
    global.fetch.mockResolvedValueOnce({
      json: async () => ({
        status: "ok",
        models: ["llama3.2:latest", "deepseek-r1:8b"],
        turbo: true,
        brain: true,
      }),
    });

    const status = await aiCanvasService.checkOllamaStatus();
    expect(status.status).toBe("ok");
    expect(status.turbo).toBe(true);
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("/api/canvas/ollama-status"));
  });

  it("generates canvas with turbo mode", async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "success",
        elements: [{ type: "rect", x: 0, y: 0, width: 100, height: 100, fill: "#ff0000" }],
        message: "✨ 1 Elemente generiert (Ollama turbo)",
        mode: "turbo",
      }),
    });

    const result = await aiCanvasService.generateCanvas("Rote Box", "turbo", []);
    expect(result.elements.length).toBe(1);
    expect(result.mode).toBe("turbo");
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.mode).toBe("turbo");
  });

  it("rejects when API reports error", async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ error: "Ollama läuft nicht" }),
    });

    await expect(aiCanvasService.generateCanvas("Test", "turbo")).rejects.toThrow("Ollama läuft nicht");
  });
});
