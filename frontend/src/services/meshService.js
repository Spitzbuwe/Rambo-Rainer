const API_BASE =
  import.meta.env.DEV && !import.meta.env.VITE_API_BASE
    ? ""
    : import.meta.env.VITE_API_BASE || "http://127.0.0.1:5001";

const ADMIN_TOKEN = import.meta.env.VITE_RAMBO_ADMIN_TOKEN || "Rambo-Admin-Token";

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

export const meshService = {
  async processMesh(filename, action) {
    try {
      const response = await fetch(apiUrl("/api/mesh/process"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Rambo-Admin": ADMIN_TOKEN,
        },
        body: JSON.stringify({ filename, action }),
      });

      console.log(`[meshService] Response Status: ${response.status}`);
      console.log(`[meshService] Content-Type: ${response.headers.get("content-type")}`);

      if (!response.ok) {
        let errorMsg = "Unbekannter Fehler";
        try {
          const errorData = await readJsonSafe(response);
          errorMsg = errorData.error || errorData.message || errorMsg;
        } catch {
          errorMsg = `HTTP ${response.status}`;
        }
        console.error(`[meshService] Error Response: ${errorMsg}`);
        throw new Error(errorMsg);
      }

      const contentLength = response.headers.get("content-length");
      if (contentLength === "0") {
        throw new Error("Leere Response vom Server");
      }

      const data = await readJsonSafe(response);
      if (!data || typeof data !== "object" || Array.isArray(data)) {
        throw new Error("Ungültige JSON-Response vom Server");
      }

      console.log("[meshService] Success Response:", data);
      console.log("🔵 [meshService] Response:", data);
      console.log("🔵 [meshService] Type:", data.type, "Path:", data.depth_map_path);
      return data;
    } catch (error) {
      console.error("[meshService] Fatal Error:", error);
      console.error("🔵 [meshService] Error:", error);
      throw error;
    }
  },

  async getMeshStatus(meshId) {
    const response = await fetch(apiUrl(`/api/mesh/status/${meshId}`), {
      headers: {
        "X-Rambo-Admin": ADMIN_TOKEN,
      },
    });

    const data = await readJsonSafe(response);
    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    return data;
  },
};
