import React from "react";
import "./LayersPanel.css";

export default function LayersPanel({
  elements,
  selectedId,
  onSelectElement,
  onDeleteElement,
  onMoveLayer,
}) {
  return (
    <aside className="layers-panel">
      <h3 className="layers-panel__title">Ebenen</h3>
      <div className="layers-list">
        {elements.length === 0 ? (
          <p className="layers-empty">Keine Elemente</p>
        ) : (
          [...elements].reverse().map((element, revIdx) => {
            const index = elements.length - 1 - revIdx;
            return (
              <div
                key={element.id}
                className={`layer-item${selectedId === element.id ? " active" : ""}`}
                onClick={() => onSelectElement(element.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelectElement(element.id);
                  }
                }}
                role="button"
                tabIndex={0}
              >
                <span className="layer-icon" aria-hidden>
                  {element.type === "rect" && "▭"}
                  {element.type === "circle" && "●"}
                  {element.type === "text" && "T"}
                  {element.type === "image" && "🖼"}
                </span>
                <span className="layer-name">
                  {element.type} #{index + 1}
                </span>
                <span className="layer-actions">
                  <button
                    type="button"
                    className="layer-move"
                    title="Nach vorne"
                    onClick={(e) => {
                      e.stopPropagation();
                      onMoveLayer(index, Math.min(elements.length - 1, index + 1));
                    }}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    className="layer-move"
                    title="Nach hinten"
                    onClick={(e) => {
                      e.stopPropagation();
                      onMoveLayer(index, Math.max(0, index - 1));
                    }}
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    className="layer-delete"
                    title="Löschen"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteElement(element.id);
                    }}
                  >
                    ✕
                  </button>
                </span>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}
