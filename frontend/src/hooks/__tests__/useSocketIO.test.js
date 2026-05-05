import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSocketIO, resolveSocketUrl, defaultSocketAdminToken } from "../useSocketIO.js";

const handlers = new Map();
const mockDisconnect = vi.fn();

vi.mock("socket.io-client", () => ({
  io: vi.fn(() => {
    handlers.clear();
    return {
      on: vi.fn((ev, fn) => {
        handlers.set(ev, fn);
      }),
      off: vi.fn(),
      disconnect: mockDisconnect,
    };
  }),
}));

import { io } from "socket.io-client";

describe("useSocketIO", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    handlers.clear();
    mockDisconnect.mockClear();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  it("nach connect-Event ist isConnected true", () => {
    const { result, unmount } = renderHook(() =>
      useSocketIO("http://127.0.0.1:5035", "good-token", { enabled: true })
    );
    act(() => {
      handlers.get("connect")?.();
    });
    expect(result.current.isConnected).toBe(true);
    unmount();
    expect(mockDisconnect).toHaveBeenCalled();
  });

  it("nach disconnect ist isConnected false (z. B. abgewiesener Token / Server-Down)", () => {
    const { result } = renderHook(() =>
      useSocketIO("http://127.0.0.1:5035", "bad-token", { enabled: true })
    );
    act(() => {
      handlers.get("connect")?.();
    });
    expect(result.current.isConnected).toBe(true);
    act(() => {
      handlers.get("disconnect")?.();
    });
    expect(result.current.isConnected).toBe(false);
  });

  it("rule_updated ruft onRuleUpdated auf", () => {
    const onRule = vi.fn();
    renderHook(() =>
      useSocketIO("http://127.0.0.1:5035", "t", {
        enabled: true,
        onRuleUpdated: onRule,
      })
    );
    act(() => {
      handlers.get("rule_updated")?.({ fingerprint: "fp1", status: "created" });
    });
    expect(onRule).toHaveBeenCalledWith({ fingerprint: "fp1", status: "created" });
  });

  it("Unmount ruft socket.disconnect auf", () => {
    const { unmount } = renderHook(() =>
      useSocketIO("http://127.0.0.1:5035", "t", { enabled: true })
    );
    unmount();
    expect(mockDisconnect).toHaveBeenCalledTimes(1);
  });

  it("enabled false → io nicht aufrufen", () => {
    renderHook(() => useSocketIO("http://127.0.0.1:5035", "t", { enabled: false }));
    expect(io).not.toHaveBeenCalled();
  });

  it("resolveSocketUrl trimmt apiBase", () => {
    expect(resolveSocketUrl("http://x:5/")).toBe("http://x:5");
  });

  it("defaultSocketAdminToken liefert String", () => {
    expect(typeof defaultSocketAdminToken()).toBe("string");
    expect(defaultSocketAdminToken().length).toBeGreaterThan(0);
  });
});
