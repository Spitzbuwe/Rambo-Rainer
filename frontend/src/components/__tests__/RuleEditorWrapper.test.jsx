import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup, within } from "@testing-library/react";
import RuleEditorWrapper from "../RuleEditorWrapper.jsx";

describe("RuleEditorWrapper", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("rendert ohne Fehler", () => {
    const { container } = render(<RuleEditorWrapper />);
    expect(container.querySelector('[data-testid="rule-editor-wrapper"]')).toBeTruthy();
  });

  it('zeigt den Button "Use Preset"', () => {
    render(<RuleEditorWrapper />);
    expect(screen.getByRole("button", { name: /Use Preset/i })).toBeInTheDocument();
  });

  it('öffnet PresetModal nach Klick auf "Use Preset"', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            presets: [{ id: "p1", name: "Test Preset" }],
          }),
      })
    );

    render(<RuleEditorWrapper apiBase="" />);
    fireEvent.click(screen.getByRole("button", { name: /Use Preset/i }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Test Preset")).toBeInTheDocument();
  });

  it("schließt das Modal über den X-Button", async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            presets: [{ id: "p1", name: "Test Preset" }],
          }),
      })
    );

    render(<RuleEditorWrapper apiBase="" />);
    fireEvent.click(screen.getByRole("button", { name: /Use Preset/i }));

    await screen.findByRole("dialog");
    fireEvent.click(screen.getByRole("button", { name: /Schließen/i }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("ruft onApplyPreset nach erfolgreichem Preset-Anwenden auf", async () => {
    global.fetch = vi.fn((url) => {
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
            presets: [{ id: "p1", name: "Apply Me" }],
          }),
      });
    });

    const onApplyPreset = vi.fn();
    render(
      <RuleEditorWrapper apiBase="" onApplyPreset={onApplyPreset} />
    );

    fireEvent.click(screen.getByRole("button", { name: /Use Preset/i }));
    await waitFor(() => {
      expect(screen.getByText("Apply Me")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Anwenden" }));

    await waitFor(
      () => {
        expect(onApplyPreset).toHaveBeenCalledTimes(1);
      },
      { timeout: 2500 }
    );
  });

  it("ruft onMergeRules nach erfolgreichem Anwenden auf (Merge über PresetModal)", async () => {
    global.fetch = vi.fn((url) => {
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
            presets: [{ id: "p1", name: "Merge Preset" }],
          }),
      });
    });

    const onMergeRules = vi.fn();
    render(<RuleEditorWrapper apiBase="" onMergeRules={onMergeRules} />);

    fireEvent.click(screen.getByRole("button", { name: /Use Preset/i }));
    await waitFor(() => {
      expect(screen.getByText("Merge Preset")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Anwenden" }));

    await waitFor(
      () => {
        expect(onMergeRules).toHaveBeenCalledTimes(1);
      },
      { timeout: 2500 }
    );
  });

  it("aktualisiert selectedRule wenn initialRule sich ändert", () => {
    const { rerender } = render(
      <RuleEditorWrapper initialRule={{ fingerprint: "fp-alpha" }} />
    );
    expect(screen.getByTestId("rule-editor-selected")).toHaveTextContent("fp-alpha");

    rerender(<RuleEditorWrapper initialRule={{ fingerprint: "fp-beta" }} />);
    expect(screen.getByTestId("rule-editor-selected")).toHaveTextContent("fp-beta");
  });

  it("PresetModal erhält die erwarteten Props (isOpen, onClose, onApplySuccess, apiBase)", async () => {
    const apiBase = "http://127.0.0.1:5999";
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            presets: [{ id: "p1", name: "Remote" }],
          }),
      })
    );

    render(<RuleEditorWrapper apiBase={apiBase} />);
    fireEvent.click(screen.getByRole("button", { name: /Use Preset/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
      const firstUrl = String(global.fetch.mock.calls[0][0]);
      expect(firstUrl).toBe(`${apiBase}/api/rules/presets`);
    });

    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Remote")).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: /Schließen/i }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });
});
