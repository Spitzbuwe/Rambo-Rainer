import React, { useCallback, useState } from "react";
import "./AdminDashboardWrapper.css";
import AdminDashboardLayout from "./AdminDashboardLayout.jsx";
import { defaultSocketAdminToken, useSocketIO } from "../hooks/useSocketIO.js";

export default function AdminDashboardWrapper({ apiBase = "" }) {
  const [showAdmin, setShowAdmin] = useState(false);
  const adminToken = defaultSocketAdminToken();
  const [socketTicks, setSocketTicks] = useState({
    rules: 0,
    agents: 0,
    db: 0,
    health: 0,
  });

  const onClose = useCallback(() => setShowAdmin(false), []);

  const { isConnected } = useSocketIO(apiBase, adminToken, {
    enabled: showAdmin,
    onRuleUpdated: () =>
      setSocketTicks((t) => ({
        ...t,
        rules: t.rules + 1,
        health: t.health + 1,
      })),
    onAgentConnected: () =>
      setSocketTicks((t) => ({
        ...t,
        agents: t.agents + 1,
        health: t.health + 1,
      })),
    onDbHealthCheck: () =>
      setSocketTicks((t) => ({
        ...t,
        db: t.db + 1,
        health: t.health + 1,
      })),
  });

  return (
    <>
      <div className="admin-dashboard-fab-wrap" data-testid="admin-fab-wrap">
        <span
          className={`admin-ws-badge ${isConnected ? "admin-ws-badge--live" : "admin-ws-badge--off"}`}
          data-testid="admin-ws-status"
          title={isConnected ? "WebSocket verbunden" : "WebSocket getrennt"}
        >
          {isConnected ? "Live" : "Offline"}
        </span>
        <button
          type="button"
          className="admin-dashboard-fab"
          onClick={() => setShowAdmin(true)}
          aria-expanded={showAdmin}
        >
          Open Admin Dashboard
        </button>
      </div>
      {showAdmin ? (
        <div
          className="admin-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="Admin dashboard"
          data-testid="admin-modal-overlay"
        >
          <div className="admin-modal-content">
            <div className="admin-modal-header">
              <button type="button" className="admin-modal-close" onClick={onClose} data-testid="admin-modal-close">
                Close
              </button>
            </div>
            <AdminDashboardLayout
              apiBase={apiBase}
              rulesRefreshTick={socketTicks.rules}
              agentsRefreshTick={socketTicks.agents}
              dbRefreshTick={socketTicks.db}
              healthRefreshTick={socketTicks.health}
            />
          </div>
        </div>
      ) : null}
    </>
  );
}
