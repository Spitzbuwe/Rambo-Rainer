import React, { useCallback, useEffect, useRef, useState } from "react";
import RankingDisplay from "./RankingDisplay.jsx";

function defaultAdminToken() {
  if (typeof import.meta !== "undefined" && import.meta.env?.VITE_RAMBO_ADMIN_TOKEN) {
    return String(import.meta.env.VITE_RAMBO_ADMIN_TOKEN);
  }
  return "Rambo-Admin-Token";
}

function buildHeaders(token, json) {
  const h = {};
  if (json) h["Content-Type"] = "application/json";
  const t = String(token || "").trim();
  if (t) h["X-Rambo-Admin"] = t;
  return h;
}

/**
 * Lädt Regeln (GET /api/rules/list), Kontext mit Debounce, rendert RankingDisplay.
 */
export default function RankingDisplayWrapper({ apiBase = "", refreshTick = 0 }) {
  const [context, setContext] = useState({});
  const [contextInput, setContextInput] = useState("");
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const debounceRef = useRef(null);
  const adminToken = defaultAdminToken();
  const base = String(apiBase || "").replace(/\/$/, "");

  const loadRules = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${base}/api/rules/list`, {
        headers: buildHeaders(adminToken, false),
      });
      if (!res.ok) throw new Error(`rules ${res.status}`);
      const data = await res.json();
      const raw = Array.isArray(data.rules) ? data.rules : [];
      const mapped = raw.map((r) => ({
        fingerprint: r.fingerprint || "",
        rule_id: r.fingerprint || "",
        text: r.text,
      }));
      setRules(mapped);
    } catch (e) {
      setError(e?.message || "Regeln konnten nicht geladen werden");
      setRules([]);
    } finally {
      setLoading(false);
    }
  }, [base, adminToken]);

  useEffect(() => {
    loadRules();
  }, [loadRules, refreshTick]);

  const onContextChange = useCallback((value) => {
    setContextInput(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const v = String(value || "").trim();
      if (!v) {
        setContext({});
        return;
      }
      try {
        const parsed = JSON.parse(v);
        setContext(typeof parsed === "object" && parsed !== null && !Array.isArray(parsed) ? parsed : { text: v });
      } catch {
        setContext({ text: v });
      }
    }, 400);
  }, []);

  useEffect(
    () => () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    },
    []
  );

  return (
    <div data-testid="ranking-display-wrapper">
      <h3 style={{ fontSize: "15px", margin: "0 0 8px" }}>Scoring-Kontext (debounced)</h3>
      <textarea
        data-testid="context-input"
        rows={3}
        style={{ width: "100%", marginBottom: "8px", fontSize: "13px" }}
        placeholder='JSON {"text":"..."} oder Freitext'
        value={contextInput}
        onChange={(e) => onContextChange(e.target.value)}
      />
      {loading ? <p data-testid="wrapper-rules-loading">Lade Regeln…</p> : null}
      {error ? (
        <p data-testid="wrapper-rules-error" style={{ color: "#c62828" }}>
          {error}
        </p>
      ) : null}
      <RankingDisplay rules={rules} context={context} apiBase={apiBase} adminToken={adminToken} />
    </div>
  );
}
