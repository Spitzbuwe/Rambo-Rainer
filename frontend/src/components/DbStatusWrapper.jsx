import React, { useCallback, useEffect, useState } from "react";
import DbStatus from "./DbStatus.jsx";

function defaultAdminToken() {
  if (typeof import.meta !== "undefined" && import.meta.env?.VITE_RAMBO_ADMIN_TOKEN) {
    return String(import.meta.env.VITE_RAMBO_ADMIN_TOKEN);
  }
  return "Rambo-Admin-Token";
}

export default function DbStatusWrapper({ apiBase = "", liveRefreshTick = 0, onBackupNow, onRestore }) {
  const [mountKey, setMountKey] = useState(0);
  const [lastRefresh, setLastRefresh] = useState(null);
  const adminToken = defaultAdminToken();

  const refresh = useCallback(() => {
    setMountKey((k) => k + 1);
    setLastRefresh(new Date().toISOString());
  }, []);

  useEffect(() => {
    if (liveRefreshTick > 0) refresh();
  }, [liveRefreshTick, refresh]);

  return (
    <div data-testid="db-status-wrapper">
      <div style={{ marginBottom: "8px" }}>
        <button type="button" data-testid="db-wrapper-refresh" onClick={refresh}>
          Status neu laden
        </button>
        {lastRefresh ? (
          <span data-testid="db-last-refresh" style={{ marginLeft: "8px", fontSize: "12px", color: "#555" }}>
            {lastRefresh}
          </span>
        ) : null}
      </div>
      <DbStatus
        key={mountKey}
        apiBase={apiBase}
        adminToken={adminToken}
        onBackupNow={onBackupNow}
        onRestore={onRestore}
      />
    </div>
  );
}
