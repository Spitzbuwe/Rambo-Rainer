import React, { useCallback, useEffect, useState } from 'react';
import './RamboManagementDashboard.css';

function defaultApiBase() {
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE) {
    return String(import.meta.env.VITE_API_BASE).replace(/\/$/, '');
  }
  if (typeof import.meta !== 'undefined' && import.meta.env?.DEV && !import.meta.env?.VITE_API_BASE) {
    return '';
  }
  return 'http://127.0.0.1:5002';
}

function defaultAdminToken() {
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_RAMBO_ADMIN_TOKEN) {
    return String(import.meta.env.VITE_RAMBO_ADMIN_TOKEN);
  }
  return '';
}

async function fetchJson(url, headers = {}) {
  const res = await fetch(url, { headers });
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function isHealthOnline(body) {
  const s = body && typeof body === 'object' ? String(body.status || '').toLowerCase() : '';
  return s === 'backend_ok';
}

function totalRulesFromSummary(s) {
  if (!s || typeof s !== 'object') return 0;
  if (typeof s.rules_total === 'number') return s.rules_total;
  if (typeof s.total_rules === 'number') return s.total_rules;
  return 0;
}

function totalGroupsFromSummary(s) {
  if (!s || typeof s !== 'object') return 0;
  if (typeof s.total_groups === 'number') return s.total_groups;
  const bg = s.count_by_group;
  if (bg && typeof bg === 'object') return Object.keys(bg).length;
  return 0;
}

function activeRulesCount(summary, status) {
  if (status && typeof status.active_rules_count === 'number') return status.active_rules_count;
  if (summary && typeof summary.count_active === 'number') return summary.count_active;
  return null;
}

function historyLabel(entry) {
  if (!entry || typeof entry !== 'object') return '—';
  return entry.event || entry.action || '—';
}

const TT_HEALTH_CARD =
  'Rambo-Health: GET …/api/health (mit Dashboard-Basis-URL). Online nur wenn JSON.status „backend_ok“. Offline = Flask nicht erreichbar, falscher Port (Standard 5002) oder CORS bei direkt geöffneter index.html.';
const HEALTH_SOURCE_NOTE = 'Quelle: /api/health (status=backend_ok)';

export function HealthCard({ online, detail }) {
  const ok = Boolean(online);
  return (
    <section className="rambo-mgmt-card" aria-label="Health" title={TT_HEALTH_CARD}>
      <h3 className="rambo-mgmt-card__title">Health</h3>
      <div className="rambo-mgmt-card__row">
        <span className={`rambo-mgmt-card__icon ${ok ? 'rambo-mgmt-card__icon--ok' : 'rambo-mgmt-card__icon--bad'}`} aria-hidden>
          {ok ? '●' : '●'}
        </span>
        <div>
          <strong>{ok ? 'Online' : 'Offline'}</strong>
          {detail ? <div className="rambo-mgmt-card__muted">{detail}</div> : null}
          <div className="rambo-mgmt-card__muted">{HEALTH_SOURCE_NOTE}</div>
        </div>
      </div>
    </section>
  );
}

export function SummaryCard({ summary }) {
  const tr = totalRulesFromSummary(summary);
  const tg = totalGroupsFromSummary(summary);
  return (
    <section className="rambo-mgmt-card" aria-label="Policy Summary">
      <h3 className="rambo-mgmt-card__title">Policy Summary</h3>
      <div className="rambo-mgmt-card__row">
        <span className="rambo-mgmt-card__icon rambo-mgmt-card__icon--ok" aria-hidden>
          ◆
        </span>
        <div>
          <div>
            <strong>{tr}</strong> Regeln gesamt
          </div>
          <div className="rambo-mgmt-card__muted">{tg} Gruppen (mit Einträgen)</div>
        </div>
      </div>
    </section>
  );
}

export function StatusCard({ summary, status, historyEntries }) {
  const active = activeRulesCount(summary, status);
  const histTotal = status && typeof status.rule_history_entries === 'number' ? status.rule_history_entries : null;
  const rollback = status?.rollback_available;
  const top3 = Array.isArray(historyEntries) ? historyEntries.slice(0, 3) : [];

  return (
    <section className="rambo-mgmt-card" aria-label="Status">
      <h3 className="rambo-mgmt-card__title">Status &amp; Verlauf</h3>
      <div className="rambo-mgmt-card__row">
        <span className="rambo-mgmt-card__icon rambo-mgmt-card__icon--ok" aria-hidden>
          ◈
        </span>
        <div>
          <div>
            Aktive Regeln: <strong>{active != null ? active : '—'}</strong>
          </div>
          {histTotal != null ? (
            <div className="rambo-mgmt-card__muted">History-Einträge (gesamt): {histTotal}</div>
          ) : null}
          {typeof rollback === 'boolean' ? (
            <div className="rambo-mgmt-card__muted">Rollback: {rollback ? 'verfügbar' : 'nicht verfügbar'}</div>
          ) : null}
        </div>
      </div>
      {top3.length > 0 ? (
        <ul className="rambo-mgmt-card__list">
          {top3.map((e) => (
            <li key={e.id || `${historyLabel(e)}-${e.timestamp}`}>
              <span className="rambo-mgmt-card__muted">{e.timestamp || '—'}</span> — {historyLabel(e)}
            </li>
          ))}
        </ul>
      ) : (
        <p className="rambo-mgmt-card__muted">Keine History-Einträge.</p>
      )}
    </section>
  );
}

export function PresetsCard({ presets }) {
  const list = Array.isArray(presets) ? presets : [];
  return (
    <section className="rambo-mgmt-card" aria-label="Presets">
      <h3 className="rambo-mgmt-card__title">Presets</h3>
      {list.length === 0 ? (
        <p className="rambo-mgmt-card__muted">Keine Presets geladen.</p>
      ) : (
        <ul className="rambo-mgmt-card__list">
          {list.map((p) => (
            <li key={p.id || p.name}>
              <strong>{p.name || p.id}</strong>
              {p.id && p.name !== p.id ? <span className="rambo-mgmt-card__muted"> ({p.id})</span> : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function BackupCard({ backup }) {
  const ok = backup && backup.success !== false;
  const ts = backup?.created_at || backup?.timestamp;
  const available = ok && Boolean(ts);

  return (
    <section className="rambo-mgmt-card" aria-label="Backup">
      <h3 className="rambo-mgmt-card__title">Backup</h3>
      <div className="rambo-mgmt-card__row">
        <span
          className={`rambo-mgmt-card__icon ${available ? 'rambo-mgmt-card__icon--ok' : 'rambo-mgmt-card__icon--bad'}`}
          aria-hidden
        >
          {available ? '✓' : '✕'}
        </span>
        <div>
          <strong>{available ? 'verfügbar' : 'nicht verfügbar'}</strong>
          {ts ? <div className="rambo-mgmt-card__muted">Stand: {ts}</div> : null}
          {backup?.backup_kind ? <div className="rambo-mgmt-card__muted">{backup.backup_kind}</div> : null}
        </div>
      </div>
    </section>
  );
}

export function RamboManagementDashboard({
  apiBase = defaultApiBase(),
  adminToken = defaultAdminToken(),
  refreshIntervalMs = 30000,
}) {
  const [loading, setLoading] = useState(true);
  const [dataLoadedOnce, setDataLoadedOnce] = useState(false);
  const [error, setError] = useState(null);
  const [health, setHealth] = useState(null);
  const [summary, setSummary] = useState(null);
  const [status, setStatus] = useState(null);
  const [historyEntries, setHistoryEntries] = useState([]);
  const [presets, setPresets] = useState([]);
  const [backup, setBackup] = useState(null);

  const adminHeaders = adminToken ? { 'X-Rambo-Admin': adminToken } : {};

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    const base = String(apiBase || '').replace(/\/$/, '');

    let online = false;
    let healthBody = null;
    try {
      healthBody = await fetchJson(`${base}/api/health`);
      online = isHealthOnline(healthBody);
    } catch {
      online = false;
    }

    setHealth(healthBody);

    if (!online) {
      setSummary(null);
      setStatus(null);
      setHistoryEntries([]);
      setPresets([]);
      setBackup(null);
      setError('API nicht erreichbar');
      setLoading(false);
      setDataLoadedOnce(true);
      return;
    }

    const endpoints = [
      ['summary', `${base}/api/rules/summary`, adminHeaders],
      ['status', `${base}/api/rules/status`, adminHeaders],
      ['history', `${base}/api/rules/history`, adminHeaders],
      ['presets', `${base}/api/rules/presets`, adminHeaders],
      ['backup', `${base}/api/rules/backup`, adminHeaders],
    ];

    const results = await Promise.allSettled(
      endpoints.map(([, url, h]) => fetchJson(url, h))
    );

    const adminFailed = results.some(
      (r) => r.status === 'rejected' || (r.status === 'fulfilled' && r.value && r.value.success === false)
    );

    if (adminFailed) {
      setError('API nicht erreichbar oder Admin-Header ungültig (X-Rambo-Admin).');
    }

    results.forEach((r, i) => {
      const key = endpoints[i][0];
      if (r.status !== 'fulfilled') return;
      const data = r.value;
      if (key === 'summary') setSummary(data);
      if (key === 'status') setStatus(data);
      if (key === 'history') setHistoryEntries(Array.isArray(data.entries) ? data.entries : []);
      if (key === 'presets') setPresets(Array.isArray(data.presets) ? data.presets : []);
      if (key === 'backup') setBackup(data);
    });

    setLoading(false);
    setDataLoadedOnce(true);
  }, [apiBase, adminToken]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!cancelled) await loadData();
    })();
    return () => {
      cancelled = true;
    };
  }, [loadData]);

  useEffect(() => {
    if (!refreshIntervalMs || refreshIntervalMs < 5000) return undefined;
    const id = setInterval(() => {
      loadData();
    }, refreshIntervalMs);
    return () => clearInterval(id);
  }, [loadData, refreshIntervalMs]);

  const online = isHealthOnline(health);

  return (
    <div className="rambo-mgmt">
      <header className="rambo-mgmt__head">
        <h2 className="rambo-mgmt__title">Rambo Management</h2>
        <div className="rambo-mgmt__actions">
          <button type="button" className="rambo-mgmt__refresh" onClick={() => loadData()} disabled={loading}>
            Refresh
          </button>
        </div>
      </header>

      {error ? <div className="rambo-mgmt__error">{error}</div> : null}

      {loading && !dataLoadedOnce ? (
        <div className="rambo-mgmt__loading" aria-busy="true">
          <div className="rambo-mgmt__spinner" />
          <span>Laden…</span>
        </div>
      ) : (
        <>
          <div className="rambo-mgmt__grid">
            <HealthCard online={online} detail={health?.server_id} />
            <SummaryCard summary={summary} />
            <StatusCard summary={summary} status={status} historyEntries={historyEntries} />
            <PresetsCard presets={presets} />
            <BackupCard backup={backup} />
          </div>
        </>
      )}
    </div>
  );
}

export default RamboManagementDashboard;
