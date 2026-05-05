const API_BASE =
  import.meta.env.DEV && !import.meta.env.VITE_API_BASE
    ? ""
    : import.meta.env.VITE_API_BASE || "http://127.0.0.1:5001";

const ADMIN_TOKEN = import.meta.env.VITE_RAMBO_ADMIN_TOKEN || "Rambo-Admin-Token";

function apiUrl(path) {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${p}`;
}

export const codeService = {
  async uploadCode(filename, content) {
    const response = await fetch(apiUrl("/api/code/upload"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Rambo-Admin": ADMIN_TOKEN,
      },
      body: JSON.stringify({
        filename,
        content,
      }),
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }

    return data;
  },

  async processCode(fileId, action, instruction) {
    const response = await fetch(apiUrl("/api/code/process"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Rambo-Admin": ADMIN_TOKEN,
      },
      body: JSON.stringify({
        file_id: fileId,
        action,
        instruction,
      }),
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }

    return data;
  },

  async getCode(fileId) {
    const response = await fetch(apiUrl(`/api/code/view/${encodeURIComponent(fileId)}`), {
      headers: {
        "X-Rambo-Admin": ADMIN_TOKEN,
      },
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }

    return data;
  },

  async downloadCode(fileId) {
    const response = await fetch(apiUrl(`/api/code/download/${encodeURIComponent(fileId)}`), {
      headers: {
        "X-Rambo-Admin": ADMIN_TOKEN,
      },
    });

    if (!response.ok) {
      throw new Error("Download fehlgeschlagen");
    }

    return response.blob();
  },
};
