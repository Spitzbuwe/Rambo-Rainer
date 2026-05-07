import React, { useCallback, useState } from "react";
import "./RainerAgent.css";

function apiDirectRunUrl(apiBase) {
  const base = String(apiBase || "").replace(/\/$/, "");
  if (!base) return "/api/direct-run";
  return `${base}/api/direct-run`;
}
function apiUrl(apiBase, path) {
  const base = String(apiBase || "").replace(/\/$/, "");
  return base ? `${base}${path}` : path;
}

/**
 * Rainer-Build Agent über POST /api/direct-run (Projekt-Arbeitsbereich).
 */
export default function RainerAgent({ apiBase = "", adminToken = "", onClose }) {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [entries, setEntries] = useState([]);
  const [workspacePath, setWorkspacePath] = useState("");
  const [workspaceBusy, setWorkspaceBusy] = useState(false);
  const [attachBusy, setAttachBusy] = useState(false);
  const [attachments, setAttachments] = useState([]);

  const append = useCallback((role, text, meta = null) => {
    setEntries((prev) => [
      ...prev,
      {
        id: `${Date.now()}-${prev.length}`,
        role,
        text: String(text ?? ""),
        meta: meta && typeof meta === "object" ? meta : null,
        time: new Date().toLocaleTimeString(),
      },
    ]);
  }, []);

  const summarizeCheckResult = useCallback((text) => {
    const t = String(text || "");
    const okHits = (t.match(/\b(ok|passed|erfolgreich)\b/gi) || []).length;
    const failHits = (t.match(/\b(fail|failed|fehlgeschlagen|error)\b/gi) || []).length;
    if (failHits > 0) return { label: "FAIL", okHits, failHits };
    if (okHits > 0) return { label: "PASS", okHits, failHits };
    return { label: "UNKLAR", okHits, failHits };
  }, []);

  const confidenceTone = useCallback((label, score) => {
    const l = String(label || "").toLowerCase();
    const s = Number(score);
    if (l === "high" || Number.isFinite(s) && s >= 80) return "ok";
    if (l === "low" || Number.isFinite(s) && s < 50) return "bad";
    return "warn";
  }, []);

  const checkTone = useCallback((status) => {
    const s = String(status || "").toUpperCase();
    if (s === "PASS") return "ok";
    if (s === "FAIL") return "bad";
    return "warn";
  }, []);

  const runChecks = useCallback(
    async (checks, sourceEntryId = "") => {
      const list = Array.isArray(checks) ? checks.map((x) => String(x || "").trim()).filter(Boolean) : [];
      if (list.length === 0 || busy) return;
      setBusy(true);
      append("user", `Starte empfohlene Checks:\n- ${list.join("\n- ")}`);
      try {
        const headers = { "Content-Type": "application/json" };
        if (adminToken) headers["X-Rambo-Admin"] = adminToken;
        const checkPrompt = [
          "Führe ausschließlich diese Verifikations-Checks im Projekt aus und gib nur ein kompaktes Ergebnis zurück.",
          "",
          "Checks:",
          ...list.map((c) => `- ${c}`),
          "",
          "Antwortformat:",
          "- pro Check: OK/FAIL",
          "- kurze Fehlerursache falls FAIL",
          "- Abschluss: Gesamtstatus",
        ].join("\n");
        const res = await fetch(apiDirectRunUrl(apiBase), {
          method: "POST",
          headers,
          body: JSON.stringify({
            task: checkPrompt,
            prompt: checkPrompt,
            scope: "project",
            mode: "safe",
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
          (res.ok ? "Checks ausgeführt (kein Textfeld in Antwort)." : `HTTP ${res.status}`);
        const summary = summarizeCheckResult(msg);
        const at = new Date().toLocaleTimeString();
        append("assistant", msg, {
          checkRun: {
            status: summary.label,
            okHits: summary.okHits,
            failHits: summary.failHits,
            at,
          },
        });
        if (sourceEntryId) {
          setEntries((prev) =>
            prev.map((e) =>
              e.id !== sourceEntryId
                ? e
                : {
                    ...e,
                    meta: {
                      ...(e.meta && typeof e.meta === "object" ? e.meta : {}),
                      lastCheckStatus: summary.label,
                      lastCheckAt: at,
                    },
                  },
            ),
          );
        }
      } catch (err) {
        append("assistant", `Check-Run fehlgeschlagen: ${err?.message ?? err}`);
      } finally {
        setBusy(false);
      }
    },
    [busy, append, adminToken, apiBase, summarizeCheckResult]
  );

  const send = useCallback(async () => {
    const t = prompt.trim();
    if ((!t && attachments.length === 0) || busy) return;
    const finalPrompt = t;
    setBusy(true);
    append("user", t || `[${attachments.length} Anhang/Anhänge gesendet]`);
    setPrompt("");
    try {
      const headers = { "Content-Type": "application/json" };
      if (adminToken) headers["X-Rambo-Admin"] = adminToken;
      const uploadedFiles = [];
      for (const a of attachments) {
        if (a.type !== "image" || !a.file) continue;
        const fd = new FormData();
        fd.append("file", a.file, a.name);
        const upRes = await fetch(apiUrl(apiBase, "/api/upload"), {
          method: "POST",
          headers: adminToken ? { "X-Rambo-Admin": adminToken } : {},
          body: fd,
        });
        const upData = await upRes.json().catch(() => ({}));
        if (upRes.ok && upData?.ok) {
          uploadedFiles.push({
            filename: upData.filename || a.name,
            filepath: upData.filepath || upData.saved_path || "",
            saved_path: upData.saved_path || upData.filepath || "",
            mime_type: upData.mime_type || a.mime || "image/*",
            file_type: upData.file_type || "",
            size: upData.size || 0,
          });
        }
      }
      const res = await fetch(apiDirectRunUrl(apiBase), {
        method: "POST",
        headers,
        body: JSON.stringify({
          task: finalPrompt,
          prompt: finalPrompt,
          scope: "project",
          mode: "apply",
          uploaded_files: uploadedFiles,
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
      const conf = data?.confidence_gate && typeof data.confidence_gate === "object" ? data.confidence_gate : null;
      const checks = Array.isArray(data?.recommended_checks)
        ? data.recommended_checks.map((x) => String(x || "").trim()).filter(Boolean)
        : [];
      const meta = {
        confidenceLabel: String(conf?.confidence_label || "").trim(),
        confidenceScore: Number.isFinite(Number(conf?.confidence_score)) ? Number(conf.confidence_score) : null,
        verificationRequired: Boolean(data?.verification_required),
        checks,
      };
      append("assistant", msg, meta);
    } catch (err) {
      append("assistant", `Fehler: ${err?.message ?? err}`);
    } finally {
      setBusy(false);
      setAttachments([]);
    }
  }, [prompt, attachments, busy, append, apiBase, adminToken]);

  const enableWorkspace = useCallback(
    async (decision) => {
      const p = workspacePath.trim();
      if (!p || workspaceBusy) return;
      setWorkspaceBusy(true);
      try {
        const headers = { "Content-Type": "application/json" };
        if (adminToken) headers["X-Rambo-Admin"] = adminToken;
        const addRes = await fetch(apiUrl(apiBase, "/api/workspaces/add"), {
          method: "POST",
          headers,
          body: JSON.stringify({ path: p }),
        });
        const addData = await addRes.json().catch(() => ({}));
        if (!addRes.ok || !addData?.ok) {
          append("assistant", addData?.error || addData?.message || `Projektordner konnte nicht hinzugefügt werden (HTTP ${addRes.status}).`);
          return;
        }
        const consRes = await fetch(apiUrl(apiBase, "/api/workspaces/select-with-consent"), {
          method: "POST",
          headers,
          body: JSON.stringify({ path: p, decision }),
        });
        const consData = await consRes.json().catch(() => ({}));
        if (!consRes.ok || !consData?.ok) {
          append("assistant", consData?.error || consData?.message || `Freigabe fehlgeschlagen (HTTP ${consRes.status}).`);
          return;
        }
        append("assistant", decision === "yes" ? `Projektordner freigegeben: ${p}` : `Projektordner ausgewählt ohne Vollzugriff: ${p}`);
      } catch (err) {
        append("assistant", `Workspace-Fehler: ${err?.message ?? err}`);
      } finally {
        setWorkspaceBusy(false);
      }
    },
    [workspacePath, workspaceBusy, adminToken, apiBase, append]
  );

  const appendFileToPrompt = useCallback(async (file) => {
    if (!file) return;
    const maxBytes = 15 * 1024 * 1024;
    if (file.size > maxBytes) {
      append("assistant", `Datei zu groß: ${file.name} (max 15 MB).`);
      return;
    }
    setAttachBusy(true);
    try {
      const isImage = String(file.type || "").startsWith("image/");
      if (isImage) {
        const dataUrl = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result || ""));
          reader.onerror = () => reject(new Error("read_failed"));
          reader.readAsDataURL(file);
        });
        setAttachments((prev) => [...prev, { type: "image", name: file.name, mime: file.type || "image/*", dataUrl, file }]);
      } else {
        const text = await file.text();
        const block = `\n\n[DATEI: ${file.name}]\n${text}\n[/DATEI]\n`;
        setPrompt((prev) => `${prev}${block}`.trimStart());
      }
    } catch (err) {
      append("assistant", `Datei konnte nicht gelesen werden: ${file.name}`);
    } finally {
      setAttachBusy(false);
    }
  }, [append]);

  return (
    <div className="rainer-agent-overlay" role="dialog" aria-modal="true" aria-label="Rainer Agent">
      <div className="rainer-agent-modal">
        <header className="rainer-agent-head">
          <h2>Rainer Agent</h2>
          <button type="button" className="rainer-agent-close" onClick={onClose}>
            Schließen
          </button>
        </header>
        <div className="rainer-agent-workspace">
          <input
            type="text"
            value={workspacePath}
            onChange={(e) => setWorkspacePath(e.target.value)}
            placeholder="Projektordner-Pfad, z. B. D:\\MeinProjekt"
            disabled={workspaceBusy}
          />
          <div className="rainer-agent-workspace-actions">
            <button type="button" onClick={() => enableWorkspace("yes")} disabled={workspaceBusy || !workspacePath.trim()}>
              Ordner + Ja
            </button>
            <button type="button" onClick={() => enableWorkspace("no")} disabled={workspaceBusy || !workspacePath.trim()}>
              Ordner + Nein
            </button>
          </div>
        </div>
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
              {m.role === "assistant" && m.meta ? (
                <div className="rainer-agent-meta">
                  {(m.meta.confidenceLabel || m.meta.confidenceScore != null) ? (
                    <div className={`rainer-agent-meta-row rainer-agent-meta-row--${confidenceTone(m.meta.confidenceLabel, m.meta.confidenceScore)}`}>
                      Confidence: {m.meta.confidenceLabel || "n/a"}
                      {m.meta.confidenceScore != null ? ` (${m.meta.confidenceScore})` : ""}
                    </div>
                  ) : null}
                  <div className="rainer-agent-meta-row">
                    Verification: {m.meta.verificationRequired ? "erforderlich" : "optional"}
                  </div>
                  {Array.isArray(m.meta.checks) && m.meta.checks.length > 0 ? (
                    <div className="rainer-agent-meta-row">
                      Checks: {m.meta.checks.join(" | ")}
                    </div>
                  ) : null}
                  {m.meta.lastCheckStatus ? (
                    <div className={`rainer-agent-meta-row rainer-agent-meta-row--${checkTone(m.meta.lastCheckStatus)}`}>
                      Letzter Check: {m.meta.lastCheckStatus}
                      {m.meta.lastCheckAt ? ` (${m.meta.lastCheckAt})` : ""}
                    </div>
                  ) : null}
                  {m.meta.checkRun && typeof m.meta.checkRun === "object" ? (
                    <div className={`rainer-agent-meta-row rainer-agent-meta-row--${checkTone(m.meta.checkRun.status)}`}>
                      Check-Run: {String(m.meta.checkRun.status || "UNKLAR")}
                      {Number.isFinite(Number(m.meta.checkRun.okHits))
                        ? ` · ok=${Number(m.meta.checkRun.okHits)}`
                        : ""}
                      {Number.isFinite(Number(m.meta.checkRun.failHits))
                        ? ` · fail=${Number(m.meta.checkRun.failHits)}`
                        : ""}
                    </div>
                  ) : null}
                  {Array.isArray(m.meta.checks) && m.meta.checks.length > 0 ? (
                    <button
                      type="button"
                      className="rainer-agent-checks-btn"
                      onClick={() => runChecks(m.meta.checks, m.id)}
                      disabled={busy}
                    >
                      Checks ausführen
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
          ))}
        </div>
        <div className="rainer-agent-compose">
          <div className="rainer-agent-attach">
            <label className="rainer-agent-attach-btn">
              Datei einfügen
              <input
                type="file"
                onChange={(e) => {
                  const f = e.target.files && e.target.files[0];
                  if (f) appendFileToPrompt(f);
                  e.target.value = "";
                }}
                disabled={busy || attachBusy}
              />
            </label>
            <span className="rainer-agent-attach-hint">Oder Text/Datei hier per Paste einfügen</span>
          </div>
          {attachments.length > 0 ? (
            <div className="rainer-agent-attachments">
              {attachments.map((a, idx) => (
                <div key={`${a.name}-${idx}`} className="rainer-agent-attachment">
                  <img src={a.dataUrl} alt={a.name} />
                  <button
                    type="button"
                    onClick={() => setAttachments((prev) => prev.filter((_, i) => i !== idx))}
                    disabled={busy}
                  >
                    Entfernen
                  </button>
                </div>
              ))}
            </div>
          ) : null}
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onPaste={(e) => {
              const items = Array.from(e.clipboardData?.items || []);
              const fileItem = items.find((it) => it.kind === "file");
              if (fileItem) {
                const f = fileItem.getAsFile();
                if (f) {
                  e.preventDefault();
                  appendFileToPrompt(f);
                }
              }
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="z. B. Analysiere backend/main.py …"
            rows={5}
            disabled={busy}
          />
          <button type="button" className="rainer-agent-send" onClick={send} disabled={busy || (!prompt.trim() && attachments.length === 0)}>
            {busy ? "Läuft …" : "Senden"}
          </button>
        </div>
      </div>
    </div>
  );
}
