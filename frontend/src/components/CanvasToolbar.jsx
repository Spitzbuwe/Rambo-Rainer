import React, { useRef } from "react";
import "./CanvasToolbar.css";

export default function CanvasToolbar({
  onAddElement,
  onAddImageFromFile,
  onClear,
  zoom,
  onZoomChange,
  onExportSvg,
  onExportPng,
  onExportPdfHint,
}) {
  const fileRef = useRef(null);

  return (
    <div className="canvas-toolbar">
      <div className="toolbar-section">
        <button type="button" className="toolbar-btn" onClick={() => onAddElement("rect")} title="Rechteck">
          ▭ Rechteck
        </button>
        <button type="button" className="toolbar-btn" onClick={() => onAddElement("circle")} title="Kreis">
          ● Kreis
        </button>
        <button type="button" className="toolbar-btn" onClick={() => onAddElement("text")} title="Text">
          T Text
        </button>
        <button
          type="button"
          className="toolbar-btn"
          onClick={() => fileRef.current?.click()}
          title="Bild aus Datei"
        >
          🖼 Bild
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="canvas-toolbar-file"
          aria-hidden
          tabIndex={-1}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f && onAddImageFromFile) onAddImageFromFile(f);
            e.target.value = "";
          }}
        />
      </div>

      <div className="toolbar-separator" aria-hidden />

      <div className="toolbar-section toolbar-zoom">
        <label htmlFor="canvas-zoom-range">Zoom: {zoom}%</label>
        <input
          id="canvas-zoom-range"
          type="range"
          min={10}
          max={200}
          value={zoom}
          onChange={(e) => onZoomChange(Number(e.target.value))}
          className="toolbar-slider"
        />
      </div>

      <div className="toolbar-separator" aria-hidden />

      <div className="toolbar-section">
        <button type="button" className="toolbar-btn toolbar-btn-export" onClick={onExportSvg} title="SVG herunterladen">
          ⬇ SVG
        </button>
        <button type="button" className="toolbar-btn toolbar-btn-export" onClick={onExportPng} title="PNG herunterladen">
          ⬇ PNG
        </button>
        <button
          type="button"
          className="toolbar-btn toolbar-btn-muted"
          onClick={onExportPdfHint}
          title="PDF-Export ist für eine spätere Phase vorgesehen"
          disabled
        >
          PDF
        </button>
        <button type="button" className="toolbar-btn toolbar-btn-danger" onClick={onClear} title="Alles löschen">
          🗑 Leeren
        </button>
      </div>
    </div>
  );
}
