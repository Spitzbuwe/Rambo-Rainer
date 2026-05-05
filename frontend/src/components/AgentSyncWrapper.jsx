import React, { useCallback, useEffect, useState } from "react";
import AgentSync from "./AgentSync.jsx";

function defaultAdminToken() {
  if (typeof import.meta !== "undefined" && import.meta.env?.VITE_RAMBO_ADMIN_TOKEN) {
    return String(import.meta.env.VITE_RAMBO_ADMIN_TOKEN);
  }
  return "Rambo-Admin-Token";
}

/**
 * Erzwingt periodisches Neu-Mount von AgentSync (Polling) + Refresh-Button.
 */
export default function AgentSyncWrapper({
  apiBase = "",
  refreshIntervalMs = 5000,
  liveRefreshTick = 0,
  onRegisterAgent: onRegisterAgentProp,
  onSyncNow: onSyncNowProp,
  onPullNow: onPullNowProp,
}) {
  const [agentMountKey, setAgentMountKey] = useState(0);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [status, setStatus] = useState("");
  const adminToken = defaultAdminToken();

  const bump = useCallback(() => {
    setAgentMountKey((k) => k + 1);
    setLastRefresh(new Date().toISOString());
    setStatus("ok");
  }, []);

  useEffect(() => {
    bump();
    const id = setInterval(bump, refreshIntervalMs);
    return () => clearInterval(id);
  }, [bump, refreshIntervalMs]);

  useEffect(() => {
    if (liveRefreshTick > 0) bump();
  }, [liveRefreshTick, bump]);

  const onRegisterAgent = useCallback(
    (id, url, port) => {
      onRegisterAgentProp?.(id, url, port);
      setStatus("register");
    },
    [onRegisterAgentProp]
  );

  const onSyncRules = useCallback(
    (agentId) => {
      onSyncNowProp?.(agentId);
    },
    [onSyncNowProp]
  );

  const onPullRules = useCallback(
    (agentId) => {
      onPullNowProp?.(agentId);
    },
    [onPullNowProp]
  );

  return (
    <div data-testid="agent-sync-wrapper">
      <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
        <button type="button" data-testid="agent-refresh-now" onClick={bump}>
          Refresh now
        </button>
        {lastRefresh ? (
          <span data-testid="agent-last-refresh" style={{ fontSize: "12px", color: "#555" }}>
            {lastRefresh}
          </span>
        ) : null}
        {status ? (
          <span data-testid="agent-wrapper-status" style={{ fontSize: "12px" }}>
            {status}
          </span>
        ) : null}
      </div>
      <AgentSync
        key={agentMountKey}
        apiBase={apiBase}
        adminToken={adminToken}
        onRegisterAgent={onRegisterAgent}
        onSyncRules={onSyncRules}
        onPullRules={onPullRules}
      />
    </div>
  );
}
