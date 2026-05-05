import React, { useState, useEffect, useCallback } from "react";
import { generatorService } from "../services/generatorService.js";
import "./GeneratorUI.css";

function designVariablesFor(type, fields) {
  const name = fields.designName?.trim() ?? "";
  const title = fields.designTitle?.trim() ?? "";
  const email = fields.designEmail?.trim() ?? "";
  const content = fields.designContent?.trim() ?? "";
  const logo = fields.designLogo?.trim() ?? "";
  if (type === "business_card") {
    return { Name: name, Title: title, Email: email };
  }
  if (type === "flyer") {
    return { Title: title, Content: content };
  }
  if (type === "logo_background") {
    return { LOGO: logo || name || "LOGO" };
  }
  return { Name: name, Title: title, Email: email };
}

export default function GeneratorUI({ variant = "inline" }) {
  const isModal = variant === "modal";
  const [activeTab, setActiveTab] = useState("documents");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [templates, setTemplates] = useState({ office: {}, design: {} });
  const [templateLoadError, setTemplateLoadError] = useState("");
  const [lastFile, setLastFile] = useState("");
  const [downloadLoading, setDownloadLoading] = useState(false);

  const [wordTitle, setWordTitle] = useState("Mein Dokument");
  const [wordContent, setWordContent] = useState("Dies ist ein automatisch generiertes Dokument.");
  const [wordTemplate, setWordTemplate] = useState("letter");
  const [wordAuthor, setWordAuthor] = useState("");

  const [excelTemplate, setExcelTemplate] = useState("budget");
  const [pptTemplate, setPptTemplate] = useState("presentation");

  const [designType, setDesignType] = useState("business_card");
  const [brandStyle, setBrandStyle] = useState("default");
  const [designName, setDesignName] = useState("Matze Müller");
  const [designTitle, setDesignTitle] = useState("Developer");
  const [designEmail, setDesignEmail] = useState("matze@test.de");
  const [designContent, setDesignContent] = useState("Text für den Flyer …");
  const [designLogo, setDesignLogo] = useState("RAMBO");

  const loadTemplates = useCallback(async () => {
    setTemplateLoadError("");
    try {
      const [officeData, designData] = await Promise.all([
        generatorService.getOfficeTemplates(),
        generatorService.getDesignTemplates(),
      ]);
      setTemplates({ office: officeData, design: designData });
    } catch (error) {
      setTemplateLoadError(String(error?.message ?? error));
    }
  }, []);

  useEffect(() => {
    void loadTemplates();
  }, [loadTemplates]);

  const handleGenerateWord = async () => {
    setLoading(true);
    setMessage("⏳ Generiere Word-Dokument...");
    try {
      const result = await generatorService.generateWordDocument(
        wordTitle,
        wordContent,
        wordTemplate,
        wordAuthor.trim() || undefined,
      );
      const fn = result?.file ?? "";
      setLastFile(fn);
      setMessage(fn ? `✅ Dokument generiert: ${fn}` : `✅ Dokument generiert.`);
    } catch (error) {
      setLastFile("");
      setMessage(`❌ Fehler: ${error.message}`);
    }
    setLoading(false);
  };

  const handleGenerateExcel = async () => {
    setLoading(true);
    setMessage("⏳ Generiere Excel...");
    try {
      const result = await generatorService.generateExcelSheet(excelTemplate);
      const fn = result?.file ?? "";
      setLastFile(fn);
      setMessage(fn ? `✅ Excel generiert: ${fn}` : `✅ Excel generiert.`);
    } catch (error) {
      setLastFile("");
      setMessage(`❌ Fehler: ${error.message}`);
    }
    setLoading(false);
  };

  const handleGeneratePowerPoint = async () => {
    setLoading(true);
    setMessage("⏳ Generiere PowerPoint...");
    try {
      const result = await generatorService.generatePowerPoint(pptTemplate);
      const fn = result?.file ?? "";
      setLastFile(fn);
      setMessage(fn ? `✅ PowerPoint generiert: ${fn}` : `✅ PowerPoint generiert.`);
    } catch (error) {
      setLastFile("");
      setMessage(`❌ Fehler: ${error.message}`);
    }
    setLoading(false);
  };

  const designFields = {
    designName,
    designTitle,
    designEmail,
    designContent,
    designLogo,
  };

  const handleGenerateDesign = async () => {
    setLoading(true);
    setMessage("⏳ Generiere Design (SVG)...");
    try {
      const vars = designVariablesFor(designType, designFields);
      const result = await generatorService.generateSVGDesign(designType, vars);
      const fn = result?.file ?? "";
      setLastFile(fn);
      setMessage(fn ? `✅ SVG generiert: ${fn} (CorelDRAW / Vektor)` : `✅ SVG generiert.`);
    } catch (error) {
      setLastFile("");
      setMessage(`❌ Fehler: ${error.message}`);
    }
    setLoading(false);
  };

  const handleGenerateBrandDesign = async () => {
    setLoading(true);
    setMessage("⏳ Generiere Design mit Markenfarben...");
    try {
      const vars = designVariablesFor(designType, designFields);
      const result = await generatorService.generateDesignTemplate(designType, brandStyle, vars);
      const fn = result?.file ?? "";
      setLastFile(fn);
      setMessage(fn ? `✅ Brand-Design: ${fn}` : `✅ Brand-Design generiert.`);
    } catch (error) {
      setLastFile("");
      setMessage(`❌ Fehler: ${error.message}`);
    }
    setLoading(false);
  };

  const handleDownload = async () => {
    if (!lastFile) return;
    setDownloadLoading(true);
    setMessage(`⏳ Lade ${lastFile} ...`);
    try {
      await generatorService.downloadGeneratedFile(lastFile);
      setMessage(`✅ Download gestartet: ${lastFile}`);
    } catch (error) {
      setMessage(`❌ Download fehlgeschlagen: ${error.message}`);
    }
    setDownloadLoading(false);
  };

  const messageTone = message.startsWith("✅")
    ? "success"
    : message.startsWith("❌")
      ? "error"
      : "info";

  return (
    <div className={`generator-ui${isModal ? " generator-ui--modal" : ""}`}>
      {!isModal && (
        <div className="generator-header">
          <h2>📁 Datei-Generator</h2>
          <p>Erstelle Dokumente, Designs und mehr</p>
        </div>
      )}

      <div className="generator-tabs">
        <button type="button" className={`tab-btn ${activeTab === "documents" ? "active" : ""}`} onClick={() => setActiveTab("documents")}>
          📄 Office-Dokumente
        </button>
        <button type="button" className={`tab-btn ${activeTab === "design" ? "active" : ""}`} onClick={() => setActiveTab("design")}>
          🎨 Designs
        </button>
        <button type="button" className={`tab-btn ${activeTab === "info" ? "active" : ""}`} onClick={() => setActiveTab("info")}>
          ℹ️ Info
        </button>
      </div>

      {activeTab === "documents" && (
        <div className="tab-content">
          <h3>📄 Office-Dokumente generieren</h3>

          <div className="form-section">
            <h4>Word-Dokument</h4>
            <input
              type="text"
              placeholder="Titel"
              value={wordTitle}
              onChange={(e) => setWordTitle(e.target.value)}
              className="form-input"
            />
            <textarea
              placeholder="Inhalt"
              value={wordContent}
              onChange={(e) => setWordContent(e.target.value)}
              className="form-input form-textarea"
            />
            <input
              type="text"
              placeholder="Autor (optional)"
              value={wordAuthor}
              onChange={(e) => setWordAuthor(e.target.value)}
              className="form-input"
            />
            <select value={wordTemplate} onChange={(e) => setWordTemplate(e.target.value)} className="form-input">
              <option value="letter">Brief</option>
              <option value="report">Bericht</option>
            </select>
            <button type="button" onClick={handleGenerateWord} disabled={loading} className="btn btn-primary">
              {loading ? "⏳ Wird generiert..." : "📄 Word generieren"}
            </button>
          </div>

          <div className="form-section">
            <h4>Excel-Sheet</h4>
            <select value={excelTemplate} onChange={(e) => setExcelTemplate(e.target.value)} className="form-input">
              <option value="budget">Budget</option>
              <option value="invoice">Rechnung</option>
            </select>
            <button type="button" onClick={handleGenerateExcel} disabled={loading} className="btn btn-primary">
              {loading ? "⏳ Wird generiert..." : "📊 Excel generieren"}
            </button>
          </div>

          <div className="form-section">
            <h4>PowerPoint-Präsentation</h4>
            <select value={pptTemplate} onChange={(e) => setPptTemplate(e.target.value)} className="form-input">
              <option value="presentation">Standard</option>
            </select>
            <button type="button" onClick={handleGeneratePowerPoint} disabled={loading} className="btn btn-primary">
              {loading ? "⏳ Wird generiert..." : "📈 PowerPoint generieren"}
            </button>
          </div>
        </div>
      )}

      {activeTab === "design" && (
        <div className="tab-content">
          <h3>🎨 SVG-Designs für CorelDRAW</h3>

          <div className="form-section">
            <label htmlFor="gen-design-type">Design-Typ</label>
            <select id="gen-design-type" value={designType} onChange={(e) => setDesignType(e.target.value)} className="form-input">
              <option value="business_card">Visitenkarte</option>
              <option value="flyer">Flyer</option>
              <option value="logo_background">Logo</option>
            </select>

            <label htmlFor="gen-brand-style">Brand-Style (Brand-Template)</label>
            <select id="gen-brand-style" value={brandStyle} onChange={(e) => setBrandStyle(e.target.value)} className="form-input">
              <option value="default">Klassisch (Blau)</option>
              <option value="modern">Modern (Schwarz/Neon)</option>
            </select>

            {(designType === "business_card" || designType === "logo_background") && (
              <>
                <label htmlFor="gen-name">Name</label>
                <input
                  id="gen-name"
                  type="text"
                  placeholder="Name"
                  value={designName}
                  onChange={(e) => setDesignName(e.target.value)}
                  className="form-input"
                />
              </>
            )}

            {(designType === "business_card" || designType === "flyer") && (
              <>
                <label htmlFor="gen-title">Titel / Überschrift</label>
                <input
                  id="gen-title"
                  type="text"
                  placeholder="Titel/Position oder Flyer-Titel"
                  value={designTitle}
                  onChange={(e) => setDesignTitle(e.target.value)}
                  className="form-input"
                />
              </>
            )}

            {designType === "business_card" && (
              <>
                <label htmlFor="gen-email">E-Mail</label>
                <input
                  id="gen-email"
                  type="email"
                  placeholder="E-Mail"
                  value={designEmail}
                  onChange={(e) => setDesignEmail(e.target.value)}
                  className="form-input"
                />
              </>
            )}

            {designType === "flyer" && (
              <>
                <label htmlFor="gen-flyer-body">Inhalt</label>
                <textarea
                  id="gen-flyer-body"
                  placeholder="Flyertext"
                  value={designContent}
                  onChange={(e) => setDesignContent(e.target.value)}
                  className="form-input form-textarea"
                />
              </>
            )}

            {designType === "logo_background" && (
              <>
                <label htmlFor="gen-logo-text">Logo-Text</label>
                <input
                  id="gen-logo-text"
                  type="text"
                  placeholder="Kürzel oder Firmenname im Kreis"
                  value={designLogo}
                  onChange={(e) => setDesignLogo(e.target.value)}
                  className="form-input"
                />
              </>
            )}

            <div className="generator-actions">
              <button type="button" onClick={handleGenerateDesign} disabled={loading} className="btn btn-primary">
                {loading ? "⏳ Wird generiert..." : "🎨 Design generieren"}
              </button>
              <button type="button" onClick={handleGenerateBrandDesign} disabled={loading} className="btn btn-secondary">
                {loading ? "⏳ ..." : "🎯 Mit Markenfarben"}
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === "info" && (
        <div className="tab-content">
          <h3>ℹ️ Templates &amp; Status</h3>

          <div className="info-section">
            <h4>Verbindung / Vorlagen</h4>
            {templateLoadError ? (
              <p className="info-line warn">⚠️ Vorlagen nicht geladen: {templateLoadError}</p>
            ) : (
              <p className="info-line ok">✅ Vorlagen vom Backend geladen.</p>
            )}
            <button type="button" className="btn btn-outline" onClick={() => void loadTemplates()}>
              🔄 Erneut laden
            </button>
          </div>

          <div className="info-section">
            <h4>Letzte generierte Datei</h4>
            <pre className="info-pre-inline">{lastFile || "— noch keine —"}</pre>
          </div>

          <div className="info-section">
            <h4>Office-Vorlagen (JSON)</h4>
            <pre>{JSON.stringify(templates.office, null, 2)}</pre>
          </div>

          <div className="info-section">
            <h4>Design-Templates (JSON)</h4>
            <pre>{JSON.stringify(templates.design, null, 2)}</pre>
          </div>
        </div>
      )}

      {message && (
        <div className={`message ${messageTone}`}>
          <div className="message-text">{message}</div>
          {lastFile ? (
            <button
              type="button"
              className="btn btn-download"
              disabled={downloadLoading || loading}
              onClick={() => void handleDownload()}
            >
              {downloadLoading ? "⏳ Download..." : "⬇️ Datei herunterladen"}
            </button>
          ) : null}
        </div>
      )}
    </div>
  );
}
