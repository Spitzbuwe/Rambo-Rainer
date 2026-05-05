import React, { useCallback, useState } from "react";
import "./RainerAgent.css";

function apiDirectRunUrl(apiBase) {
  const base = String(apiBase || "").replace(/\/$/, "");
  if (!base) return "/api/direct-run";
  return `${base}/api/direct-run`;
}

/**
 * Rainer-Build Agent über POST /api/direct-run (Projekt-Arbeitsbereich).
 */
export default function RainerAgent({ apiBase = "", adminToken = "", onClose }) {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [entries, setEntries] = useState([]);

  const append = useCallback((role, text) => {
    setEntries((prev) => [
      ...prev,
      {
        id: `${Date.now()}-${prev.length}`,
        role,
        text: String(text ?? ""),
        time: new Date().toLocaleTimeString(),
      },
    ]);
  }, []);

  const send = useCallback(async () => {
    const t = prompt.trim();
    if (!t || busy) return;
    setBusy(true);
    append("user", t);
    setPrompt("");
    try {
      const headers = { "Content-Type": "application/json" };
      if (adminToken) headers["X-Rambo-Admin"] = adminToken;
      const res = await fetch(apiDirectRunUrl(apiBase), {
        method: "POST",
        headers,
        body: JSON.stringify({
          task: t,
          prompt: t,
          scope: "project",
          mode: "apply",
        }),
      });
      const data = await res.json().catch(() => ({}));
      const msg =
        data.formatted_response ||
        data.chat_response ||
        data.natural_message ||
        data.message ||
        data.analysis ||
        data.error ||
        (res.ok ? "OK (kein Textfeld in Antwort)" : `HTTP ${res.status}`);
      append("assistant", msg);
    } catch (err) {
      append("assistant", `Fehler: ${err?.message ?? err}`);
    } finally {
      setBusy(false);
    }
  }, [prompt, busy, append, apiBase, adminToken]);

  return (
    <div className="rainer-agent-overlay" role="dialog" aria-modal="true" aria-label="Rainer Agent">
      <div className="rainer-agent-modal">
        <header className="rainer-agent-head">
          <h2>Rainer Agent</h2>
          <button type="button" className="rainer-agent-close" onClick={onClose}>
            Schließen
          </button>
        </header>
        <div className="rainer-agent-thread">
          {entries.length === 0 && (
            <p className="rainer-agent-hint">Prompt eingeben — Antworten kommen von Rainer-Build /api/direct-run (Groq/Agent-Loop).</p>
          )}
          {entries.map((m) => (
            <div key={m.id} className={`rainer-agent-msg rainer-agent-msg--${m.role}`}>
              <span className="rainer-agent-msg-meta">
                {m.time} · {m.role === "user" ? "Du" : "Rainer"}
              </span>
              <pre className="rainer-agent-msg-body">{m.text}</pre>
            </div>
          ))}
        </div>
        <div className="rainer-agent-compose">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="z. B. Analysiere backend/main.py …"
            rows={5}
            disabled={busy}
          />
          <button type="button" className="rainer-agent-send" onClick={send} disabled={busy || !prompt.trim()}>
            {busy ? "Läuft …" : "Senden"}
          </button>
        </div>
      </div>
    </div>
  );
}
