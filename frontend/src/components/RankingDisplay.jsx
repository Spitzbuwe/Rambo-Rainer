import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

function buildHeaders(adminToken, isJson) {
  const h = {};
  if (isJson) h["Content-Type"] = "application/json";
  const t = String(adminToken || "").trim();
  if (t) h["X-Rambo-Admin"] = t;
  return h;
}

/**
 * Zeigt Regeln nach Relevanz (POST /api/rules/score-batch).
 */
export default function RankingDisplay({ rules = [], context = {}, apiBase = "", adminToken = "" }) {
  const [ranked, setRanked] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedRule, setSelectedRule] = useState(null);
  const rulesRef = useRef(rules);
  rulesRef.current = rules;

  const base = String(apiBase || "").replace(/\/$/, "");
  const contextKey = useMemo(() => JSON.stringify(context ?? {}), [context]);
  const rulesKey = useMemo(
    () =>
      JSON.stringify(
        (Array.isArray(rules) ? rules : []).map((r) => String(r?.fingerprint || r?.rule_id || ""))
      ),
    [rules]
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const ctxObj = contextKey ? JSON.parse(contextKey) : {};
      const res = await fetch(`${base}/api/rules/score-batch`, {
        method: "POST",
        headers: buildHeaders(adminToken, true),
        body: JSON.stringify({ context: ctxObj }),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t.slice(0, 200) || `HTTP ${res.status}`);
      }
      const data = await res.json();
      let list = Array.isArray(data.ranked_rules) ? data.ranked_rules : [];
      const rulesArr = Array.isArray(rulesRef.current) ? rulesRef.current : [];
      if (rulesArr.length > 0) {
        const want = new Set(
          rulesArr.map((r) => String(r.fingerprint || r.rule_id || "").trim()).filter(Boolean)
        );
        if (want.size > 0) {
          list = list.filter((row) => want.has(String(row.rule_id || "")));
        }
      }
      list.sort((x, y) => Number(y.score) - Number(x.score));
      setRanked(list);
    } catch (e) {
      setError(e?.message || "Laden fehlgeschlagen");
      setRanked([]);
    } finally {
      setLoading(false);
    }
  }, [base, adminToken, contextKey, rulesKey]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div data-testid="ranking-display">
      <h3 style={{ margin: "0 0 8px", fontSize: "16px" }}>Regel-Ranking</h3>
      {loading ? <p data-testid="ranking-loading">Lade Scores…</p> : null}
      {error ? (
        <p data-testid="ranking-error" style={{ color: "#c62828" }}>
          {error}
        </p>
      ) : null}
      {!loading && !error ? (
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {ranked.map((row) => (
            <li
              key={row.rule_id}
              data-testid={`rank-row-${row.rule_id}`}
              style={{
                marginBottom: "12px",
                padding: "8px",
                border: "1px solid #ddd",
                borderRadius: "6px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong style={{ fontSize: "13px" }}>{row.rule_id}</strong>
                <span data-testid={`score-val-${row.rule_id}`}>{row.score?.toFixed?.(3) ?? row.score}</span>
              </div>
              <div
                data-testid={`score-bar-${row.rule_id}`}
                style={{
                  height: "8px",
                  background: "#e0e0e0",
                  borderRadius: "4px",
                  marginTop: "6px",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${Math.min(100, Math.max(0, Number(row.score) * 100))}%`,
                    height: "100%",
                    background: "#1976d2",
                  }}
                />
              </div>
              <div style={{ fontSize: "11px", color: "#666", marginTop: "4px" }}>{row.reason}</div>
              <button
                type="button"
                data-testid={`details-btn-${row.rule_id}`}
                onClick={() => setSelectedRule(selectedRule?.rule_id === row.rule_id ? null : row)}
                style={{ marginTop: "6px", fontSize: "12px" }}
              >
                View Details
              </button>
              {selectedRule?.rule_id === row.rule_id && row.heuristics ? (
                <pre
                  data-testid={`details-${row.rule_id}`}
                  style={{
                    fontSize: "11px",
                    background: "#f5f5f5",
                    padding: "8px",
                    marginTop: "6px",
                    borderRadius: "4px",
                    overflow: "auto",
                  }}
                >
                  {JSON.stringify(row.heuristics, null, 2)}
                </pre>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
