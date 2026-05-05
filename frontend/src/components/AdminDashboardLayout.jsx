import React from "react";
import "./AdminDashboardLayout.css";
import RankingDisplayWrapper from "./RankingDisplayWrapper.jsx";
import AgentSyncWrapper from "./AgentSyncWrapper.jsx";
import DbStatusWrapper from "./DbStatusWrapper.jsx";

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="admin-dashboard-error-fallback" data-testid="admin-widget-error">
          {this.props.label}: {String(this.state.error?.message || "Fehler")}
        </div>
      );
    }
    return this.props.children;
  }
}

async function fetchHealth(apiBase) {
  const base = String(apiBase || "").replace(/\/$/, "");
  const res = await fetch(`${base}/api/health`);
  if (!res.ok) throw new Error(`health ${res.status}`);
  return res.json();
}

/**
 * Zentrale Admin-Ansicht: drei Spalten + Health-Leiste.
 */
export default function AdminDashboardLayout({
  apiBase = "",
  rulesRefreshTick = 0,
  agentsRefreshTick = 0,
  dbRefreshTick = 0,
  healthRefreshTick = 0,
}) {
  const [health, setHealth] = React.useState(null);
  const [healthErr, setHealthErr] = React.useState(null);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const h = await fetchHealth(apiBase);
        if (!cancelled) {
          setHealth(h);
          setHealthErr(null);
        }
      } catch (e) {
        if (!cancelled) {
          setHealthErr(e?.message || "Health fehlgeschlagen");
          setHealth(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiBase, healthRefreshTick]);

  return (
    <div data-testid="admin-dashboard-layout">
      <h2 style={{ margin: "16px 16px 0", fontSize: "18px" }}>Admin-Dashboard</h2>
      <div className="admin-dashboard-root" data-testid="admin-dashboard-grid">
        <div className="admin-dashboard-card">
          <ErrorBoundary label="Ranking">
            <RankingDisplayWrapper apiBase={apiBase} refreshTick={rulesRefreshTick} />
          </ErrorBoundary>
        </div>
        <div className="admin-dashboard-card">
          <ErrorBoundary label="Agent-Sync">
            <AgentSyncWrapper apiBase={apiBase} liveRefreshTick={agentsRefreshTick} />
          </ErrorBoundary>
        </div>
        <div className="admin-dashboard-card">
          <ErrorBoundary label="DB-Status">
            <DbStatusWrapper apiBase={apiBase} liveRefreshTick={dbRefreshTick} />
          </ErrorBoundary>
        </div>
        <div className="admin-dashboard-bottom" data-testid="admin-status-bar">
          <strong>Backend-Health:</strong>{" "}
          {healthErr ? (
            <span data-testid="health-error" style={{ color: "#c62828" }}>
              {healthErr}
            </span>
          ) : health ? (
            <span data-testid="health-ok">
              {health.status} — db: {health.db} — {health.timestamp}
            </span>
          ) : (
            <span>…</span>
          )}
        </div>
      </div>
    </div>
  );
}
