import React, { useCallback, useEffect, useState } from "react";

function defaultAdminToken() {
  if (typeof import.meta !== "undefined" && import.meta.env?.VITE_RAMBO_ADMIN_TOKEN) {
    return String(import.meta.env.VITE_RAMBO_ADMIN_TOKEN);
  }
  return "";
}

function buildHeaders(adminToken, isJson = false) {
  const h = {};
  if (isJson) {
    h["Content-Type"] = "application/json";
  }
  const t = String(adminToken || "").trim();
  if (t) {
    h["X-Rambo-Admin"] = t;
  }
  return h;
}

async function readErrorMessage(res) {
  try {
    const data = await res.json();
    if (data && typeof data.error === "string" && data.error.trim()) {
      return data.error.trim();
    }
  } catch {
    /* ignore */
  }
  return `HTTP ${res.status}`;
}

/**
 * Modal: Presets laden und per POST anwenden.
 * Backend erwartet Body { preset, merge? } und Admin-Header X-Rambo-Admin.
 */
export default function PresetModal({
  isOpen,
  onClose,
  onApplySuccess,
  apiBase = "",
  adminToken = defaultAdminToken(),
}) {
  const [presets, setPresets] = useState([]);
  const [selectedPresetId, setSelectedPresetId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [applying, setApplying] = useState(false);

  const base = String(apiBase || "").replace(/\/$/, "");

  const loadPresets = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSuccess(false);
    setPresets([]);
    setSelectedPresetId(null);

    try {
      const res = await fetch(`${base}/api/rules/presets`, {
        headers: buildHeaders(adminToken, false),
      });
      if (!res.ok) {
        throw new Error(await readErrorMessage(res));
      }
      const data = await res.json();
      const list = Array.isArray(data.presets) ? data.presets : [];
      setPresets(list);
      if (list.length > 0) {
        setSelectedPresetId(list[0].id);
      }
    } catch (err) {
      setError(
        err?.message || "Presets konnten nicht geladen werden"
      );
    } finally {
      setLoading(false);
    }
  }, [base, adminToken]);

  useEffect(() => {
    if (!isOpen) return;
    loadPresets();
  }, [isOpen, loadPresets]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose?.();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [isOpen, onClose]);

  const handleApply = async () => {
    if (!selectedPresetId) {
      setError("Bitte wählen Sie einen Preset");
      return;
    }

    setApplying(true);
    setError(null);

    try {
      const res = await fetch(`${base}/api/rules/presets/apply`, {
        method: "POST",
        headers: buildHeaders(adminToken, true),
        body: JSON.stringify({ preset: selectedPresetId, merge: true }),
      });

      if (!res.ok) {
        const msg = await readErrorMessage(res);
        throw new Error(msg);
      }

      setSuccess(true);
      setTimeout(() => {
        onApplySuccess?.();
        onClose?.();
      }, 1000);
    } catch (err) {
      setError(err?.message || "Fehler beim Anwenden des Presets");
    } finally {
      setApplying(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      role="presentation"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        backgroundColor: "rgba(0,0,0,0.5)",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        zIndex: 1000,
      }}
      onClick={onClose}
      onKeyDown={(e) => e.key === "Escape" && onClose?.()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="preset-modal-title"
        style={{
          backgroundColor: "#ffffff",
          borderRadius: "8px",
          padding: "24px",
          width: "90%",
          maxWidth: "400px",
          maxHeight: "70vh",
          overflowY: "auto",
          boxShadow: "0 4px 16px rgba(0,0,0,0.2)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "16px",
          }}
        >
          <h2
            id="preset-modal-title"
            style={{ margin: 0, fontSize: "18px", fontWeight: "600", color: "#333" }}
          >
            Preset auswählen
          </h2>
          <button
            type="button"
            aria-label="Schließen"
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              fontSize: "24px",
              cursor: "pointer",
              color: "#666",
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>

        {success ? (
          <div
            style={{
              padding: "12px",
              backgroundColor: "#e8f5e9",
              color: "#2e7d32",
              borderRadius: "4px",
              marginBottom: "16px",
              fontSize: "14px",
            }}
          >
            ✓ Preset erfolgreich angewendet
          </div>
        ) : null}

        {loading ? (
          <div style={{ textAlign: "center", padding: "32px 0" }}>
            <div
              style={{
                display: "inline-block",
                width: "32px",
                height: "32px",
                border: "3px solid #f3f3f3",
                borderTop: "3px solid #007bff",
                borderRadius: "50%",
                animation: "preset-modal-spin 1s linear infinite",
              }}
            />
            <style>{`@keyframes preset-modal-spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
            <p style={{ marginTop: "12px", color: "#666", fontSize: "14px" }}>
              Presets werden geladen...
            </p>
          </div>
        ) : null}

        {error && !loading ? (
          <div
            style={{
              padding: "12px",
              backgroundColor: "#ffebee",
              color: "#c62828",
              borderRadius: "4px",
              marginBottom: "16px",
              fontSize: "14px",
            }}
          >
            ⚠ {error}
          </div>
        ) : null}

        {!loading && !error && presets.length === 0 ? (
          <div style={{ textAlign: "center", padding: "24px 0", color: "#999" }}>
            Keine Presets verfügbar
          </div>
        ) : null}

        {!loading && presets.length > 0 ? (
          <div style={{ marginBottom: "16px" }}>
            {presets.map((preset) => (
              <label
                key={preset.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  padding: "12px",
                  marginBottom: "8px",
                  border:
                    selectedPresetId === preset.id ? "2px solid #007bff" : "1px solid #ddd",
                  borderRadius: "4px",
                  cursor: "pointer",
                  backgroundColor: selectedPresetId === preset.id ? "#f0f7ff" : "#fff",
                  transition: "all 0.2s",
                }}
              >
                <input
                  type="radio"
                  name="preset"
                  value={preset.id}
                  checked={selectedPresetId === preset.id}
                  onChange={() => setSelectedPresetId(preset.id)}
                  style={{ marginRight: "12px", cursor: "pointer" }}
                />
                <div>
                  <div style={{ fontWeight: "600", color: "#333", fontSize: "14px" }}>
                    {preset.name}
                  </div>
                  {preset.description ? (
                    <div style={{ fontSize: "12px", color: "#999", marginTop: "4px" }}>
                      {preset.description}
                    </div>
                  ) : null}
                </div>
              </label>
            ))}
          </div>
        ) : null}

        {!loading ? (
          <div
            style={{
              display: "flex",
              gap: "12px",
              marginTop: "24px",
              justifyContent: "flex-end",
            }}
          >
            <button
              type="button"
              onClick={onClose}
              disabled={applying}
              style={{
                padding: "8px 16px",
                backgroundColor: "#e0e0e0",
                color: "#333",
                border: "none",
                borderRadius: "4px",
                cursor: applying ? "not-allowed" : "pointer",
                fontSize: "14px",
                fontWeight: "600",
                opacity: applying ? 0.6 : 1,
              }}
            >
              Abbrechen
            </button>
            <button
              type="button"
              onClick={handleApply}
              disabled={!selectedPresetId || applying}
              style={{
                padding: "8px 16px",
                backgroundColor: "#007bff",
                color: "#fff",
                border: "none",
                borderRadius: "4px",
                cursor: !selectedPresetId || applying ? "not-allowed" : "pointer",
                fontSize: "14px",
                fontWeight: "600",
                opacity: !selectedPresetId || applying ? 0.6 : 1,
              }}
            >
              {applying ? "Wird angewendet..." : "Anwenden"}
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
