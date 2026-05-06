const API_BASE =
  import.meta.env.DEV && !import.meta.env.VITE_API_BASE
    ? ""
    : import.meta.env.VITE_API_BASE || "http://127.0.0.1:5002";

const ADMIN_TOKEN = import.meta.env.VITE_RAMBO_ADMIN_TOKEN || "Rambo-Admin-Token";

function apiUrl(path) {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${p}`;
}

async function readJsonSafe(response) {
  const raw = await response.text();
  if (!raw || !raw.trim()) return {};
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

export const imageService = {
  async processImage(filename, action) {
    const response = await fetch(apiUrl("/api/image/process"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Rambo-Admin": ADMIN_TOKEN,
      },
      body: JSON.stringify({
        filename,
        action,
      }),
    });

    const data = await readJsonSafe(response);
    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    return data;
  },
};
