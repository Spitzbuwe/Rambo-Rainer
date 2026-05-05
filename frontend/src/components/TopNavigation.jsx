import React from "react";
import "./TopNavigation.css";

/**
 * Sticky Top-Navigation: optional Builder, Datei-Generator, Design Studio.
 * @param {"builder"|"generator"|"studio"|null} activeSection
 * @param {boolean} [showBuilderMode] — sichtbarer Builder-Einstieg (Standard: aus)
 */
export default function TopNavigation({
  onBuilderMode,
  onGeneratorUI,
  onDesignStudio,
  onRainerAgent = () => {},
  activeSection = null,
  showBuilderMode = false,
}) {
  return (
    <nav className="top-navigation" aria-label="Hauptaktionen">
      <div className="nav-buttons">
        {showBuilderMode ? (
        <button
          type="button"
          className={`nav-btn nav-btn-builder${activeSection === "builder" ? " active" : ""}`}
          onClick={onBuilderMode}
          title="Apps bauen lassen"
        >
          🏗️ Builder Mode
        </button>
        ) : null}

        <button
          type="button"
          className={`nav-btn nav-btn-rainer${activeSection === "rainer" ? " active" : ""}`}
          onClick={onRainerAgent}
          title="Rainer-Build Agent (direct-run)"
        >
          🤖 Rainer Agent
        </button>

        <button
          type="button"
          className={`nav-btn nav-btn-generator${activeSection === "generator" ? " active" : ""}`}
          onClick={onGeneratorUI}
          title="Dokumente und Designs generieren"
        >
          📁 Datei-Generator
        </button>

        <button
          type="button"
          className={`nav-btn nav-btn-studio${activeSection === "studio" ? " active" : ""}`}
          onClick={onDesignStudio}
          title="Design Studio mit Chat & Canvas"
        >
          🎨 Design Studio
        </button>
      </div>
    </nav>
  );
}
