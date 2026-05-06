/** K.4 — Canvas per Ollama (Backend /api/canvas/ai-generate, lokal). */
const API_BASE =
  import.meta.env.DEV && !import.meta.env.VITE_API_BASE
    ? ""
    : import.meta.env.VITE_API_BASE || "http://127.0.0.1:5002";

const ADMIN_TOKEN =
  import.meta.env.VITE_RAMBO_ADMIN_TOKEN || "Rambo-Admin-Token";

function apiUrl(path) {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${p}`;
}

async function readJsonSafe(response) {
  if (response && typeof response.text !== "function" && typeof response.json === "function") {
    try {
      return await response.json();
    } catch {
      return {};
    }
  }
  const raw = await response.text();
  if (!raw || !raw.trim()) return {};
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

export const aiCanvasService = {
  /** GET /api/canvas/ollama-status — ohne Admin-Header (Health). */
  async checkOllamaStatus() {
    try {
      const response = await fetch(apiUrl("/api/canvas/ollama-status"));
      return await readJsonSafe(response);
    } catch {
      return { status: "offline" };
    }
  },

  /**
   * @param {string} prompt
   * @param {'turbo'|'brain'} [mode]
   * @param {unknown[]} [currentElements]
   */
  async generateCanvas(prompt, mode = "turbo", currentElements = []) {
    const response = await fetch(apiUrl("/api/canvas/ai-generate"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Rambo-Admin": ADMIN_TOKEN,
      },
      body: JSON.stringify({
        prompt,
        mode,
        elements: Array.isArray(currentElements) ? currentElements : [],
      }),
    });

    const data = await readJsonSafe(response);
    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    return data;
  },
};
