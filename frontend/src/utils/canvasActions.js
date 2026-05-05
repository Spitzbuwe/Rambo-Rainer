import {
  canvasAddElement,
  canvasClear,
  canvasDeleteElement,
  canvasUpdateElement,
  getSelectedElement,
  normalizeCanvasState,
} from "../store/canvasStore.js";
import { parseColor } from "./commandParser.js";

const CANVAS_W = 800;
const CANVAS_H = 600;

export const executeCanvasAction = (state, command) => {
  const base = normalizeCanvasState(state);

  if (!command.recognized) {
    return { state: base, message: command.suggestion ?? "Nicht erkannt." };
  }

  switch (command.action) {
    case "add":
      return handleAddElement(base, command);

    case "delete":
      return handleDeleteElement(base, command);

    case "deleteAll":
      return handleDeleteAll(base);

    case "updateColor":
      return handleUpdateColor(base, command);

    case "resize":
      return handleResize(base, command);

    case "center":
      return handleCenter(base, command);

    default:
      return { state: base, message: "Unbekannte Aktion." };
  }
};

function jitter() {
  return 40 + Math.random() * 80;
}

function handleAddElement(state, command) {
  const props = { ...command.props };
  const next = canvasAddElement(state, command.element, jitter(), jitter(), props);
  const fillLabel = props.fill ?? "Standard";
  return {
    state: normalizeCanvasState(next),
    message: `✅ ${command.element} hinzugefügt (${fillLabel})`,
  };
}

function handleDeleteElement(state, command) {
  if (command.target === "last" && state.elements.length > 0) {
    const lastElement = state.elements[state.elements.length - 1];
    const next = canvasDeleteElement(state, lastElement.id);
    return {
      state: normalizeCanvasState(next),
      message: `✅ Letztes Element (${lastElement.type}) gelöscht`,
    };
  }

  const selected = getSelectedElement(state);
  if (selected) {
    const next = canvasDeleteElement(state, selected.id);
    return {
      state: normalizeCanvasState(next),
      message: "✅ Ausgewähltes Element gelöscht",
    };
  }

  return {
    state,
    message: "⚠️ Kein Element zum Löschen (weder letztes noch ausgewählt).",
  };
}

function handleDeleteAll(state) {
  const n = state.elements.length;
  const next = canvasClear(state);
  return {
    state: normalizeCanvasState(next),
    message: `✅ Alle ${n} Elemente gelöscht`,
  };
}

function handleUpdateColor(state, command) {
  const selected = getSelectedElement(state);
  if (!selected) {
    return { state, message: "⚠️ Kein Element ausgewählt." };
  }

  const colorMatch = command.originalMessage.match(
    /(rot|blau|grün|gelb|orange|lila|schwarz|weiß)/i,
  );
  const name = colorMatch ? colorMatch[1] : "schwarz";
  const color = colorMatch ? parseColor(colorMatch[1]) : "#000000";

  const next = canvasUpdateElement(state, selected.id, { fill: color });
  return {
    state: normalizeCanvasState(next),
    message: `✅ Farbe geändert zu ${name} (${color})`,
  };
}

function handleResize(state, command) {
  const selected = getSelectedElement(state);
  if (!selected) {
    return { state, message: "⚠️ Kein Element ausgewählt." };
  }

  const factor = command.size ?? 1;
  const newWidth = Math.max(4, Math.round(selected.width * factor));
  const newHeight = Math.max(4, Math.round(selected.height * factor));

  const next = canvasUpdateElement(state, selected.id, {
    width: newWidth,
    height: newHeight,
  });
  return {
    state: normalizeCanvasState(next),
    message: factor > 1 ? "✅ Vergrößert" : "✅ Verkleinert",
  };
}

function handleCenter(state, _command) {
  const selected = getSelectedElement(state);
  if (!selected) {
    return { state, message: "⚠️ Kein Element ausgewählt." };
  }

  const centerX = (CANVAS_W - selected.width) / 2;
  const centerY = (CANVAS_H - selected.height) / 2;

  const next = canvasUpdateElement(state, selected.id, {
    x: Math.max(0, centerX),
    y: Math.max(0, centerY),
  });
  return {
    state: normalizeCanvasState(next),
    message: "✅ Element zentriert",
  };
}
