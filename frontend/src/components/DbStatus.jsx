import React, { useCallback, useEffect, useState } from "react";

function hdr(adminToken, json = false) {
  const h = {};
  if (json) h["Content-Type"] = "application/json";
  const t = String(adminToken || "").trim();
  if (t) h["X-Rambo-Admin"] = t;
  return h;
}

export default function DbStatus({
  apiBase = "",
  adminToken = "",
  onBackupNow,
  onRestore,
}) {
  const [status, setStatus] = useState(null);
  const [err, setErr] = useState(null);
  const [showRestore, setShowRestore] = useState(false);
  const [restoreFile, setRestoreFile] = useState("db_backup_rules.json");

  const base = String(apiBase || "").replace(/\/$/, "");

  const load = useCallback(async () => {
    setErr(null);
    try {
      const res = await fetch(`${base}/api/db/status`, { headers: hdr(adminToken) });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.message || "status");
      setStatus(data);
    } catch (e) {
      setErr(e?.message || "Fehler");
    }
  }, [base, adminToken]);

  useEffect(() => {
    load();
  }, [load]);

  const backup = async () => {
    setErr(null);
    try {
      onBackupNow?.();
      const res = await fetch(`${base}/api/db/backup`, { method: "POST", headers: hdr(adminToken) });
      if (!res.ok) throw new Error("backup");
      await load();
    } catch (e) {
      setErr(e?.message || "backup failed");
    }
  };

  const restore = async () => {
    setErr(null);
    try {
      const res = await fetch(`${base}/api/db/restore`, {
        method: "POST",
        headers: hdr(adminToken, true),
        body: JSON.stringify({ file: restoreFile }),
      });
      if (!res.ok) throw new Error("restore");
      setShowRestore(false);
      onRestore?.();
      await load();
    } catch (e) {
      setErr(e?.message || "restore failed");
    }
  };

  return (
    <div data-testid="db-status">
      <h3 style={{ margin: "0 0 8px", fontSize: "16px" }}>Datenbank</h3>
      {err ? (
        <p data-testid="db-error" style={{ color: "#c62828" }}>
          {err}
        </p>
      ) : null}
      {status ? (
        <div data-testid="db-status-body">
          <p data-testid="db-size">Größe: {status.db_size}</p>
          <p data-testid="db-rules">Regeln: {status.rule_count}</p>
          <p data-testid="db-history">History: {status.history_count}</p>
          <p data-testid="db-last-backup">Letztes Backup: {status.last_backup || "—"}</p>
        </div>
      ) : null}
      <button type="button" data-testid="db-backup-btn" onClick={backup}>
        Backup Now
      </button>{" "}
      <button type="button" data-testid="db-restore-open" onClick={() => setShowRestore(true)}>
        Restore from Backup
      </button>
      {showRestore ? (
        <div data-testid="restore-modal" role="dialog">
          <input
            aria-label="backup file"
            value={restoreFile}
            onChange={(e) => setRestoreFile(e.target.value)}
          />
          <button type="button" onClick={restore}>
            Ausführen
          </button>
          <button type="button" data-testid="restore-close" onClick={() => setShowRestore(false)}>
            Abbrechen
          </button>
        </div>
      ) : null}
    </div>
  );
}
