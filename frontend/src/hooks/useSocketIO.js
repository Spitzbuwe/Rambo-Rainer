import { useEffect, useRef, useState } from "react";
import { io } from "socket.io-client";

/**
 * Ermittelt die Socket.IO-Basis-URL.
 * - Mit gesetztem apiBase: direkt ans Backend.
 * - Dev + leeres apiBase: gleicher Origin wie Vite (Proxy /socket.io → 5035).
 */
export function resolveSocketUrl(apiBase) {
  const b = String(apiBase || "").replace(/\/$/, "");
  if (b) return b;
  if (typeof window !== "undefined" && window.location?.host) {
    return `${window.location.protocol}//${window.location.host}`;
  }
  if (typeof import.meta !== "undefined" && import.meta.env?.DEV) {
    return "http://127.0.0.1:3000";
  }
  return "http://127.0.0.1:5035";
}

export function defaultSocketAdminToken() {
  if (typeof import.meta !== "undefined" && import.meta.env?.VITE_RAMBO_ADMIN_TOKEN) {
    return String(import.meta.env.VITE_RAMBO_ADMIN_TOKEN).trim();
  }
  return "";
}

/**
 * Live-Updates fürs Admin-Dashboard (Phase 22b).
 *
 * @param {string} apiBase – wie in der App (kann "" sein → Vite-Proxy)
 * @param {string} [adminToken] – fallback defaultSocketAdminToken()
 * @param {object} [options]
 * @param {boolean} [options.enabled=true]
 * @param {(data: object) => void} [options.onRuleUpdated]
 * @param {(data: object) => void} [options.onAgentConnected]
 * @param {(data: object) => void} [options.onDbHealthCheck]
 * @param {(data: object) => void} [options.onAdminConnected]
 */
export function useSocketIO(apiBase, adminToken, options = {}) {
  const enabled = options.enabled !== false;
  const optsRef = useRef(options);
  optsRef.current = options;

  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!enabled) {
      setIsConnected(false);
      return undefined;
    }

    const url = resolveSocketUrl(apiBase);
    const token = adminToken ?? defaultSocketAdminToken();
    const isDev = typeof import.meta !== "undefined" && !!import.meta.env?.DEV;
    const socket = io(url, {
      query: { admin_token: token || "test" },
      reconnection: true,
      reconnectionDelay: 1000,
      // Dev/HMR: zuerst polling, um WebSocket send-Races beim Hot-Reload zu vermeiden.
      transports: isDev ? ["polling", "websocket"] : ["websocket", "polling"],
      upgrade: !isDev,
      rememberUpgrade: !isDev,
    });

    const handleConnect = () => setIsConnected(true);
    const handleDisconnect = () => setIsConnected(false);

    socket.on("connect", handleConnect);
    socket.on("disconnect", handleDisconnect);
    socket.on("connect_error", (err) => {
      console.warn("[socket] connect_error:", err?.message || err);
      setIsConnected(false);
    });
    socket.on("admin_connected", (data) => {
      console.log("Admin OK", data);
      optsRef.current.onAdminConnected?.(data);
    });
    socket.on("rule_updated", (data) => {
      console.log("Rule updated:", data);
      optsRef.current.onRuleUpdated?.(data);
    });
    socket.on("agent_connected", (data) => {
      console.log("Agent connected:", data);
      optsRef.current.onAgentConnected?.(data);
    });
    socket.on("db_health_check", (data) => {
      console.log("DB health:", data);
      optsRef.current.onDbHealthCheck?.(data);
    });

    return () => {
      socket.off("connect", handleConnect);
      socket.off("disconnect", handleDisconnect);
      try {
        // Dev/HMR/StrictMode: Reconnect-Timer und Heartbeat-Pings abschalten,
        // bevor disconnect() intern transport.send() aufruft — sonst TypeError.
        if (socket.io?.opts) socket.io.opts.reconnection = false;
        socket.io?.removeAllListeners?.();
        socket.io?.engine?.removeAllListeners?.();
        if (typeof socket.disconnect === "function") {
          socket.disconnect();
        } else if (typeof socket.close === "function") {
          socket.close();
        }
      } catch (err) {
        console.warn("[socket] cleanup disconnect skipped:", err?.message || err);
      }
      setIsConnected(false);
    };
  }, [apiBase, adminToken, enabled]);

  return { isConnected };
}
