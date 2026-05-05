import React, { useCallback, useEffect, useMemo } from "react";
import { DndProvider } from "react-dnd";
import { HTML5Backend } from "react-dnd-html5-backend";
import {
  canvasAddElement,
  canvasClear,
  canvasDeleteElement,
  canvasReorderElements,
  canvasSelect,
  canvasSetZoom,
  canvasUpdateElement,
  getSelectedElement,
  normalizeCanvasState,
} from "../store/canvasStore.js";
import { downloadPng, downloadSvg } from "../utils/canvasExport.js";
import CanvasToolbar from "./CanvasToolbar.jsx";
import LayersPanel from "./LayersPanel.jsx";
import CanvasWorkspace from "./CanvasWorkspace.jsx";
import CanvasPropertyPanel from "./CanvasPropertyPanel.jsx";
import "./Canvas.css";

export default function Canvas({ state: rawState, onChange }) {
  const state = useMemo(() => normalizeCanvasState(rawState), [rawState]);

  const dispatch = useCallback(
    (fn) => {
      onChange((prev) => fn(normalizeCanvasState(prev)));
    },
    [onChange],
  );

  const selected = useMemo(() => getSelectedElement(state), [state]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== "Delete" && e.key !== "Backspace") return;
      const t = e.target;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) return;
      if (!state.selectedId) return;
      e.preventDefault();
      dispatch((s) => canvasDeleteElement(s, s.selectedId));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dispatch, state.selectedId]);

  const handleAddImageFromFile = useCallback(
    (file) => {
      const reader = new FileReader();
      reader.onload = () => {
        const href = String(reader.result || "");
        dispatch((s) =>
          canvasAddElement(s, "image", 72, 72, {
            width: 220,
            height: 160,
            href,
            fill: "#ffffff",
            strokeWidth: 0,
          }),
        );
      };
      reader.readAsDataURL(file);
    },
    [dispatch],
  );

  return (
    <DndProvider backend={HTML5Backend}>
      <div className="canvas-container">
        <div className="canvas-header-row">
          <div className="canvas-title">
            <h2>🎨 Canvas</h2>
          </div>
        </div>

        <CanvasToolbar
          onAddElement={(type) => dispatch((s) => canvasAddElement(s, type))}
          onAddImageFromFile={handleAddImageFromFile}
          onClear={() => {
            if (!window.confirm("Alle Elemente wirklich löschen?")) return;
            dispatch((s) => canvasClear(s));
          }}
          zoom={state.zoom}
          onZoomChange={(z) => dispatch((s) => canvasSetZoom(s, z))}
          onExportSvg={() => downloadSvg(state.elements, state.backgroundColor)}
          onExportPng={() => downloadPng(state.elements, state.backgroundColor)}
          onExportPdfHint={() => {
            window.alert("PDF-Export ist für eine spätere Phase vorgesehen.");
          }}
        />

        <div className="canvas-main">
          <LayersPanel
            elements={state.elements}
            selectedId={state.selectedId}
            onSelectElement={(id) => dispatch((s) => canvasSelect(s, id))}
            onDeleteElement={(id) => dispatch((s) => canvasDeleteElement(s, id))}
            onMoveLayer={(from, to) => {
              if (from === to) return;
              dispatch((s) => canvasReorderElements(s, from, to));
            }}
          />

          <CanvasWorkspace
            elements={state.elements}
            selectedId={state.selectedId}
            zoom={state.zoom}
            backgroundColor={state.backgroundColor}
            onSelectElement={(id) => dispatch((s) => canvasSelect(s, id))}
            onUpdateElement={(id, updates) => dispatch((s) => canvasUpdateElement(s, id, updates))}
          />

          <div className="canvas-properties">
            <CanvasPropertyPanel
              element={selected}
              canvasBackground={state.backgroundColor}
              onCanvasBackgroundChange={(c) => dispatch((s) => ({ ...s, backgroundColor: c }))}
              onUpdate={(updates) => {
                if (!selected) return;
                dispatch((s) => canvasUpdateElement(s, selected.id, updates));
              }}
            />
          </div>
        </div>

        <div className="canvas-footer">
          <span>
            Zoom: {state.zoom}% · Elemente: {state.elements.length}
          </span>
          <span>
            {selected ? `Ausgewählt: ${selected.type}` : "Kein Element ausgewählt"}
          </span>
        </div>
      </div>
    </DndProvider>
  );
}
