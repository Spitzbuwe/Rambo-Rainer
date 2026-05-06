/** API-Basis wie in App.jsx — im Dev-Vite oft leer (= Proxy). */
const API_BASE =
  import.meta.env.DEV && !import.meta.env.VITE_API_BASE
    ? ""
    : import.meta.env.VITE_API_BASE || "http://127.0.0.1:5002";

const ADMIN_TOKEN =
  import.meta.env.VITE_RAMBO_ADMIN_TOKEN || "Rambo-Admin-Token";

function apiUrl(pathOrQuery) {
  const p = pathOrQuery.startsWith("/") ? pathOrQuery : `/${pathOrQuery}`;
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

async function apiPost(path, body) {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Rambo-Admin": ADMIN_TOKEN,
    },
    body: JSON.stringify(body ?? {}),
  });
  if (!response.ok) {
    let detail = "";
    try {
      const errJson = await readJsonSafe(response);
      detail =
        typeof errJson?.error === "string"
          ? errJson.error
          : typeof errJson?.message === "string"
            ? errJson.message
            : "";
    } catch {
      void 0;
    }
    throw new Error(detail ? `HTTP ${response.status}: ${detail}` : `HTTP ${response.status}`);
  }
  return readJsonSafe(response);
}

async function apiGet(path) {
  const response = await fetch(apiUrl(path));
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return readJsonSafe(response);
}

export const generatorService = {
  async generateWordDocument(title, content, templateType = "letter", author) {
    const body = {
      template_type: templateType,
      title,
      content,
    };
    if (author) body.author = author;
    return apiPost("/api/generate/word-document", body);
  },

  async generateExcelSheet(templateType = "budget") {
    return apiPost("/api/generate/excel-sheet", {
      template_type: templateType,
    });
  },

  async generatePowerPoint(templateType = "presentation") {
    return apiPost("/api/generate/powerpoint", {
      template_type: templateType,
    });
  },

  async generateSVGDesign(templateType, variables = {}) {
    return apiPost("/api/generate/svg-design", {
      template_type: templateType,
      variables,
    });
  },

  async generateDesignTemplate(designType, brandStyle = "default", variables = {}) {
    return apiPost("/api/generate/design-template", {
      design_type: designType,
      brand_style: brandStyle,
      variables,
    });
  },

  async getOfficeTemplates() {
    return apiGet("/api/generate/office-templates");
  },

  async getDesignTemplates() {
    return apiGet("/api/generate/design-templates");
  },

  /** Lädt die zuletzt erzeugte Datei als Blob und triggert Browser-Download (Admin-Header). */
  async downloadGeneratedFile(fileName) {
    if (!fileName) throw new Error("file_required");
    const url = apiUrl(`/api/generate/download?file=${encodeURIComponent(fileName)}`);
    const response = await fetch(url, {
      headers: {
        "X-Rambo-Admin": ADMIN_TOKEN,
      },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    const a = document.createElement("a");
    const objectUrl = URL.createObjectURL(blob);
    a.href = objectUrl;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(objectUrl);
  },
};
