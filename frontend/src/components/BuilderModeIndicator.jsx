import React, { useState, useEffect } from "react";
import DesignStudio from "./DesignStudio.jsx";
import GeneratorUI from "./GeneratorUI.jsx";
import "./BuilderModeIndicator.css";

/** Wie in App.jsx – geschützte Builder-APIs erwarten dasselbe Admin-Token. */
const RAMBO_ADMIN_TOKEN =
  import.meta.env.VITE_RAMBO_ADMIN_TOKEN || "Rambo-Admin-Token";

/**
 * Nur Modals / Vollbild (keine Button-Leiste – steuert TopNavigation in App).
 */
export default function BuilderModeIndicator({
  builderModalOpen,
  setBuilderModalOpen,
  generatorModalOpen,
  setGeneratorModalOpen,
  designStudioOpen,
  setDesignStudioOpen,
}) {
  const [appType, setAppType] = useState("web_app");
  const [appName, setAppName] = useState("");
  const [buildProgress, setBuildProgress] = useState(null);
  const [loading, setLoading] = useState(false);

  const readJsonSafe = async (response) => {
    const raw = await response.text();
    if (!raw || !raw.trim()) return {};
    try {
      return JSON.parse(raw);
    } catch {
      return {};
    }
  };

  useEffect(() => {
    const checkBuilderIntent = (e) => {
      if (e.key === "?" && (e.ctrlKey || e.metaKey)) {
        setDesignStudioOpen(false);
        setGeneratorModalOpen(false);
        setBuilderModalOpen(true);
      }
    };
    window.addEventListener("keydown", checkBuilderIntent);
    return () => window.removeEventListener("keydown", checkBuilderIntent);
  }, [setBuilderModalOpen, setDesignStudioOpen, setGeneratorModalOpen]);

  const handleBuild = async () => {
    if (!appName.trim()) {
      alert("App-Name erforderlich");
      return;
    }

    setLoading(true);
    setBuildProgress({ stage: "Starting...", percent: 10 });

    try {
      const headers = {
        "Content-Type": "application/json",
        "X-Rambo-Admin": RAMBO_ADMIN_TOKEN,
      };

      setBuildProgress({ stage: "Coach analysiert...", percent: 20 });
      const coachRes = await fetch("/api/coach/next-step", {
        method: "POST",
        headers,
        body: JSON.stringify({}),
      });
      await readJsonSafe(coachRes);

      setBuildProgress({ stage: "Scaffold generieren...", percent: 40 });
      const scaffoldRes = await fetch("/api/scaffold", {
        method: "POST",
        headers,
        body: JSON.stringify({
          app_type: appType,
          app_name: appName,
          features: [],
        }),
      });
      const scaffoldData = await readJsonSafe(scaffoldRes);

      setBuildProgress({ stage: "Dateien schreiben...", percent: 60 });
      const genRes = await fetch("/api/generate/write-files", {
        method: "POST",
        headers,
        body: JSON.stringify({
          app_name: appName,
          app_type: appType,
          files: scaffoldData.files || [],
          base_path: ".",
        }),
      });
      await readJsonSafe(genRes);

      setBuildProgress({ stage: "Build ausführen...", percent: 80 });
      const buildRes = await fetch("/api/build-full", {
        method: "POST",
        headers,
        body: JSON.stringify({
          app_type: appType,
          app_name: appName,
          features: [],
        }),
      });
      const buildData = await readJsonSafe(buildRes);

      if (buildData.final_status === "success") {
        setBuildProgress({
          stage: "✅ Build erfolgreich!",
          percent: 100,
          success: true,
          files: buildData.summary.files_written,
          tests: buildData.summary.tests_passed,
        });
      } else {
        setBuildProgress({
          stage: "❌ Build fehlgeschlagen",
          percent: 0,
          error: buildData.final_status,
        });
      }
    } catch (err) {
      setBuildProgress({
        stage: `❌ Fehler: ${err.message}`,
        percent: 0,
        error: true,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {builderModalOpen && (
        <div
          className="builder-modal-overlay"
          onClick={() => !loading && setBuilderModalOpen(false)}
          role="presentation"
        >
          <div
            className="builder-modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="builder-modal-title"
          >
            <div className="builder-modal-header">
              <h2 id="builder-modal-title">🏗️ Rambo App Builder</h2>
              <button
                type="button"
                className="close-btn"
                onClick={() => setBuilderModalOpen(false)}
                disabled={loading}
              >
                ✕
              </button>
            </div>

            {!buildProgress ? (
              <div className="builder-form">
                <div className="form-group">
                  <label htmlFor="builder-app-type">App-Type</label>
                  <select
                    id="builder-app-type"
                    value={appType}
                    onChange={(e) => setAppType(e.target.value)}
                    disabled={loading}
                  >
                    <option value="web_app">Web App (React + Flask)</option>
                    <option value="tool">CLI Tool (Python)</option>
                    <option value="dashboard">Dashboard (WebSocket)</option>
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="builder-app-name">App-Name</label>
                  <input
                    id="builder-app-name"
                    type="text"
                    value={appName}
                    onChange={(e) => setAppName(e.target.value)}
                    placeholder="z.B. my_awesome_app"
                    disabled={loading}
                    autoComplete="off"
                  />
                </div>

                <div className="form-description">
                  <p>
                    Rambo wird:
                    <br />
                    1️⃣ Architektur analysieren (Coach)
                    <br />
                    2️⃣ Boilerplate generieren (Scaffold)
                    <br />
                    3️⃣ Dateien schreiben (Generate)
                    <br />
                    4️⃣ Tests ausführen (Dev-Workflow)
                  </p>
                </div>

                <button
                  type="button"
                  className="build-btn"
                  onClick={handleBuild}
                  disabled={!appName.trim() || loading}
                >
                  {loading ? "⏳ Building..." : "🚀 Build starten"}
                </button>
              </div>
            ) : (
              <div className="builder-progress">
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${buildProgress.percent}%` }} />
                </div>
                <p className="progress-text">{buildProgress.stage}</p>
                {buildProgress.percent}%

                {buildProgress.success && (
                  <div className="builder-success">
                    <h3>✅ App erfolgreich erstellt!</h3>
                    <p>📁 {buildProgress.files} Dateien geschrieben</p>
                    <p>✅ Tests: {buildProgress.tests ? "Bestanden" : "Fehlgeschlagen"}</p>
                    <button
                      type="button"
                      onClick={() => {
                        setBuildProgress(null);
                        setBuilderModalOpen(false);
                        setAppName("");
                      }}
                    >
                      Schließen
                    </button>
                  </div>
                )}

                {buildProgress.error && (
                  <div className="builder-error">
                    <h3>❌ Build fehlgeschlagen</h3>
                    <p>{buildProgress.stage}</p>
                    <button type="button" onClick={() => setBuildProgress(null)}>
                      Erneut versuchen
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {generatorModalOpen && (
        <div
          className="builder-modal-overlay builder-modal-overlay--generator"
          onClick={() => setGeneratorModalOpen(false)}
          role="presentation"
        >
          <div
            className="builder-modal builder-modal--generator"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="generator-modal-title"
          >
            <div className="builder-modal-header">
              <h2 id="generator-modal-title">📁 Datei-Generator</h2>
              <button
                type="button"
                className="close-btn"
                onClick={() => setGeneratorModalOpen(false)}
                aria-label="Schließen"
              >
                ✕
              </button>
            </div>
            <p className="builder-modal-lead">Dokumente, SVG-Designs und Downloads</p>
            <GeneratorUI variant="modal" />
          </div>
        </div>
      )}

      {designStudioOpen && (
        <div className="design-studio-fullscreen" role="dialog" aria-modal="true">
          <DesignStudio onClose={() => setDesignStudioOpen(false)} />
        </div>
      )}
    </>
  );
}
