import React, { useCallback, useEffect, useState } from "react";

function headers(adminToken, json = false) {
  const h = {};
  if (json) h["Content-Type"] = "application/json";
  const t = String(adminToken || "").trim();
  if (t) h["X-Rambo-Admin"] = t;
  return h;
}

export default function AgentSync({
  apiBase = "",
  adminToken = "",
  onRegisterAgent,
  onSyncRules,
  onPullRules,
}) {
  const [connectedAgents, setConnectedAgents] = useState([]);
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [form, setForm] = useState({ agent_id: "", base_url: "http://127.0.0.1", port: "5036" });
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);

  const base = String(apiBase || "").replace(/\/$/, "");

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const res = await fetch(`${base}/api/sync/agents`, { headers: headers(adminToken) });
      if (!res.ok) throw new Error(`agents ${res.status}`);
      const data = await res.json();
      setConnectedAgents(Array.isArray(data.agents) ? data.agents : []);
    } catch (e) {
      setError(e?.message || "Fehler");
      setConnectedAgents([]);
    }
  }, [base, adminToken]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const register = async () => {
    setToast(null);
    const payload = {
      agent_id: form.agent_id.trim(),
      base_url: form.base_url.trim(),
      port: parseInt(form.port, 10),
    };
    onRegisterAgent?.(payload.agent_id, payload.base_url, payload.port);
    try {
      const res = await fetch(`${base}/api/sync/register-agent`, {
        method: "POST",
        headers: headers(adminToken, true),
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("register failed");
      setShowRegisterModal(false);
      await refresh();
    } catch (e) {
      setToast(String(e?.message || e));
    }
  };

  const syncNow = async (agentId) => {
    onSyncRules?.(agentId);
    setToast(null);
    try {
      const res = await fetch(`${base}/api/sync/push-rules`, {
        method: "POST",
        headers: headers(adminToken, true),
        body: JSON.stringify({ target_agent_id: agentId, rules: [] }),
      });
      if (!res.ok) throw new Error("sync failed");
    } catch (e) {
      setToast(String(e?.message || e));
    }
  };

  const pullNow = async (agentId) => {
    onPullRules?.(agentId);
    try {
      const res = await fetch(`${base}/api/sync/pull-rules/${encodeURIComponent(agentId)}`, {
        headers: headers(adminToken),
      });
      if (!res.ok) throw new Error("pull failed");
    } catch (e) {
      setToast(String(e?.message || e));
    }
  };

  return (
    <div data-testid="agent-sync">
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <h3 style={{ margin: 0, fontSize: "16px" }}>Remote Agents</h3>
        <button type="button" onClick={() => setShowRegisterModal(true)}>
          Register New Agent
        </button>
      </div>
      {error ? (
        <p data-testid="agent-sync-error" style={{ color: "#c62828" }}>
          {error}
        </p>
      ) : null}
      {toast ? (
        <p data-testid="agent-sync-toast" style={{ color: "#c62828" }}>
          {toast}
        </p>
      ) : null}
      <ul data-testid="agent-list" style={{ listStyle: "none", padding: 0 }}>
        {connectedAgents.map((a) => (
          <li key={a.id} data-testid={`agent-row-${a.id}`} style={{ margin: "8px 0" }}>
            <span data-testid={`agent-status-${a.id}`} style={{ marginRight: "8px" }}>
              {a.connected ? "🟢" : "🔴"}
            </span>
            {a.id} — {a.url}:{a.port}{" "}
            <button type="button" data-testid={`sync-${a.id}`} onClick={() => syncNow(a.id)}>
              Sync Now
            </button>{" "}
            <button type="button" data-testid={`pull-${a.id}`} onClick={() => pullNow(a.id)}>
              Pull
            </button>
          </li>
        ))}
      </ul>
      {showRegisterModal ? (
        <div data-testid="register-modal" role="dialog" aria-modal="true">
          <p>Neuer Agent</p>
          <input
            aria-label="agent id"
            value={form.agent_id}
            onChange={(e) => setForm((f) => ({ ...f, agent_id: e.target.value }))}
          />
          <button type="button" onClick={register}>
            Save
          </button>
          <button type="button" onClick={() => setShowRegisterModal(false)}>
            Close
          </button>
        </div>
      ) : null}
    </div>
  );
}
