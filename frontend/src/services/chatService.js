/** Wie App.jsx / generatorService — im Dev oft leerer Base = Vite-Proxy. */
const API_BASE =
  import.meta.env.DEV && !import.meta.env.VITE_API_BASE
    ? ""
    : import.meta.env.VITE_API_BASE || "http://127.0.0.1:5001";

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

export const chatService = {
  async sendMessage(message, context = {}) {
    const response = await fetch(apiUrl("/api/chat/message"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, context }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return readJsonSafe(response);
  },

  async getHistory() {
    const response = await fetch(apiUrl("/api/chat/history"));
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return readJsonSafe(response);
  },
};
