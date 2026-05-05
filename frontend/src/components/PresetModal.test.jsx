import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup, within } from "@testing-library/react";
import PresetModal from "./PresetModal.jsx";

describe("PresetModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("rendert nicht wenn isOpen=false", () => {
    const { container } = render(
      <PresetModal isOpen={false} onClose={vi.fn()} onApplySuccess={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("zeigt Loading-Spinner während fetch läuft", async () => {
    global.fetch = vi.fn(() => new Promise(() => {}));
    render(<PresetModal isOpen={true} onClose={vi.fn()} onApplySuccess={vi.fn()} apiBase="" />);
    expect(await screen.findByText(/Presets werden geladen/i)).toBeInTheDocument();
  });

  it("lädt Presets und zeigt sie an", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            presets: [
              { id: "p1", name: "Strict", description: "Strict rules" },
              { id: "p2", name: "Permissive", description: "Permissive rules" },
            ],
          }),
      })
    );

    render(<PresetModal isOpen={true} onClose={vi.fn()} onApplySuccess={vi.fn()} apiBase="" />);

    await waitFor(() => {
      expect(screen.getByText("Strict")).toBeInTheDocument();
      expect(screen.getByText("Permissive")).toBeInTheDocument();
    });
  });

  it("zeigt Error-Message bei Fetch-Fehler", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ error: "Server error" }),
      })
    );

    render(<PresetModal isOpen={true} onClose={vi.fn()} onApplySuccess={vi.fn()} apiBase="" />);

    await waitFor(() => {
      expect(screen.getByText(/Server error/i)).toBeInTheDocument();
    });
  });

  it("ruft onClose auf wenn Cancel-Button geklickt wird", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            presets: [{ id: "p1", name: "Test" }],
          }),
      })
    );

    const onClose = vi.fn();
    render(<PresetModal isOpen={true} onClose={onClose} onApplySuccess={vi.fn()} apiBase="" />);

    await waitFor(() => {
      expect(screen.getByText("Test")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Abbrechen" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("ruft onClose auf wenn X-Button geklickt wird", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            presets: [{ id: "p1", name: "Test" }],
          }),
      })
    );

    const onClose = vi.fn();
    render(<PresetModal isOpen={true} onClose={onClose} onApplySuccess={vi.fn()} apiBase="" />);

    await waitFor(() => {
      expect(screen.getByText("Test")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Schließen/i }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("sendet POST mit korrektem preset (Backend-Feld) bei Apply", async () => {
    global.fetch = vi.fn((url, options) => {
      const u = String(url);
      if (u.includes("/api/rules/presets/apply")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ success: true }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            presets: [
              { id: "p1", name: "Preset 1" },
              { id: "p2", name: "Preset 2" },
            ],
          }),
      });
    });

    render(<PresetModal isOpen={true} onClose={vi.fn()} onApplySuccess={vi.fn()} apiBase="" />);

    await waitFor(() => {
      expect(screen.getByText("Preset 1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Anwenden" }));

    await waitFor(() => {
      const postCalls = global.fetch.mock.calls.filter(
        (call) => call[1] && call[1].method === "POST"
      );
      expect(postCalls.length).toBeGreaterThan(0);
      const body = JSON.parse(postCalls[0][1].body);
      expect(body.preset).toBe("p1");
      expect(body.merge).toBe(true);
    });
  });

  it("ruft onApplySuccess und onClose nach erfolgreichem Apply auf", async () => {
    global.fetch = vi.fn((url, options) => {
      const u = String(url);
      if (u.includes("/api/rules/presets/apply")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ success: true }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            presets: [{ id: "p1", name: "Test Preset" }],
          }),
      });
    });

    const onApplySuccess = vi.fn();
    const onClose = vi.fn();

    render(
      <PresetModal isOpen={true} onClose={onClose} onApplySuccess={onApplySuccess} apiBase="" />
    );

    await waitFor(() => {
      expect(screen.getByText("Test Preset")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Anwenden" }));

    await waitFor(
      () => {
        expect(onApplySuccess).toHaveBeenCalledTimes(1);
        expect(onClose).toHaveBeenCalled();
      },
      { timeout: 2500 }
    );
  });

  it("zeigt Erfolgs-Message nach erfolgreichem Apply", async () => {
    global.fetch = vi.fn((url, options) => {
      const u = String(url);
      if (u.includes("/api/rules/presets/apply")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ success: true }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            presets: [{ id: "p1", name: "Test" }],
          }),
      });
    });

    render(<PresetModal isOpen={true} onClose={vi.fn()} onApplySuccess={vi.fn()} apiBase="" />);

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Test")).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: "Anwenden" }));

    await waitFor(() => {
      expect(screen.getByText(/erfolgreich angewendet/i)).toBeInTheDocument();
    });
  });

  it("deaktiviert Anwenden wenn keine Presets geladen sind", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ presets: [] }),
      })
    );

    render(<PresetModal isOpen={true} onClose={vi.fn()} onApplySuccess={vi.fn()} apiBase="" />);

    await waitFor(() => {
      expect(screen.getByText(/Keine Presets verfügbar/i)).toBeInTheDocument();
    });

    const applyButton = screen.getByRole("button", { name: /Anwenden/i });
    expect(applyButton).toBeDisabled();
  });

  it("handhabt leere Presets-Liste (keine Presets verfügbar)", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ presets: [] }),
      })
    );

    render(<PresetModal isOpen={true} onClose={vi.fn()} onApplySuccess={vi.fn()} apiBase="" />);

    await waitFor(() => {
      expect(screen.getByText(/Keine Presets verfügbar/i)).toBeInTheDocument();
    });
  });

  it("ruft onClose auf wenn Escape-Taste gedrückt wird", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            presets: [{ id: "p1", name: "Test" }],
          }),
      })
    );

    const onClose = vi.fn();
    render(<PresetModal isOpen={true} onClose={onClose} onApplySuccess={vi.fn()} apiBase="" />);

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Test")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
