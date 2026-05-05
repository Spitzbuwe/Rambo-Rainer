import React, { useRef, useCallback } from "react";
import "./CanvasWorkspace.css";

const VIEW_W = 800;
const VIEW_H = 600;

export default function CanvasWorkspace({
  elements,
  selectedId,
  zoom,
  backgroundColor,
  onSelectElement,
  onUpdateElement,
}) {
  const svgRef = useRef(null);

  const clientToSvg = useCallback((clientX, clientY) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const pt = svg.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    const p = pt.matrixTransform(ctm.inverse());
    return { x: p.x, y: p.y };
  }, []);

  const beginDrag = useCallback(
    (e, el) => {
      if (!el) return;
      e.stopPropagation();
      e.preventDefault();
      onSelectElement(el.id);
      const p = clientToSvg(e.clientX, e.clientY);
      const ox = p.x - el.x;
      const oy = p.y - el.y;

      const move = (ev) => {
        const q = clientToSvg(ev.clientX, ev.clientY);
        let nx = q.x - ox;
        let ny = q.y - oy;
        const w = el.width ?? 100;
        const h = el.height ?? 100;
        nx = Math.max(0, Math.min(VIEW_W - w, nx));
        ny = Math.max(0, Math.min(VIEW_H - h, ny));
        onUpdateElement(el.id, { x: nx, y: ny });
      };

      const up = () => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
        window.removeEventListener("pointercancel", up);
      };

      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
      window.addEventListener("pointercancel", up);
    },
    [clientToSvg, onSelectElement, onUpdateElement],
  );

  const scale = zoom / 100;

  if (elements.length === 0) {
    return (
      <div className="canvas-workspace-shell canvas-workspace-shell--empty">
        <div className="canvas-empty">
          <div className="empty-message">
            <p>Canvas ist leer</p>
            <p className="empty-hint">
              Toolbar: Rechteck, Kreis, Text oder Bild hinzufügen · Zoom mit dem Schieberegler
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="canvas-workspace-shell">
      <div
        className="canvas-workspace-scale"
        style={{
          transform: `scale(${scale})`,
          transformOrigin: "top left",
        }}
      >
        <svg
          ref={svgRef}
          className="canvas-svg-main"
          viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
          width={VIEW_W}
          height={VIEW_H}
          role="img"
          aria-label="Design-Canvas"
          style={{ backgroundColor: backgroundColor || "#ffffff" }}
          onPointerDown={(e) => {
            if (e.target === svgRef.current) {
              onSelectElement(null);
            }
          }}
        >
          {elements.map((el) => {
            const isSel = selectedId === el.id;
            if (el.type === "rect") {
              return (
                <g key={el.id}>
                  <rect
                    x={el.x}
                    y={el.y}
                    width={el.width}
                    height={el.height}
                    fill={el.fill}
                    stroke={el.stroke}
                    strokeWidth={el.strokeWidth ?? 0}
                    style={{ cursor: "grab" }}
                    onPointerDown={(e) => beginDrag(e, el)}
                  />
                  {isSel && (
                    <rect
                      x={el.x}
                      y={el.y}
                      width={el.width}
                      height={el.height}
                      fill="none"
                      stroke="#667eea"
                      strokeWidth={2}
                      strokeDasharray="6 4"
                      pointerEvents="none"
                    />
                  )}
                </g>
              );
            }
            if (el.type === "circle") {
              const r = el.width / 2;
              const cx = el.x + r;
              const cy = el.y + r;
              return (
                <g key={el.id}>
                  <circle
                    cx={cx}
                    cy={cy}
                    r={r}
                    fill={el.fill}
                    stroke={el.stroke}
                    strokeWidth={el.strokeWidth ?? 0}
                    style={{ cursor: "grab" }}
                    onPointerDown={(e) => beginDrag(e, el)}
                  />
                  {isSel && (
                    <rect
                      x={el.x}
                      y={el.y}
                      width={el.width}
                      height={el.height}
                      fill="none"
                      stroke="#667eea"
                      strokeWidth={2}
                      strokeDasharray="6 4"
                      pointerEvents="none"
                    />
                  )}
                </g>
              );
            }
            if (el.type === "text") {
              const fs = el.fontSize ?? 16;
              return (
                <g key={el.id}>
                  <text
                    x={el.x}
                    y={el.y + fs}
                    fontSize={fs}
                    fontFamily={el.fontFamily || "Arial"}
                    fontWeight={el.fontWeight || "normal"}
                    fill={el.fill}
                    style={{ cursor: "grab" }}
                    onPointerDown={(e) => beginDrag(e, el)}
                  >
                    {el.text ?? ""}
                  </text>
                  {isSel && (
                    <rect
                      x={el.x}
                      y={el.y}
                      width={el.width}
                      height={el.height}
                      fill="none"
                      stroke="#667eea"
                      strokeWidth={2}
                      strokeDasharray="6 4"
                      pointerEvents="none"
                    />
                  )}
                </g>
              );
            }
            if (el.type === "image" && el.href) {
              return (
                <g key={el.id}>
                  <image
                    href={el.href}
                    x={el.x}
                    y={el.y}
                    width={el.width}
                    height={el.height}
                    preserveAspectRatio="xMidYMid meet"
                    style={{ cursor: "grab" }}
                    onPointerDown={(e) => beginDrag(e, el)}
                  />
                  {isSel && (
                    <rect
                      x={el.x}
                      y={el.y}
                      width={el.width}
                      height={el.height}
                      fill="none"
                      stroke="#667eea"
                      strokeWidth={2}
                      strokeDasharray="6 4"
                      pointerEvents="none"
                    />
                  )}
                </g>
              );
            }
            return null;
          })}
        </svg>
      </div>
    </div>
  );
}
