import React from "react";
import { describe, test, expect, afterEach, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import ChatPanel from "../ChatPanel.jsx";
import { chatService } from "../../services/chatService.js";
import { createInitialCanvasState } from "../../store/canvasStore.js";

vi.mock("../../services/chatService.js", () => ({
  chatService: {
    sendMessage: vi.fn(),
    getHistory: vi.fn(),
  },
}));

vi.mock("../../services/aiCanvasService.js", () => ({
  aiCanvasService: {
    generateCanvas: vi.fn().mockRejectedValue(new Error("KEIN_API_KEY_TEST")),
    checkOllamaStatus: vi.fn().mockResolvedValue({ status: "offline" }),
  },
}));

describe("ChatPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  test("renders chat panel", () => {
    render(<ChatPanel messages={[]} onMessage={() => {}} />);
    expect(screen.getByText(/Designer Assistant/i)).toBeInTheDocument();
  });

  test("sends message", async () => {
    const onMessage = vi.fn();
    chatService.sendMessage.mockResolvedValue({
      id: "1",
      role: "assistant",
      content: "Response",
      timestamp: new Date().toISOString(),
    });

    render(<ChatPanel messages={[]} onMessage={onMessage} />);

    const input = screen.getByPlaceholderText(/Beschreibe dein Design/);
    fireEvent.change(input, { target: { value: "Test" } });
    fireEvent.click(screen.getByRole("button", { name: /Nachricht senden/i }));

    await waitFor(() => {
      expect(onMessage).toHaveBeenCalled();
      expect(chatService.sendMessage).toHaveBeenCalledWith("Test");
    });
  });

  test("Canvas-Befehl aktualisiert Canvas ohne Chat-API", async () => {
    const onMessage = vi.fn();
    const onCanvasUpdate = vi.fn();
    chatService.sendMessage.mockResolvedValue({ id: "x", content: "noop", timestamp: new Date().toISOString() });

    render(
      <ChatPanel
        messages={[]}
        onMessage={onMessage}
        canvasState={createInitialCanvasState()}
        onCanvasUpdate={onCanvasUpdate}
      />,
    );

    const input = screen.getByPlaceholderText(/Beschreibe dein Design/);
    fireEvent.change(input, { target: { value: "Erstelle eine rote Box" } });
    fireEvent.click(screen.getByRole("button", { name: /Nachricht senden/i }));

    await waitFor(() => {
      expect(onCanvasUpdate).toHaveBeenCalled();
      const next = onCanvasUpdate.mock.calls[0][0];
      expect(next.elements).toHaveLength(1);
      expect(next.elements[0].type).toBe("rect");
      expect(next.elements[0].fill).toBe("#ff0000");
      expect(chatService.sendMessage).not.toHaveBeenCalled();
    });
  });
});
