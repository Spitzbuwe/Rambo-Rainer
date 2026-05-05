import React from "react";
import "./CanvasPropertyPanel.css";

export default function CanvasPropertyPanel({
  element,
  onUpdate,
  canvasBackground,
  onCanvasBackgroundChange,
}) {
  if (!element) {
    return (
      <div className="property-panel property-panel--canvas">
        <h3 className="property-panel__title">Canvas</h3>
        {typeof onCanvasBackgroundChange === "function" && (
          <div className="property-group">
            <label htmlFor="prop-canvas-bg">Hintergrundfarbe</label>
            <input
              id="prop-canvas-bg"
              type="color"
              value={toColorInput(canvasBackground)}
              onChange={(e) => onCanvasBackgroundChange(e.target.value)}
            />
          </div>
        )}
        <div className="properties-empty properties-empty--inline">
          <p>Element auswählen, um Eigenschaften zu bearbeiten.</p>
        </div>
      </div>
    );
  }

  const numOr = (v, d = 0) => {
    const n = Number.parseInt(String(v ?? ""), 10);
    return Number.isFinite(n) ? n : d;
  };

  return (
    <div className="property-panel">
      <h3 className="property-panel__title">Eigenschaften</h3>

      <div className="property-group">
        <label htmlFor="prop-x">Position X</label>
        <input
          id="prop-x"
          type="number"
          value={Math.round(element.x)}
          onChange={(e) => onUpdate({ x: numOr(e.target.value, element.x) })}
        />
      </div>

      <div className="property-group">
        <label htmlFor="prop-y">Position Y</label>
        <input
          id="prop-y"
          type="number"
          value={Math.round(element.y)}
          onChange={(e) => onUpdate({ y: numOr(e.target.value, element.y) })}
        />
      </div>

      {(element.type === "rect" || element.type === "circle" || element.type === "image") && (
        <>
          <div className="property-group">
            <label htmlFor="prop-w">Breite</label>
            <input
              id="prop-w"
              type="number"
              min={4}
              value={Math.round(element.width)}
              onChange={(e) => onUpdate({ width: Math.max(4, numOr(e.target.value, element.width)) })}
            />
          </div>
          <div className="property-group">
            <label htmlFor="prop-h">Höhe</label>
            <input
              id="prop-h"
              type="number"
              min={4}
              value={Math.round(element.height)}
              onChange={(e) => onUpdate({ height: Math.max(4, numOr(e.target.value, element.height)) })}
            />
          </div>
        </>
      )}

      {element.type !== "text" && (
        <div className="property-group">
          <label htmlFor="prop-fill">Füllfarbe</label>
          <input
            id="prop-fill"
            type="color"
            value={toColorInput(element.fill)}
            onChange={(e) => onUpdate({ fill: e.target.value })}
          />
        </div>
      )}

      {element.type !== "text" && (
        <>
          <div className="property-group">
            <label htmlFor="prop-stroke">Randfarbe</label>
            <input
              id="prop-stroke"
              type="color"
              value={toColorInput(element.stroke)}
              onChange={(e) => onUpdate({ stroke: e.target.value })}
            />
          </div>
          <div className="property-group">
            <label htmlFor="prop-sw">Randbreite</label>
            <input
              id="prop-sw"
              type="number"
              min={0}
              max={20}
              value={element.strokeWidth ?? 0}
              onChange={(e) => onUpdate({ strokeWidth: numOr(e.target.value, 0) })}
            />
          </div>
        </>
      )}

      {element.type === "text" && (
        <>
          <div className="property-group">
            <label htmlFor="prop-text">Text</label>
            <input
              id="prop-text"
              type="text"
              value={element.text ?? ""}
              onChange={(e) => onUpdate({ text: e.target.value })}
            />
          </div>
          <div className="property-group">
            <label htmlFor="prop-ff">Schriftart</label>
            <select
              id="prop-ff"
              value={element.fontFamily ?? "Arial, sans-serif"}
              onChange={(e) => onUpdate({ fontFamily: e.target.value })}
            >
              <option value="Arial, sans-serif">Arial</option>
              <option value="Georgia, serif">Georgia</option>
              <option value="'Courier New', monospace">Courier New</option>
              <option value="system-ui, sans-serif">System UI</option>
            </select>
          </div>
          <div className="property-group">
            <label htmlFor="prop-fs">Schriftgröße</label>
            <input
              id="prop-fs"
              type="number"
              min={8}
              max={120}
              value={element.fontSize ?? 16}
              onChange={(e) => onUpdate({ fontSize: Math.max(8, numOr(e.target.value, 16)) })}
            />
          </div>
          <div className="property-group">
            <label htmlFor="prop-fill-t">Farbe</label>
            <input
              id="prop-fill-t"
              type="color"
              value={toColorInput(element.fill)}
              onChange={(e) => onUpdate({ fill: e.target.value })}
            />
          </div>
        </>
      )}
    </div>
  );
}

function toColorInput(val) {
  const s = String(val ?? "#000000").trim();
  if (/^#[0-9a-fA-F]{6}$/.test(s)) return s;
  if (/^#[0-9a-fA-F]{3}$/.test(s)) {
    const r = s[1];
    const g = s[2];
    const b = s[3];
    return `#${r}${r}${g}${g}${b}${b}`;
  }
  return "#333333";
}
