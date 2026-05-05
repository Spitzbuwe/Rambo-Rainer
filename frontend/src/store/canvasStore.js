import { v4 as uuidv4 } from "uuid";

/** Standard-Zustand für Design-Studio-Canvas (immutable Updates). */
export function createInitialCanvasState() {
  return {
    elements: [],
    selectedId: null,
    zoom: 100,
    backgroundColor: "#ffffff",
  };
}

/** Legacy: zoom 0–2, selectedElement, text.content → normalisieren. */
export function normalizeCanvasState(raw) {
  const base = createInitialCanvasState();
  if (!raw || typeof raw !== "object") return base;

  let zoom = raw.zoom ?? base.zoom;
  if (typeof zoom === "number" && zoom > 0 && zoom <= 2) {
    zoom = Math.round(zoom * 100);
  }
  if (typeof zoom !== "number" || zoom < 10 || zoom > 200) {
    zoom = base.zoom;
  }

  const elements = Array.isArray(raw.elements)
    ? raw.elements.map((el) => {
        if (el?.type === "text" && el.content != null && el.text == null) {
          return { ...el, text: String(el.content) };
        }
        return el;
      })
    : [];

  let selectedId = raw.selectedId ?? null;
  if (selectedId == null && raw.selectedElement && typeof raw.selectedElement === "object") {
    selectedId = raw.selectedElement.id ?? null;
  }

  const backgroundColor =
    typeof raw.backgroundColor === "string" ? raw.backgroundColor : base.backgroundColor;

  return {
    ...base,
    ...raw,
    zoom,
    elements,
    selectedId,
    backgroundColor,
  };
}

export function canvasAddElement(state, type, x = 80, y = 80, props = {}) {
  const base = {
    id: uuidv4(),
    type,
    x,
    y,
    width: props.width ?? (type === "text" ? 200 : 100),
    height: props.height ?? (type === "text" ? 36 : 100),
    fill: props.fill ?? (type === "text" ? "#111827" : "#667eea"),
    stroke: props.stroke ?? "#000000",
    strokeWidth: props.strokeWidth ?? 1,
    rotation: props.rotation ?? 0,
    text: props.text ?? (type === "text" ? "Text" : ""),
    fontSize: props.fontSize ?? 18,
    fontFamily: props.fontFamily ?? "Arial, sans-serif",
    fontWeight: props.fontWeight ?? "normal",
    href: props.href ?? "",
    ...props,
  };
  return {
    ...state,
    elements: [...state.elements, base],
    selectedId: base.id,
  };
}

export function canvasDeleteElement(state, id) {
  return {
    ...state,
    elements: state.elements.filter((el) => el.id !== id),
    selectedId: state.selectedId === id ? null : state.selectedId,
  };
}

export function canvasUpdateElement(state, id, updates) {
  return {
    ...state,
    elements: state.elements.map((el) => (el.id === id ? { ...el, ...updates } : el)),
  };
}

export function canvasMoveElement(state, id, x, y) {
  return canvasUpdateElement(state, id, { x, y });
}

export function canvasSelect(state, id) {
  return { ...state, selectedId: id };
}

export function canvasClear(state) {
  return { ...state, elements: [], selectedId: null };
}

export function canvasSetZoom(state, zoom) {
  const z = Math.max(10, Math.min(200, Number(zoom) || 100));
  return { ...state, zoom: z };
}

export function canvasReorderElements(state, fromIndex, toIndex) {
  const next = [...state.elements];
  const [removed] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, removed);
  return { ...state, elements: next };
}

export function getSelectedElement(state) {
  if (!state.selectedId) return null;
  return state.elements.find((el) => el.id === state.selectedId) ?? null;
}
