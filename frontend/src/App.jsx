import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import { RamboManagementDashboard } from "./components/RamboManagementDashboard.jsx";
import AdminDashboardWrapper from "./components/AdminDashboardWrapper.jsx";
import TopNavigation from "./components/TopNavigation.jsx";
import RainerAgent from "./components/RainerAgent.jsx";
import DesignStudio from "./components/DesignStudio.jsx";
import { parseImageIntent, parseImageGenerationIntent } from "./utils/imageIntentParser.js";
import { imageService } from "./services/imageService.js";
import { parse3DIntent, is3DIntent, isTextTo3dChatPrompt } from "./utils/meshIntentParser.js";
import { parseCodeIntent, isCodeIntent } from "./utils/codeIntentParser.js";
import { codeService } from "./services/codeService.js";
import CodeViewer from "./components/CodeViewer.jsx";
import MeshPreview from "./components/MeshPreview.jsx";

/** Dev: leer → Requests über Vite-Proxy (vite.config.js) nach Backend-Port (5002). */
const API_BASE =
  import.meta.env.DEV && !import.meta.env.VITE_API_BASE
    ? ""
    : (import.meta.env.VITE_API_BASE || "http://127.0.0.1:5002");
const RAMBO_ADMIN_TOKEN = (import.meta.env.VITE_RAMBO_ADMIN_TOKEN || "").trim();

/** Bis zur ersten gültigen GET-/api/status-Antwort — bewusst kein Erfolgslabel. */
const BACKEND_STATUS_PENDING = "Prüfe Verbindung...";

const TT_HEAD_STATUS =
  "Quelle: GET /api/status (alle 10 s). Grün bei backend_ok oder status ok/running/healthy. „Nicht erreichbar“ = Netzwerk/Proxy/Backend nicht erreichbar — nicht Ollama.";
const TT_PANEL_BACKEND =
  "Backend-Zeile = GET /api/status (wie Kopfzeile). „Verbunden“ = Poll erfolgreich. Verwechseln mit Rambo Health (/api/health) oder Ollama (Chat/Canvas).";
const STATUS_SOURCE_NOTE = "Quelle: /api/status (10s Poll)";

function truncateUiText(s, max = 44) {
  const t = String(s || "")
    .replace(/\s+/g, " ")
    .trim();
  if (!t) return "";
  if (t.length <= max) return t;
  return `${t.slice(0, Math.max(1, max - 1))}…`;
}

function mapQualityGraphEntry(e) {
  if (!e || typeof e !== "object") return null;
  const finalFailed = Number(e.final_failed_count ?? 0);
  const checks = Array.isArray(e.checks) ? e.checks : [];
  return {
    checkScore: Number.isFinite(Number(e.score)) ? Number(e.score) : null,
    initialFailed: Number(e.initial_failed_count ?? 0),
    finalFailed,
    fixRounds: Array.isArray(e.fix_rounds) ? e.fix_rounds.length : 0,
    at: String(e.timestamp || "—"),
    evalScore: Number.isFinite(Number(e.eval_avg_score)) ? Number(e.eval_avg_score) : null,
    passedCount: null,
    failedCount: null,
    taskLabel: truncateUiText(e.task, 40),
    checksCount: checks.length,
    autoFixOn: Boolean(e.auto_fix),
    statusOk: finalFailed === 0,
    statusLabel: finalFailed === 0 ? "OK" : "OFFEN",
  };
}

function apiUrl(pathOrQuery) {
  const p = pathOrQuery.startsWith("/") ? pathOrQuery : `/${pathOrQuery}`;
  return `${API_BASE}${p}`;
}

/** Alle fetch-Aufrufe ans Backend: Standard-Header X-Rambo-Admin (überschreibbar). */
const CODE_FILE_EXTENSIONS = [".py", ".js", ".jsx", ".html", ".css", ".ts", ".tsx"];

function isCodeFilename(name) {
  const n = String(name || "").toLowerCase();
  return CODE_FILE_EXTENSIONS.some((ext) => n.endsWith(ext));
}

/** Wie ChatPanel: MIME image/* oder Bild-Extension (Windows liefert oft leeren type). */
function isUploadedImageForPipeline(meta) {
  const name = String(meta?.name || "").trim();
  if (!name) return false;
  const t = String(meta?.type || "").toLowerCase();
  if (t.startsWith("image/")) return true;
  // Windows: häufig .jfif statt .jpg; sonst kein Bild-Pfad → kein /api/image/process
  return /\.(jpg|jpeg|jpe|jfif|png|gif|webp|bmp|tif|tiff)$/i.test(name);
}

function formatCodePipelineErrorMessage(rawError) {
  const msg = String(rawError?.message || rawError || "").trim();
  if (!msg) return "⚠️ Code-Verarbeitung fehlgeschlagen.";
  if (
    /ollama.*nicht erreichbar/i.test(msg) ||
    msg.includes("HTTP 503") ||
    msg.includes("503")
  ) {
    return "âŒ Ollama ist nicht erreichbar. Bitte lokal `ollama serve` starten und erneut versuchen.";
  }
  if (/timeout|HTTP 504|504/i.test(msg)) {
    return "⏱️ Ollama-Timeout bei Code-Verarbeitung. Bitte erneut versuchen.";
  }
  if (/extrahiert|keine verwertbare antwort|502|HTTP 502/i.test(msg)) {
    return "⚠️ Ollama-Antwort war leer oder unbrauchbar. Bitte Prompt präzisieren und erneut ausführen.";
  }
  return `⚠️ Code-Verarbeitung fehlgeschlagen: ${msg}`;
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function apiFetchWithRetry(pathOrUrl, init = {}, { retries = 3, baseDelayMs = 450 } = {}) {
  let lastErr = null;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await apiFetch(pathOrUrl, init);
    } catch (e) {
      lastErr = e;
      if (attempt < retries) await sleep(baseDelayMs * 2 ** attempt);
    }
  }
  throw lastErr;
}

function apiFetch(pathOrUrl, init = {}) {
  const url =
    pathOrUrl.startsWith("http://") || pathOrUrl.startsWith("https://")
      ? pathOrUrl
      : apiUrl(pathOrUrl);
  const headers = new Headers(init.headers ?? undefined);
  if (!headers.has("X-Rambo-Admin")) {
    headers.set("X-Rambo-Admin", RAMBO_ADMIN_TOKEN);
  }
  return fetch(url, { ...init, headers });
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

const MEMORY_STORAGE_KEY = "rainer-dashboard-memory";

const DEFAULT_MEMORY = {
  facts: ["System lokal aufgesetzt", "Ollama aktiv", "Pollinations aktiv"],
  problems: ["Keine Meldungen"],
  project: ["backend/server.py", "src/App.jsx", "src/App.css"],
};

function readStoredMemory() {
  try {
    const raw = localStorage.getItem(MEMORY_STORAGE_KEY);
    if (!raw) return null;
    const o = JSON.parse(raw);
    if (!o || typeof o !== "object") return null;
    return {
      facts: Array.isArray(o.facts) ? o.facts.map(String) : [...DEFAULT_MEMORY.facts],
      problems: Array.isArray(o.problems) ? o.problems.map(String) : [...DEFAULT_MEMORY.problems],
      project:
        Array.isArray(o.project) && o.project.length > 0
          ? o.project.map(String)
          : [...DEFAULT_MEMORY.project],
    };
  } catch {
    return null;
  }
}

const INITIAL_MEMORY = readStoredMemory() || {
  facts: [...DEFAULT_MEMORY.facts],
  problems: [...DEFAULT_MEMORY.problems],
  project: [...DEFAULT_MEMORY.project],
};

function _pickFirstString(...vals) {
  for (const v of vals) {
    if (v == null) continue;
    const t = String(v).trim();
    if (t && t !== "—" && t !== "-") return t;
  }
  return "";
}

function _cleanUiText(s) {
  return String(s || "")
    .replace(/Â·/g, "·")
    .replace(/ollama_404_plan_fallback_local/gi, "Lokaler Fallback aktiv")
    .replace(/\bertselle\b/gi, "erstelle")
    .trim();
}

/** Datenbindung Statuspanel: Backend state + status_report + rambo + level4/5 */
function buildCodingAgentPanelView(agentL4) {
  const raw = agentL4 && typeof agentL4 === "object" ? agentL4 : {};
  const sr = raw.status_report && typeof raw.status_report === "object" ? raw.status_report : {};
  const rambo = raw.rambo && typeof raw.rambo === "object" ? raw.rambo : {};
  const l4 = raw.level4 && typeof raw.level4 === "object" ? raw.level4 : null;
  const l5 = raw.level5 && typeof raw.level5 === "object" ? raw.level5 : null;

  const deAgentStatus = (s) => {
    const t = _pickFirstString(s);
    if (!t) return "Bereit";
    const low = t.toLowerCase();
    if (low === "blocked") return "Agent blockiert";
    if (low === "ready") return "Bereit";
    if (low === "fix_loop" || low === "fixloop") return "Reparatur-Schleife";
    if (low === "failed" || low === "fehlgeschlagen") return "Fehlgeschlagen";
    return t;
  };

  const deErrCategory = (s) => {
    const t = _pickFirstString(s);
    if (!t || t.toLowerCase() === "unknown") return "Unbekannter Fehler";
    const low = t.toLowerCase();
    const map = {
      unknown_error: "Unbekannter Fehler",
      error_loop: "Fehlerschleife erkannt",
      build_error: "Build-Fehler",
      lint_error: "Lint-Fehler",
      frontend_write_locked: "Frontend-Schreibschutz",
      prohibited_file: "Durch Dateischutz blockiert",
      invalid_path_placeholder: "Ungültiger Platzhalter-Pfad",
      syntax_error: "Syntaxfehler",
      import_error: "Importfehler",
      runtime_error: "Laufzeitfehler",
    };
    return map[low] || t.replace(/_/g, " ");
  };

  const deBlockReason = (b) => {
    const t = _pickFirstString(b);
    if (!t) return "Kein Block aktiv";
    const low = t.toLowerCase();
    if (low === "error_loop") return "Fehlerschleife erkannt";
    if (low.includes("prohibited") || low.includes("verbot")) return "Durch Dateischutz blockiert";
    return t.replace(/_/g, " ");
  };

  const deSubtaskStatus = (s) => {
    const t = String(s ?? "").trim();
    const low = t.toLowerCase();
    if (!t) return "offen";
    if (low === "blocked") return "blockiert";
    if (low === "ok" || low === "done") return "fertig";
    return t;
  };

  const lintTri =
    l5?.lastLintOk === true || l4?.lastLintOk === true
      ? true
      : l5?.lastLintOk === false || l4?.lastLintOk === false
        ? false
        : null;

  const buildTri =
    l5?.lastBuildOk === true || l4?.lastBuildOk === true
      ? true
      : l5?.lastBuildOk === false || l4?.lastBuildOk === false
        ? false
        : null;

  const lintLabel =
    lintTri === true ? "Lint erfolgreich" : lintTri === false ? "Lint fehlgeschlagen" : "Kein Lint ausgeführt";

  const buildLabel =
    buildTri === true
      ? "Build erfolgreich"
      : buildTri === false
        ? "Build fehlgeschlagen"
        : "Kein Build ausgeführt";

  const errMsg = _pickFirstString(
    sr.error_message,
    sr.build_error_excerpt,
    rambo.last_error_message,
    l5?.lastBuildErr,
    l4?.lastBuildErr,
    l5?.lastClassifiedError?.excerpt,
    l5?.lastClassifiedError?.hint
  );

  const errCat =
    _pickFirstString(sr.error_class_label_de) ||
    deErrCategory(_pickFirstString(sr.error_class, rambo.last_error_class, l5?.lastClassifiedError?.type));

  const blockRaw = _pickFirstString(
    sr.block_reason,
    rambo.block_reason,
    l5?.blockedReason,
    l4?.blockedReason,
    l4?.lastError
  );

  const phaseRaw =
    _pickFirstString(sr.phase, l5?.currentPhase, l4?.lastStep, rambo.last_route) || "Keine aktive Phase";
  const phase = _cleanUiText(phaseRaw);

  const taskRaw = _pickFirstString(sr.task, l5?.task, l4?.task, rambo.last_task) || "Keine aktive Aufgabe";
  const task = _cleanUiText(taskRaw);

  const agentLine = _cleanUiText(deAgentStatus(_pickFirstString(l5?.status, l4?.status, rambo.phase, sr.phase)));

  const lastAction =
    _pickFirstString(sr.last_action, rambo.last_action) || "Keine letzte Aktion gemeldet";

  const fromSrFiles =
    Array.isArray(sr.files_touched) && sr.files_touched.length
      ? sr.files_touched
          .filter(Boolean)
          .slice(-4)
          .map(String)
          .join(" · ")
      : "";

  const filesLine =
    _pickFirstString(sr.last_target_file, sr.primary_files_line, sr.error_file, rambo.last_error_file) ||
    fromSrFiles ||
    (Array.isArray(l5?.lastTouchedFiles) && l5.lastTouchedFiles.length
      ? l5.lastTouchedFiles
          .filter(Boolean)
          .slice(-4)
          .map(String)
          .join(" · ")
      : Array.isArray(l4?.lastEditedFiles) && l4.lastEditedFiles.length
        ? l4.lastEditedFiles
            .filter(Boolean)
            .slice(-4)
            .map(String)
            .join(" · ")
        : "") || "Keine betroffene Datei";

  const retryRaw = sr.retry_count ?? rambo.retry_count ?? l5?.repairIteration ?? l5?.lastReflection?.repeatCount;
  const retryNum = retryRaw != null && retryRaw !== "" ? Number(retryRaw) : 0;
  const retryLabel =
    Number.isFinite(retryNum) && retryNum > 0 ? `Wiederholungen: ${retryNum}` : "Keine Retries gemeldet";

  const rep = l5?.lastReflection && typeof l5.lastReflection === "object" ? l5.lastReflection : null;
  const reflectionLine = _pickFirstString(rep?.recommendation, rep?.progress)
    ? `${_pickFirstString(rep?.recommendation, rep?.progress)}${_pickFirstString(rep?.blockedReason) ? ` · ${rep.blockedReason}` : ""}`
    : "Keine Recovery-Empfehlung";

  const repeatAction = _pickFirstString(rambo.repeated_action, rep?.fingerprint);
  const repeatFiles =
    Array.isArray(rambo.repeated_files) && rambo.repeated_files.length
      ? rambo.repeated_files
          .filter(Boolean)
          .slice(-4)
          .map(String)
          .join(" · ")
      : "";

  let loopLine = "";
  const loopFromBackend = _pickFirstString(sr.loop_detail_de);
  if (loopFromBackend) {
    loopLine = loopFromBackend;
  } else if (repeatAction || repeatFiles) {
    const parts = [];
    if (repeatAction) parts.push(`Wiederholte Aktion: ${repeatAction}`);
    if (repeatFiles) parts.push(`Dateien: ${repeatFiles}`);
    loopLine = parts.join(" · ");
  } else if (
    ["error_loop", "import_loop", "same_error_repeated", "no_progress"].includes(String(blockRaw).toLowerCase()) ||
    String(sr.loop_reason_code || "").toLowerCase() === "error_loop"
  ) {
    loopLine = "Fehlerschleife aktiv (Details im Tooltip)";
  } else {
    loopLine = "Keine Fehlerschleife aktiv";
  }

  const isBlocked =
    String(l5?.status || "").toLowerCase() === "blocked" ||
    String(l4?.status || "").toLowerCase() === "blocked" ||
    Boolean(blockRaw);

  const subtasks = Array.isArray(l5?.subtasks) ? l5.subtasks : [];

  const errMsgDisplay =
    errMsg ||
    (buildTri === false && !_pickFirstString(l5?.lastBuildErr, l4?.lastBuildErr)
      ? "(Kein Build-Logtext - siehe Backend/CLI)"
      : "Keine Fehlermeldung");

  const errClip = _pickFirstString(sr.last_error_excerpt_short) || errMsgDisplay;
  const recommendationLine = _pickFirstString(sr.recovery_recommendation);
  const lastErrTime = _pickFirstString(sr.last_error_time);
  const lastOkTime = _pickFirstString(sr.last_success_time);
  const lastOkAction = _pickFirstString(sr.last_success_action);
  const timingParts = [];
  if (lastErrTime) timingParts.push(`Fehler: ${lastErrTime}`);
  if (lastOkTime) {
    const okPart = lastOkAction ? `${lastOkAction} · ${lastOkTime}` : lastOkTime;
    timingParts.push(`Erfolg: ${okPart}`);
  }
  const timingLine = timingParts.join(" · ");

  return {
    agentLine,
    phase,
    task,
    subtasks,
    deSubtaskStatus,
    lastAction,
    filesLine,
    lintLabel,
    buildLabel,
    errMsg: errMsgDisplay,
    errClip,
    recommendationLine,
    timingLine,
    errCat,
    blockLine: _pickFirstString(sr.block_reason_label_de) || deBlockReason(blockRaw),
    retryLabel,
    reflectionLine,
    loopLine,
    isBlocked,
    lintTri,
    buildTri,
  };
}

function isBackendReachableLabel(label) {
  const s = String(label || "").trim().toLowerCase();
  return (
    s === "verbunden" ||
    s === "online" ||
    s === "running" ||
    s === "ok" ||
    s === "healthy" ||
    s === "backend_ok"
  );
}

function App() {
  const [modelMode, setModelMode] = useState("turbo");
  const [status, setStatus] = useState({
    backend_status: BACKEND_STATUS_PENDING,
    ollama_ok: null,
    last_status_check_at: "",
    system_mode: "Lokal & Autark",
    rainer_core: "Aktiv",
    model: "Llama3",
  });
  const [autopilotActive, _setAutopilotActive] = useState(true);
  const [_builderModalOpen, setBuilderModalOpen] = useState(false);
  const [generatorModalOpen, setGeneratorModalOpen] = useState(false);
  const [designStudioOpen, setDesignStudioOpen] = useState(false);
  const [rainerAgentOpen, setRainerAgentOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      sender: "ai",
      text: "Rambo Rainer online. Gib mir einen Befehl.",
      image_url: "",
      time: new Date().toLocaleTimeString(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isConverting, setIsConverting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState("");
  const [uploadedFileMeta, setUploadedFileMeta] = useState({ name: "", type: "" });
  /** Letzte lokale Datei fuer Code-Pipeline (gleicher Name wie uploadedFileMeta nach Upload). */
  const [pendingLocalFile, setPendingLocalFile] = useState(null);
  const [imageLoading, setImageLoading] = useState({});
  const [imageFailed, setImageFailed] = useState({});
  const [imageRetries, setImageRetries] = useState({});
  const [codeActivity, setCodeActivity] = useState([]);
  const [weather, setWeather] = useState({
    city: "Idar-Oberstein",
    temperature: "--",
    status: "Lade...",
    loading: true,
  });
  const [learningStats, setLearningStats] = useState({
    solved: 0,
    successRate: "0%",
    memoryHits: 0,
  });
  const [errorCount, setErrorCount] = useState(0);
  const [facts, setFacts] = useState(() => [...INITIAL_MEMORY.facts]);
  const [problems, setProblems] = useState(() => [...INITIAL_MEMORY.problems]);
  const [project, _setProject] = useState(() => [...INITIAL_MEMORY.project]);
  const [cpuPct, setCpuPct] = useState(14);
  const [ramPct, setRamPct] = useState(26);
  const [agentL4, setAgentL4] = useState(null);
  const [agentL4Busy, setAgentL4Busy] = useState(false);
  const [agentL4Task, setAgentL4Task] = useState("");
  const [agentL4Logs, setAgentL4Logs] = useState([]);
  const [agentErrs, setAgentErrs] = useState([]);
  const [agentPats, setAgentPats] = useState([]);
  const [qualityEval, setQualityEval] = useState({
    loading: false,
    loadingKind: null,
    avgScore: null,
    totalCases: 0,
    lastRunAt: "",
    history: [],
    lastAutofix: null,
    taskGraphTop: [],
  });
  const chatRef = useRef(null);
  const prevBackendRef = useRef(null);
  const autopilotSyncedRef = useRef(false);
  /** Verhindert verzoegerte/zugeordnete AI-Antworten bei schnellen Folge-Sends (async Race). */
  const chatSendSeqRef = useRef(0);

  const addFact = useCallback((text) => {
    const t = String(text ?? "").trim();
    if (!t) return;
    setFacts((prev) => (prev.includes(t) ? prev : [...prev, t]));
  }, []);

  const addProblem = useCallback((text) => {
    const t = String(text ?? "").trim();
    if (!t) return;
    setProblems((prev) => {
      if (prev.includes(t)) return prev;
      const base = prev.filter((x) => x !== "Keine Meldungen");
      return [...base, t];
    });
  }, []);

  const removeProblem = useCallback((text) => {
    const t = String(text ?? "").trim();
    if (!t) return;
    setProblems((prev) => {
      const next = prev.filter((x) => x !== t);
      return next.length === 0 ? ["Keine Meldungen"] : next;
    });
  }, []);

  const clipText = (value, max) => {
    const s = value == null ? "" : String(value);
    if (s.length <= max) return s;
    return `${s.slice(0, max)}…`;
  };

  const fetchWeather = async () => {
    setWeather((prev) => ({ ...prev, loading: true }));
    try {
      const res = await apiFetch("/api/weather?city=Idar-Oberstein");
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await readJsonSafe(res);
      const nextTemp =
        typeof data?.temperature === "number" ? `${Math.round(data.temperature)}Â°C` : "--";
      setWeather({
        city: String(data?.city || "Idar-Oberstein"),
        temperature: nextTemp,
        status: String(data?.status || "Unbekannt"),
        loading: false,
      });
    } catch {
      setWeather((prev) => ({
        ...prev,
        status: "Wetterdaten nicht erreichbar",
        loading: false,
      }));
    }
  };

  useEffect(() => {
    fetchWeather();
    const interval = setInterval(fetchWeather, 300000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(
        MEMORY_STORAGE_KEY,
        JSON.stringify({ facts, problems, project })
      );
    } catch {
      void 0;
    }
  }, [facts, problems, project]);

  useEffect(() => {
    const solved = learningStats.solved;
    const denom = solved + errorCount;
    const successRate =
      denom === 0 ? "0%" : `${Math.round((solved / denom) * 100)}%`;
    setLearningStats((prev) =>
      prev.successRate === successRate ? prev : { ...prev, successRate }
    );
  }, [learningStats.solved, errorCount]);

  useEffect(() => {
    const cur = status.backend_status;
    const prev = prevBackendRef.current;
    if (prev !== null) {
      const curOk = isBackendReachableLabel(cur);
      const prevOk = isBackendReachableLabel(prev);
      if (!curOk && prevOk) addProblem("Backend getrennt");
      if (curOk && !prevOk) removeProblem("Backend getrennt");
    }
    prevBackendRef.current = cur;
  }, [status.backend_status, addProblem, removeProblem]);

  useEffect(() => {
    if (!chatRef.current) return;
    chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages, loading]);

  useEffect(() => {
    if (!chatRef.current) return;
    chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [imageLoading]);

  useEffect(() => {
    const fetchCodeActivity = async () => {
      try {
        const res = await apiFetch("/api/code-activity");
        const data = await readJsonSafe(res);
        setCodeActivity(Array.isArray(data?.entries) ? data.entries : []);
      } catch {
        setCodeActivity([]);
      }
    };
    fetchCodeActivity();
    const interval = setInterval(fetchCodeActivity, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await apiFetchWithRetry("/api/status", {}, { retries: 3, baseDelayMs: 400 });
        if (!res.ok) {
          setStatus((s) => ({
            ...s,
            backend_status: `HTTP ${res.status}`,
            last_status_check_at: new Date().toLocaleTimeString(),
          }));
          return;
        }
        let data;
        try {
          data = await res.json();
        } catch {
          setStatus((s) => ({
            ...s,
            backend_status: "Ungültige API-Antwort",
            last_status_check_at: new Date().toLocaleTimeString(),
          }));
          return;
        }
        const apiStRaw = String(data?.status || "").trim().toLowerCase();
        const backendOk = Boolean(data?.backend_ok);
        const live = backendOk || apiStRaw === "running" || apiStRaw === "ok" || apiStRaw === "healthy" || apiStRaw === "backend_ok";
        const backendLabel = live
          ? "Verbunden"
          : apiStRaw
            ? String(data?.status)
            : "Unbekannt";
        setStatus((s) => ({
          ...s,
          backend_status: backendLabel,
          ollama_ok: typeof data?.ollama_ok === "boolean" ? data.ollama_ok : s.ollama_ok,
          last_status_check_at: new Date().toLocaleTimeString(),
          system_mode: String(data?.system_mode || s.system_mode),
          rainer_core: String(data?.rainer_core || s.rainer_core),
          model: String(data?.model || s.model),
        }));
        if (
          !autopilotSyncedRef.current &&
          data?.autopilot &&
          typeof data.autopilot.active === "boolean"
        ) {
          autopilotSyncedRef.current = true;
          // setAutopilotActive(!!data.autopilot.active); // dauerhaft aktiv
        }
      } catch {
        setStatus((s) => ({
          ...s,
          backend_status: "Nicht erreichbar",
          last_status_check_at: new Date().toLocaleTimeString(),
        }));
      }
    };
    fetchStatus();
    const t = setInterval(fetchStatus, 10000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const t = setInterval(
      () => setCpuPct(10 + Math.floor(Math.random() * 18)),
      4000
    );
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const t = setInterval(
      () => setRamPct(Math.floor(Math.random() * 46) + 22),
      3500
    );
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await apiFetch("/api/agent/state");
        const data = await readJsonSafe(res);
        if (!cancelled && data?.ok) {
          setAgentL4(data.data);
        }
      } catch {
        if (!cancelled) {
          setAgentL4(null);
        }
      }
    };
    load();
    const interval = setInterval(load, 2800);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await apiFetch("/api/agent/logs?limit=14");
        const data = await readJsonSafe(res);
        if (!cancelled && data?.ok && Array.isArray(data.runs)) {
          setAgentL4Logs(data.runs);
        }
      } catch {
        if (!cancelled) {
          setAgentL4Logs([]);
        }
      }
    };
    load();
    const interval = setInterval(load, 5200);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [er, pa] = await Promise.all([
          apiFetch("/api/agent/errors?limit=14").then(readJsonSafe),
          apiFetch("/api/agent/patterns?limit=10").then(readJsonSafe),
        ]);
        if (!cancelled && er?.ok && Array.isArray(er.errors)) {
          setAgentErrs(er.errors);
        }
        if (!cancelled && pa?.ok && Array.isArray(pa.patterns)) {
          setAgentPats(pa.patterns);
        }
      } catch {
        if (!cancelled) {
          setAgentErrs([]);
          setAgentPats([]);
        }
      }
    };
    load();
    const interval = setInterval(load, 8000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const refreshAgentL4State = async () => {
    try {
      const res = await apiFetch("/api/agent/state");
      const data = await readJsonSafe(res);
      if (data?.ok) {
        setAgentL4(data.data);
      }
    } catch {
      /* ignore */
    }
  };

  const agentL4Post = async (path, body) => {
    setAgentL4Busy(true);
    try {
      await apiFetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      });
    } catch {
      /* ignore */
    } finally {
      setAgentL4Busy(false);
      await refreshAgentL4State();
    }
  };

  const runQualityEvalSuite = useCallback(async () => {
    setQualityEval((s) => ({ ...s, loading: true, loadingKind: "suite" }));
    try {
      const res = await apiFetch("/api/quality/eval-suite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await readJsonSafe(res);
      const [histRes, tgRes] = await Promise.all([
        apiFetch("/api/quality/eval-history?limit=5"),
        apiFetch("/api/quality/task-graph?limit=5"),
      ]);
      const hist = await readJsonSafe(histRes);
      const tg = await readJsonSafe(tgRes);
      const tgEntries = Array.isArray(tg?.entries) ? tg.entries : [];
      setQualityEval((s) => ({
        ...s,
        loading: false,
        loadingKind: null,
        avgScore: Number.isFinite(Number(data?.avg_score)) ? Number(data.avg_score) : null,
        totalCases: Number.isFinite(Number(data?.total_cases)) ? Number(data.total_cases) : 0,
        lastRunAt: new Date().toLocaleTimeString(),
        history: Array.isArray(hist?.entries) ? hist.entries : [],
        taskGraphTop: tgEntries.slice(0, 3),
      }));
    } catch {
      setQualityEval((s) => ({ ...s, loading: false, loadingKind: null }));
    }
  }, []);

  const runQualityAutofixThenEval = useCallback(async () => {
    setQualityEval((s) => ({ ...s, loading: true, loadingKind: "chain" }));
    try {
      const afRes = await apiFetch("/api/quality/autofix-run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task: "Quality gate: Checks stabilisieren, danach Eval",
          checks: ["python -m py_compile backend/main.py", "python -m pytest tests -q"],
          auto_fix: true,
          max_fix_rounds: 2,
          eval_after: true,
        }),
      });
      const afData = await readJsonSafe(afRes);
      const [histRes, tgRes] = await Promise.all([
        apiFetch("/api/quality/eval-history?limit=5"),
        apiFetch("/api/quality/task-graph?limit=5"),
      ]);
      const hist = await readJsonSafe(histRes);
      const tg = await readJsonSafe(tgRes);
      const tgEntries = Array.isArray(tg?.entries) ? tg.entries : [];
      const tgEntry = afData?.task_graph && typeof afData.task_graph === "object" ? afData.task_graph : tgEntries[0];
      const base = mapQualityGraphEntry(tgEntry || null);
      const evalScore =
        base?.evalScore ??
        (Number.isFinite(Number(afData?.eval_avg_score)) ? Number(afData.eval_avg_score) : null);
      const lastAutofix = base
        ? {
            ...base,
            evalScore: evalScore ?? base.evalScore,
            passedCount: Number.isFinite(Number(afData?.passed_count)) ? Number(afData.passed_count) : null,
            failedCount: Number.isFinite(Number(afData?.failed_count)) ? Number(afData.failed_count) : null,
            at: new Date().toLocaleTimeString(),
          }
        : null;
      const totalCases =
        Number.isFinite(Number(afData?.task_graph?.eval_total_cases))
          ? Number(afData.task_graph.eval_total_cases)
          : Number.isFinite(Number(afData?.eval_total_cases))
            ? Number(afData.eval_total_cases)
            : 0;
      setQualityEval((s) => ({
        ...s,
        loading: false,
        loadingKind: null,
        avgScore: evalScore,
        totalCases,
        lastRunAt: new Date().toLocaleTimeString(),
        history: Array.isArray(hist?.entries) ? hist.entries : [],
        lastAutofix,
        taskGraphTop: tgEntries.slice(0, 3),
      }));
    } catch {
      setQualityEval((s) => ({ ...s, loading: false, loadingKind: null }));
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [histRes, tgRes] = await Promise.all([
          apiFetch("/api/quality/eval-history?limit=5"),
          apiFetch("/api/quality/task-graph?limit=5"),
        ]);
        const hist = await readJsonSafe(histRes);
        const tg = await readJsonSafe(tgRes);
        if (!cancelled) {
          const tgEntries = Array.isArray(tg?.entries) ? tg.entries : [];
          const first = tgEntries[0] ? mapQualityGraphEntry(tgEntries[0]) : null;
          setQualityEval((s) => ({
            ...s,
            history: Array.isArray(hist?.entries) ? hist.entries : [],
            lastAutofix: first || s.lastAutofix,
            taskGraphTop: tgEntries.slice(0, 3),
          }));
        }
      } catch {
        if (!cancelled) {
          setQualityEval((s) => ({ ...s, history: [], taskGraphTop: [] }));
        }
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const qualityScoreClass = useMemo(() => {
    const s = qualityEval.avgScore;
    if (s == null) return "";
    if (s >= 80) return "dash-quality-score--high";
    if (s >= 55) return "dash-quality-score--mid";
    return "dash-quality-score--low";
  }, [qualityEval.avgScore]);

  const qualityTrend = useMemo(() => {
    const h = qualityEval.history;
    if (!Array.isArray(h) || h.length < 2) return null;
    const a = Number(h[0]?.avg_score);
    const b = Number(h[1]?.avg_score);
    if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
    const d = a - b;
    if (d > 0) return { cls: "dash-quality-trend--up", text: `↑ +${d}% vs. letzter Lauf` };
    if (d < 0) return { cls: "dash-quality-trend--down", text: `↓ ${d}% vs. letzter Lauf` };
    return { cls: "dash-quality-trend--flat", text: "→ gleich wie letzter Lauf" };
  }, [qualityEval.history]);

  const avatarStatus = useMemo(() => {
    if (!isBackendReachableLabel(status.backend_status)) return "error";
    if (isConverting) return "converting";
    if (loading) return "thinking";
    if (autopilotActive) return "searching";
    return "idle";
  }, [autopilotActive, isConverting, loading, status.backend_status]);

  const activeModelLabel = useMemo(
    () => (modelMode === "brain" ? "DeepSeek-R1 8B (Brain)" : "Llama 3.2 (Speed-Mode)"),
    [modelMode]
  );

  const extractImageUrlFromText = (text) => {
    const content = String(text || "");
    if (!content) return "";
    const match = content.match(/https?:\/\/[^\s)"]+/i);
    if (!match?.[0]) return "";
    const url = match[0];
    const isImageLike =
      /pollinations\.ai/i.test(url) ||
      /\.(png|jpg|jpeg|webp|gif)(\?.*)?$/i.test(url) ||
      /image\.pollinations\.ai/i.test(url);
    return isImageLike ? url : "";
  };

  const extractMeshUrlFromText = (text) => {
    const content = String(text || "");
    if (!content) return "";
    const match = content.match(/(?:https?:\/\/[^\s)"]+|\/api\/download\/[^\s)"]+)/i);
    if (!match?.[0]) return "";
    const url = match[0];
    const isMeshLike = /\.(obj|stl|glb|gltf|ply)(\?.*)?$/i.test(url);
    return isMeshLike ? url : "";
  };

  const appendCacheBuster = (url, cacheKey) => {
    const raw = String(url || "").trim();
    if (!raw) return "";
    const stableKey = encodeURIComponent(String(cacheKey || "base"));
    return `${raw}${raw.includes("?") ? "&" : "?"}cb=${stableKey}`;
  };

  const handleSend = async () => {
    const value = input.trim();
    if (!value) return;
    const sendSeq = ++chatSendSeqRef.current;
    const stillCurrent = () => sendSeq === chatSendSeqRef.current;

    setLoading(true);
    const conversionIntent =
      /wandle\s+.+\s+in\s+[a-zA-Z0-9.]+\s+um/i.test(value) ||
      /(?:umwandeln|konvertiere|konvertieren).*(?:pdf)/i.test(value);
    setIsConverting(conversionIntent);

    const userMsg = {
      id: `u-${Date.now()}`,
      sender: "user",
      text: value,
      image_url: "",
      time: new Date().toLocaleTimeString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    if (conversionIntent) {
      setMessages((prev) => [
        ...prev,
        {
          id: `c-${Date.now()}`,
          sender: "ai",
          text: "Verstanden. Ich konvertiere die Datei jetzt lokal für dich...",
          image_url: "",
          time: new Date().toLocaleTimeString(),
        },
      ]);
    }
    setInput("");

    try {
      // Nach /api/upload kann uploadedFileMeta.name (secure_filename) vom lokalen File.name abweichen (Windows/Sonderzeichen).
      const hasCodeContext =
        !!uploadedFileMeta?.name &&
        isCodeFilename(uploadedFileMeta.name) &&
        !!pendingLocalFile &&
        isCodeFilename(pendingLocalFile.name);

      if (hasCodeContext) {
        const codeIntent = parseCodeIntent(value);
        if (isCodeIntent(codeIntent)) {
          try {
            const fileText = await pendingLocalFile.text();
            const uploadResult = await codeService.uploadCode(uploadedFileMeta.name, fileText);
            const processResult = await codeService.processCode(
              uploadResult.file_id,
              codeIntent.action,
              value,
            );

            let responseText = "";
            let codeViewerPayload = null;

            if (codeIntent.action === "explain_code") {
              responseText = `${codeIntent.label}:\n\n${processResult.result}`;
              codeViewerPayload = {
                code: fileText,
                language: uploadResult.language,
                filename: uploadResult.filename,
              };
            } else {
              responseText = `${codeIntent.label}\n\nCode aktualisiert (v${processResult.version}).`;
              codeViewerPayload = {
                code: processResult.result,
                language: uploadResult.language,
                filename: uploadResult.filename,
              };
            }

            if (!stillCurrent()) return;
            setMessages((prev) => [
              ...prev,
              {
                id: `code-${Date.now()}`,
                sender: "ai",
                text: responseText,
                image_url: "",
                time: new Date().toLocaleTimeString(),
                action: "code_process",
                file_id: uploadResult.file_id,
                codeViewer: codeViewerPayload,
              },
            ]);
            return;
          } catch (codeErr) {
            if (!stillCurrent()) return;
            setMessages((prev) => [
              ...prev,
              {
                id: `code-err-${Date.now()}`,
                sender: "ai",
                text: formatCodePipelineErrorMessage(codeErr),
                image_url: "",
                time: new Date().toLocaleTimeString(),
              },
            ]);
            return;
          }
        }
      }

      // Text→3D-MVP vor Bild-/Mesh-Pfad: sonst matcht parse3DIntent auf "mach … 3d" und ruft meshService mit (ggf. altem) Upload auf.
      if (isTextTo3dChatPrompt(value)) {
        const resT3d = await apiFetch("/api/chat/message", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: value, context: {} }),
        });
        const msgJson = await readJsonSafe(resT3d);
        if (!stillCurrent()) return;
        if (!resT3d.ok) {
          addProblem("Chat/Backend Fehler");
          setErrorCount((c) => c + 1);
          setMessages((prev) => [
            ...prev,
            {
              id: `t3d-err-${Date.now()}`,
              sender: "ai",
              text: String(
                msgJson?.content || msgJson?.error || msgJson?.message || `Anfrage fehlgeschlagen (HTTP ${resT3d.status})`,
              ),
              image_url: "",
              time: new Date().toLocaleTimeString(),
            },
          ]);
          return;
        }
        removeProblem("Chat/Backend Fehler");
        addFact("Aufgabe verarbeitet");
        let outText = String(msgJson?.content || "").trim();
        const meshUrl = String(msgJson?.mesh_download_url || "").trim();
        if (meshUrl && !outText.includes(meshUrl)) {
          outText = outText ? `${outText}\n\n📥 Mesh: ${meshUrl}` : `📥 Mesh: ${meshUrl}`;
        }
        setMessages((prev) => [
          ...prev,
          {
            id: `t3d-${Date.now()}`,
            sender: "ai",
            text: outText || "Keine Antwort erhalten.",
            type: String(msgJson?.type || "text"),
            mesh_filename: String(msgJson?.mesh_filename || "").trim() || null,
            mesh_download_url: meshUrl || null,
            mesh_format: String(msgJson?.mesh_format || "").trim() || null,
            mesh_vertices: Number.isFinite(Number(msgJson?.mesh_vertices))
              ? Number(msgJson?.mesh_vertices)
              : null,
            mesh_faces: Number.isFinite(Number(msgJson?.mesh_faces))
              ? Number(msgJson?.mesh_faces)
              : null,
            stl_filename: String(msgJson?.stl_filename || "").trim() || null,
            stl_download_url: String(msgJson?.stl_download_url || "").trim() || null,
            glb_filename: String(msgJson?.glb_filename || "").trim() || null,
            glb_download_url: String(msgJson?.glb_download_url || "").trim() || null,
            image_url: "",
            time: new Date().toLocaleTimeString(),
          },
        ]);
        setLearningStats((prev) => ({
          ...prev,
          solved: prev.solved + 1,
          memoryHits: prev.memoryHits,
        }));
        return;
      }

      const hasUploadedImage = isUploadedImageForPipeline(uploadedFileMeta);
      if (hasUploadedImage) {
        const imageIntent = parseImageIntent(value);
        if (imageIntent.recognized) {
          try {
            const result = await imageService.processImage(uploadedFileMeta.name, imageIntent.action);
            if (!stillCurrent()) return;
            setMessages((prev) => [
              ...prev,
              {
                id: `img-${Date.now()}`,
                sender: "ai",
                text: `âœ¨ ${result.message}\n\n📥 Datei: ${result.result}${
                  result.download_url ? `\nDownload: ${result.download_url}` : ""
                }`,
                image_url: "",
                time: new Date().toLocaleTimeString(),
              },
            ]);
            return;
          } catch (imageErr) {
            if (!stillCurrent()) return;
            setMessages((prev) => [
              ...prev,
              {
                id: `img-err-${Date.now()}`,
                sender: "ai",
                text: `⚠️ Verarbeitung fehlgeschlagen: ${String(imageErr?.message || imageErr)}`,
                image_url: "",
                time: new Date().toLocaleTimeString(),
              },
            ]);
            return;
          }
        }

        const meshIntent = parse3DIntent(value);
        if (is3DIntent(meshIntent)) {
          try {
            const res3d = await apiFetch("/api/chat", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ message: value, modelMode, autopilot: autopilotActive }),
            });
            const result = await readJsonSafe(res3d);
            if (!res3d.ok || result?.success === false) {
              throw new Error(
                String(
                  result?.response ||
                    result?.message ||
                    result?.error ||
                    `Anfrage fehlgeschlagen (HTTP ${res3d.status})`,
                ),
              );
            }
            if (!stillCurrent()) return;
            const resolvedDepthPath = String(
              result?.depth_map_path || result?.depth_map_download_url || result?.download_url || "",
            ).trim();
            setMessages((prev) => [
              ...prev,
              {
                id: `mesh-${Date.now()}`,
                sender: "ai",
                text: String(result?.response || result?.message || "Keine Antwort erhalten."),
                type: String(result?.type || (resolvedDepthPath ? "depth_map" : "mesh_mvp")),
                depth_map_path: resolvedDepthPath || null,
                depth_map_download_url: String(result?.depth_map_download_url || resolvedDepthPath || "").trim() || null,
                depth_map_filename: String(result?.depth_map_filename || result?.result_file || result?.result_filename || "").trim() || null,
                mesh_filename: String(result?.mesh_filename || "").trim() || null,
                mesh_download_url: String(result?.mesh_download_url || "").trim() || null,
                mesh_format: String(result?.mesh_format || "").trim() || null,
                mesh_vertices: Number.isFinite(Number(result?.mesh_vertices))
                  ? Number(result?.mesh_vertices)
                  : null,
                mesh_faces: Number.isFinite(Number(result?.mesh_faces))
                  ? Number(result?.mesh_faces)
                  : null,
                stl_filename: String(result?.stl_filename || "").trim() || null,
                stl_download_url: String(result?.stl_download_url || "").trim() || null,
                glb_filename: String(result?.glb_filename || "").trim() || null,
                glb_download_url: String(result?.glb_download_url || "").trim() || null,
                image_url: "",
                time: new Date().toLocaleTimeString(),
              },
            ]);
            return;
          } catch (meshErr) {
            if (!stillCurrent()) return;
            setMessages((prev) => [
              ...prev,
              {
                id: `mesh-err-${Date.now()}`,
                sender: "ai",
                text: `⚠️ 3D-Verarbeitung fehlgeschlagen: ${String(meshErr?.message || meshErr)}`,
                image_url: "",
                time: new Date().toLocaleTimeString(),
              },
            ]);
            return;
          }
        }
      }

      // Text→Background-Remove ohne Upload: klare Hinweisnachricht statt generischem Chat.
      const imageIntentNoUpload = parseImageIntent(value);
      if (
        !hasUploadedImage &&
        imageIntentNoUpload.recognized &&
        imageIntentNoUpload.action === "remove_background"
      ) {
        if (!stillCurrent()) return;
        setMessages((prev) => [
          ...prev,
          {
            id: `img-hint-${Date.now()}`,
            sender: "ai",
            text: "⚠️ Hintergrund entfernen braucht ein Bild. Bitte zuerst Bild hochladen!",
            image_url: "",
            time: new Date().toLocaleTimeString(),
          },
        ]);
        return;
      }

      const genIntent = parseImageGenerationIntent(value);
      if (genIntent.recognized && genIntent.prompt) {
        const genId = `img-gen-${Date.now()}`;
        if (!stillCurrent()) return;
        setMessages((prev) => [
          ...prev,
          {
            id: genId,
            sender: "ai",
            text: "Bildgenerierung läuft…",
            image_url: "",
            imageGenStatus: "loading",
            time: new Date().toLocaleTimeString(),
          },
        ]);
        try {
          const imgRes = await imageService.generate(genIntent.prompt, "1024x1024");
          if (!stillCurrent()) return;
          const url = String(imgRes?.image_url || "").trim();
          setMessages((prev) =>
            prev.map((m) =>
              m.id === genId
                ? {
                    ...m,
                    text: `${imgRes?.provider || "Provider"} / ${imgRes?.model || "Modell"}: ${genIntent.prompt}`,
                    image_url: url,
                    imageUrl: url,
                    type: "image",
                    imageGenStatus: "ok",
                  }
                : m,
            ),
          );
          if (url) {
            setImageLoading((prev) => ({ ...prev, [genId]: true }));
            setImageFailed((prev) => ({ ...prev, [genId]: false }));
          }
        } catch (genErr) {
          if (!stillCurrent()) return;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === genId
                ? {
                    ...m,
                    text: `Bildgenerierung fehlgeschlagen: ${String(genErr?.message || genErr)}`,
                    imageGenStatus: "error",
                  }
                : m,
            ),
          );
        }
        return;
      }

      const res = await apiFetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: value, modelMode, autopilot: autopilotActive }),
      });
      const data = await readJsonSafe(res);
      const ok = res.ok && data?.success !== false;
      if (!ok) {
        if (!stillCurrent()) return;
        addProblem("Chat/Backend Fehler");
        setErrorCount((c) => c + 1);
        setMessages((prev) => [
          ...prev,
          {
            id: `e-${Date.now()}`,
            sender: "ai",
            text: String(
              data?.response ||
                data?.message ||
                data?.error ||
                `Anfrage fehlgeschlagen (HTTP ${res.status})`
            ),
            image_url: "",
            time: new Date().toLocaleTimeString(),
          },
        ]);
        return;
      }
      if (!stillCurrent()) return;
      removeProblem("Chat/Backend Fehler");
      addFact("Aufgabe verarbeitet");
      const conversionOutput = String(data?.conversion_output || "").trim();
      const responseText = String(data?.response || data?.message || "Keine Antwort erhalten.").trim();
      const renderedText = conversionOutput
        ? `${responseText}\n\nAusgabe: ${conversionOutput}`
        : responseText;
      const displayText = data?.split_patch_recovery
        ? `Automatische Patch-Recovery (Step-Engine): angewendet.\n\n${renderedText}`
        : renderedText;
      const resolvedImageUrl = String(
        data?.imageUrl || data?.image_url || extractImageUrlFromText(data?.message || data?.response)
      ).trim();
      const resolvedMeshUrl = String(data?.mesh_download_url || "").trim() || extractMeshUrlFromText(renderedText);
      const aiMessageId = `a-${Date.now()}`;

      if (!stillCurrent()) return;
      setMessages((prev) => [
        ...prev,
        {
          id: aiMessageId,
          sender: "ai",
          text: displayText,
          type: String(data?.type || (resolvedImageUrl ? "image" : "text")),
          mesh_filename: String(data?.mesh_filename || "").trim() || null,
          mesh_download_url: resolvedMeshUrl || null,
          mesh_format: String(data?.mesh_format || "").trim() || null,
          mesh_vertices: Number.isFinite(Number(data?.mesh_vertices)) ? Number(data?.mesh_vertices) : null,
          mesh_faces: Number.isFinite(Number(data?.mesh_faces)) ? Number(data?.mesh_faces) : null,
          stl_filename: String(data?.stl_filename || "").trim() || null,
          stl_download_url: String(data?.stl_download_url || "").trim() || null,
          glb_filename: String(data?.glb_filename || "").trim() || null,
          glb_download_url: String(data?.glb_download_url || "").trim() || null,
          image_url: resolvedImageUrl,
          imageUrl: resolvedImageUrl,
          time: new Date().toLocaleTimeString(),
        },
      ]);
      if (resolvedImageUrl) {
        setImageLoading((prev) => ({ ...prev, [aiMessageId]: true }));
        setImageFailed((prev) => ({ ...prev, [aiMessageId]: false }));
      }
      if (Array.isArray(data?.code_activity)) {
        setCodeActivity(data.code_activity);
      }
      setLearningStats((prev) => ({
        ...prev,
        solved: prev.solved + 1,
        memoryHits: prev.memoryHits + (resolvedImageUrl ? 1 : 0),
      }));
    } catch {
      if (sendSeq === chatSendSeqRef.current) {
        addProblem("Chat/Backend Fehler");
        setErrorCount((c) => c + 1);
        setMessages((prev) => [
          ...prev,
          {
            id: `e-${Date.now()}`,
            sender: "ai",
            text: "SIGNALVERLUST: Backend nicht erreichbar.",
            image_url: "",
            time: new Date().toLocaleTimeString(),
          },
        ]);
      }
    } finally {
      if (sendSeq === chatSendSeqRef.current) {
        setIsConverting(false);
        setLoading(false);
      }
    }
  };

  const uploadFile = async (event) => {
    const selectedFile = event?.target?.files?.[0];
    if (!selectedFile) return;

    setIsUploading(true);
    setUploadedFileName("");
    setUploadedFileMeta({ name: "", type: "" });
    setPendingLocalFile(null);
    setMessages((prev) => [
      ...prev,
      {
        id: `up-user-${Date.now()}`,
        sender: "user",
        text: `📁 Datei ausgewählt: ${selectedFile.name}`,
        image_url: "",
        time: new Date().toLocaleTimeString(),
      },
    ]);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const res = await apiFetch("/api/upload", {
        method: "POST",
        body: formData,
      });
      const data = await readJsonSafe(res);

      if (!res.ok || data.success === false) {
        const errorText = data.error || `Upload fehlgeschlagen (HTTP ${res.status})`;
        setMessages((prev) => [
          ...prev,
          {
            id: `up-err-${Date.now()}`,
            sender: "ai",
            text: `Upload fehlgeschlagen: ${errorText}`,
            image_url: "",
            time: new Date().toLocaleTimeString(),
          },
        ]);
        return;
      }

      const upName = data.filename || selectedFile.name;
      setUploadedFileName(upName);
      setUploadedFileMeta({ name: upName, type: selectedFile.type || "" });
      setPendingLocalFile(selectedFile);
      addFact(`Datei hochgeladen: ${upName}`);
      setMessages((prev) => [
        ...prev,
        {
          id: `up-ok-${Date.now()}`,
          sender: "ai",
          text: `Datei hochgeladen: ${data.path || data.filename}`,
          image_url: "",
          time: new Date().toLocaleTimeString(),
        },
        {
          id: `up-q-${Date.now()}-q`,
          sender: "ai",
          text: "Datei empfangen. Soll ich sie umwandeln oder analysieren?",
          image_url: "",
          time: new Date().toLocaleTimeString(),
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `up-net-${Date.now()}`,
          sender: "ai",
          text: `Upload fehlgeschlagen: ${String(err?.message ?? err)}`,
          image_url: "",
          time: new Date().toLocaleTimeString(),
        },
      ]);
    } finally {
      setIsUploading(false);
      if (event?.target) event.target.value = "";
    }
  };

  const agentPanel = useMemo(() => buildCodingAgentPanelView(agentL4), [agentL4]);
  const pageStatusLabel = isBackendReachableLabel(status.backend_status)
    ? "Status Bereit"
    : `Status ${status.backend_status}`;
  const backendReachable = isBackendReachableLabel(status.backend_status);
  const quickDiagLine = !backendReachable
    ? "Diagnose: Backend offline/nicht erreichbar"
    : status.ollama_ok === true
      ? "Diagnose: Backend ok, Ollama ok"
      : status.ollama_ok === false
        ? "Diagnose: Backend ok, Ollama offline"
        : "Diagnose: Backend ok, Ollama-Status unbekannt";
  const quickDiagMeta = status.last_status_check_at
    ? `Letzter Check: ${status.last_status_check_at}`
    : "Letzter Check: –";

  const topNavActive = rainerAgentOpen
    ? "rainer"
    : designStudioOpen
      ? "studio"
      : generatorModalOpen
        ? "generator"
        : null;

  return (
    <div className="dash-root" id="dash-root">
      <header className="dash-page-head">
        <div className="dash-page-head__titles">
          <h1 className="dash-page-title">KI Agent Control Center</h1>
          <p className="dash-page-sub">
            {status.system_mode} · {activeModelLabel}
          </p>
        </div>
        <div className="dash-page-head__right">
          <span
            className={`dash-head-status${
              isBackendReachableLabel(status.backend_status) ? " dash-head-status--ok" : ""
            }`}
            title={TT_HEAD_STATUS}
          >
            {pageStatusLabel}
          </span>
          <label className="dash-ap">
            <input
              type="checkbox"
              checked={autopilotActive}
              onChange={() => {}} disabled
            />
            <span>Autopilot</span>
          </label>
        </div>
      </header>
      <TopNavigation
        activeSection={topNavActive}
        showBuilderMode={false}
        onBuilderMode={() => {
          setRainerAgentOpen(false);
          setDesignStudioOpen(false);
          setGeneratorModalOpen(false);
          setBuilderModalOpen(true);
        }}
        onGeneratorUI={() => {
          setRainerAgentOpen(false);
          setDesignStudioOpen(false);
          setBuilderModalOpen(false);
          setGeneratorModalOpen(true);
        }}
        onDesignStudio={() => {
          setRainerAgentOpen(false);
          setBuilderModalOpen(false);
          setGeneratorModalOpen(false);
          setDesignStudioOpen(true);
        }}
        onRainerAgent={() => {
          setBuilderModalOpen(false);
          setGeneratorModalOpen(false);
          setDesignStudioOpen(false);
          setRainerAgentOpen(true);
        }}
      />
      <div className="dash-rambo-section">
        <div
          className="dash-panel dash-panel--rambo-mw"
          style={{ maxHeight: "min(42vh, 520px)", overflow: "auto" }}
        >
          <RamboManagementDashboard apiBase={API_BASE} adminToken={RAMBO_ADMIN_TOKEN} refreshIntervalMs={30000} />
        </div>
      </div>
      <div className="dash-page-grid">
      <aside className="dash-col dash-col--left">
        <div className="dash-panel">
          <h3 className="dash-panel__title">Status</h3>
          <div className="dash-kv">
            <span className="dash-kv__k">Backend</span>
            <span className="dash-kv__v" title={TT_PANEL_BACKEND}>
              {status.backend_status}
            </span>
          </div>
          <p className="dash-hint" title={TT_PANEL_BACKEND}>{STATUS_SOURCE_NOTE}</p>
          <div className="dash-kv">
            <span className="dash-kv__k">System</span>
            <span className="dash-kv__v">{status.system_mode}</span>
          </div>
          <div className="dash-kv">
            <span className="dash-kv__k">Rainer-Core</span>
            <span className="dash-kv__v dash-kv__v--cyan">{status.rainer_core}</span>
          </div>
          <p className="dash-hint">{quickDiagLine}</p>
          <p className="dash-hint">{quickDiagMeta}</p>
          <div className="dash-mode">
            <button
              type="button"
              className={`dash-mode__btn ${modelMode === "turbo" ? "dash-mode__btn--on" : ""}`}
              onClick={() => setModelMode("turbo")}
            >
              Turbo
            </button>
            <button
              type="button"
              className={`dash-mode__btn ${modelMode === "brain" ? "dash-mode__btn--on" : ""}`}
              onClick={() => setModelMode("brain")}
            >
              Brain
            </button>
          </div>
          <p className="dash-hint">{activeModelLabel}</p>
        </div>

        <div className="dash-panel">
          <h3 className="dash-panel__title">Wetter · Idar-Oberstein</h3>
          <div className="dash-kv">
            <span className="dash-kv__k">Ort</span>
            <span className="dash-kv__v dash-kv__v--cyan">{weather.city}</span>
          </div>
          <div className="dash-kv">
            <span className="dash-kv__k">Temp</span>
            <span className="dash-kv__v">{weather.temperature}</span>
          </div>
          <div className="dash-kv">
            <span className="dash-kv__k">Status</span>
            <span className="dash-kv__v">{weather.status}</span>
          </div>
          <button
            type="button"
            className="dash-btn dash-btn--block"
            onClick={fetchWeather}
            disabled={weather.loading}
          >
            {weather.loading ? "…" : "Aktualisieren"}
          </button>
        </div>

        <div className="dash-panel">
          <h3 className="dash-panel__title">Ressourcen</h3>
          <div className="dash-res">
            <div className="dash-res__row">
              <span>CPU</span>
              <span className="dash-res__pct">{cpuPct}%</span>
            </div>
            <div className="dash-bar">
              <div className="dash-bar__fill dash-bar__fill--cyan" style={{ width: `${cpuPct}%` }} />
            </div>
          </div>
          <div className="dash-res">
            <div className="dash-res__row">
              <span>RAM</span>
              <span className="dash-res__pct">4.2 / 16 GB</span>
            </div>
            <div className="dash-bar">
              <div className="dash-bar__fill dash-bar__fill--pink" style={{ width: `${ramPct}%` }} />
            </div>
          </div>
        </div>
      </aside>

      <main className="dash-col dash-col--center">
        <div className="dash-main-stage">
          <div className="dash-terminal dash-terminal--main">
            <div className="dash-terminal__sonar-layer" aria-hidden="true">
              <div className={`dash-sonar dash-sonar--embed dash-sonar--${avatarStatus}`}>
                <div className="dash-sonar__rings">
                  <span className="dash-sonar__ring" />
                  <span className="dash-sonar__ring" />
                  <span className="dash-sonar__ring" />
                </div>
                <div className="dash-sonar__hub" />
                <div className="dash-sonar__sweep" />
              </div>
            </div>
            <div className="dash-terminal__stack">
              <div className="dash-terminal__bar">
                <span className="dash-terminal__dot dash-terminal__dot--r" />
                <span className="dash-terminal__dot dash-terminal__dot--y" />
                <span className="dash-terminal__dot dash-terminal__dot--g" />
                <span className="dash-terminal__label">CHAT</span>
                {isUploading && <span className="dash-badge">UPLOAD</span>}
                {!isUploading && uploadedFileName && (
                  <span className="dash-badge dash-badge--ok">READY</span>
                )}
                {!isBackendReachableLabel(status.backend_status) &&
                  status.backend_status !== BACKEND_STATUS_PENDING && (
                  <span className="dash-badge dash-badge--warn" style={{ display: "none" }}>OFFLINE</span>
                )}
              </div>
              <div className="dash-terminal__body dash-chat-body" ref={chatRef}>
                <div className="dash-chat-messages">
                  {(Array.isArray(messages) ? messages : [])
                    .filter((msg) => msg && typeof msg === "object" && msg.id != null)
                    .map((msg) => {
                      const t = String(msg.text || "");
                      const finalImageUrl =
                        String(msg.imageUrl || msg.image_url || "").trim() ||
                        (t.match(/(https?:\/\/image\.pollinations\.ai[^\s]+)/g)?.[0] || "") ||
                        extractImageUrlFromText(t);
                      const normalizedType = String(msg.type || "").toLowerCase();
                      const meshUrl = String(msg.mesh_download_url || "").trim() || extractMeshUrlFromText(t);
                      const isMeshType =
                        normalizedType === "mesh_mvp" || normalizedType === "text_to_3d_mvp";
                      const hasMeshCardData = Boolean(
                        meshUrl ||
                          msg.mesh_filename ||
                          msg.mesh_format ||
                          msg.mesh_vertices != null ||
                          msg.mesh_faces != null ||
                          msg.stl_download_url ||
                          msg.glb_download_url
                      );
                      const shouldRenderImage =
                        normalizedType === "image" || (!normalizedType && Boolean(finalImageUrl));
                      const retryCount = imageRetries[msg.id] || 0;
                      const imageSrc = finalImageUrl
                        ? appendCacheBuster(finalImageUrl, `${msg.id}-${retryCount}`)
                        : "";
                      const proxyImageSrc = imageSrc
                        ? apiUrl(`/api/proxy-image?url=${encodeURIComponent(imageSrc)}`)
                        : "";
                      const isImageStillLoading =
                        shouldRenderImage && imageLoading[msg.id] !== false;
                      const isImageFailed = shouldRenderImage && imageFailed[msg.id] === true;
                      const isUser = msg.sender === "user";
                      const whoLabel = isUser ? "USER" : "AI";

                      return (
                        <div
                          key={msg.id}
                          className={`dash-msg ${isUser ? "dash-msg--user" : "dash-msg--ai"}`}
                        >
                          <div className="dash-msg__bubble">
                            <div className="dash-msg__meta">
                              <span className="dash-msg__who">{whoLabel}</span>
                              <span className="dash-msg__time">{msg.time}</span>
                              <button
                                type="button"
                                className="dash-btn dash-btn--sm"
                                style={{ marginLeft: "auto", padding: "2px 8px" }}
                                onClick={async () => {
                                  const textToCopy = String(msg.text || "").trim();
                                  if (!textToCopy) return;
                                  try {
                                    await navigator.clipboard.writeText(textToCopy);
                                  } catch (_e) {
                                    // no-op: copy fallback intentionally silent
                                  }
                                }}
                              >
                                Copy
                              </button>
                            </div>
                            {msg.text ? (
                              <div className="dash-msg__text">{msg.text}</div>
                            ) : null}
                            {isMeshType && hasMeshCardData ? (
                              (meshUrl || msg.glb_download_url) ? (
                                <MeshPreview
                                  meshUrl={meshUrl}
                                  meshFilename={msg.mesh_filename}
                                  meshFormat={msg.mesh_format}
                                  meshVertices={msg.mesh_vertices}
                                  meshFaces={msg.mesh_faces}
                                  stlUrl={msg.stl_download_url}
                                  stlFilename={msg.stl_filename}
                                  glbUrl={msg.glb_download_url}
                                  glbFilename={msg.glb_filename}
                                />
                              ) : (
                                <div className="dash-msg__text">
                                  ⚠️ Mesh wurde erkannt, aber es gibt aktuell keinen Download-Link.
                                </div>
                              )
                            ) : null}
                            {msg.codeViewer && typeof msg.codeViewer.code === "string" ? (
                              <div className="dash-msg__code">
                                <CodeViewer
                                  code={msg.codeViewer.code}
                                  language={msg.codeViewer.language}
                                  filename={msg.codeViewer.filename}
                                />
                                {msg.file_id ? (
                                  <button
                                    type="button"
                                    className="dash-btn dash-btn--sm"
                                    onClick={async () => {
                                      try {
                                        const blob = await codeService.downloadCode(msg.file_id);
                                        const url = URL.createObjectURL(blob);
                                        const a = document.createElement("a");
                                        a.href = url;
                                        a.download = String(msg.codeViewer.filename || "code.txt");
                                        a.click();
                                        URL.revokeObjectURL(url);
                                      } catch (e) {
                                        console.error(e);
                                      }
                                    }}
                                  >
                                    Datei herunterladen
                                  </button>
                                ) : null}
                              </div>
                            ) : null}
                            {shouldRenderImage ? (
                              <div className="dash-msg__media">
                                {isImageStillLoading && !isImageFailed ? (
                                  <span className="dash-msg__media-wait" aria-hidden="true" />
                                ) : null}
                                {isImageFailed ? (
                                  <button
                                    type="button"
                                    className="dash-btn dash-btn--sm dash-msg__retry"
                                    onClick={() => {
                                      setImageFailed((prev) => ({ ...prev, [msg.id]: false }));
                                      setImageLoading((prev) => ({ ...prev, [msg.id]: true }));
                                      setImageRetries((prev) => ({
                                        ...prev,
                                        [msg.id]: (prev[msg.id] || 0) + 1,
                                      }));
                                    }}
                                  >
                                    Retry
                                  </button>
                                ) : null}
                                {proxyImageSrc && !isImageFailed ? (
                                  <img
                                    src={proxyImageSrc}
                                    crossOrigin="anonymous"
                                    referrerPolicy="no-referrer"
                                    alt=""
                                    className="dash-img dash-msg__img"
                                    onLoad={() => {
                                      setImageLoading((prev) => ({ ...prev, [msg.id]: false }));
                                      setImageFailed((prev) => ({ ...prev, [msg.id]: false }));
                                    }}
                                    onError={() => {
                                      setImageLoading((prev) => ({ ...prev, [msg.id]: false }));
                                      setImageFailed((prev) => ({ ...prev, [msg.id]: true }));
                                    }}
                                  />
                                ) : null}
                              </div>
                            ) : null}
                          </div>
                        </div>
                      );
                    })}
                  {loading ? (
                    <div className="dash-msg dash-msg--ai dash-msg--pending">
                      <div className="dash-msg__bubble dash-msg__bubble--pending">
                        <div className="dash-msg__meta">
                          <span className="dash-msg__who">AI</span>
                          <span className="dash-msg__time">…</span>
                        </div>
                        <div className="dash-msg__typing" aria-hidden="true">
                          <span className="dash-msg__typing-dot" />
                          <span className="dash-msg__typing-dot" />
                          <span className="dash-msg__typing-dot" />
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
              <div className="dash-chat-composer">
                <input
                  id="file-upload"
                  type="file"
                  className="dash-file"
                  onChange={uploadFile}
                />
                <label htmlFor="file-upload" className="dash-chat-composer__upload">
                  +
                </label>
                <input
                  className="dash-chat-composer__input"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !loading) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  placeholder=""
                  autoComplete="off"
                  disabled={loading}
                />
                <button
                  type="button"
                  className="dash-btn dash-chat-composer__send"
                  onClick={handleSend}
                  disabled={loading}
                >
                  Senden
                </button>
                <button
                  type="button"
                  className="dash-btn dash-btn--pink dash-chat-composer__extra"
                  onClick={() => setInput("Generiere ein Weltraum-Bild")}
                >
                  SPACE
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>

      <aside className="dash-col dash-col--right">
        <div className="dash-panel">
          <h3 className="dash-panel__title">Level 5 · Coding-Agent</h3>
          <div className="dash-kv">
            <span className="dash-kv__k">Agent</span>
            <span
              className={`dash-kv__v ${agentPanel.isBlocked ? "dash-kv__v--pink" : "dash-kv__v--cyan"}`}
            >
              {agentPanel.agentLine}
            </span>
          </div>
          <div className="dash-kv">
            <span className="dash-kv__k">Phase</span>
            <span className="dash-kv__v">{agentPanel.phase}</span>
          </div>
          <div className="dash-kv">
            <span className="dash-kv__k">Aufgabe</span>
            <span className="dash-kv__v" title={agentPanel.task}>
              {clipText(agentPanel.task, 48)}
            </span>
          </div>
          <div className="dash-kv dash-kv--stack">
            <span className="dash-kv__k">Unteraufgaben</span>
            <div className="dash-l4-runs dash-l4-runs--tight">
              {agentPanel.subtasks.length > 0 ? (
                agentPanel.subtasks.map((s) => (
                  <div key={String(s.id)} className="dash-code__line">
                    {String(s.id)} · {agentPanel.deSubtaskStatus(s.status)}
                    {s.stepCount != null ? ` · ${s.stepCount} Schritte` : ""}
                  </div>
                ))
              ) : (
                <div className="dash-code__line">Keine Unteraufgaben</div>
              )}
            </div>
          </div>
          <div className="dash-kv">
            <span className="dash-kv__k">Letzte Aktion</span>
            <span className="dash-kv__v dash-l4-mono" title={agentPanel.lastAction}>
              {clipText(agentPanel.lastAction, 56)}
            </span>
          </div>
          <div className="dash-kv">
            <span className="dash-kv__k">Lint</span>
            <span
              className={`dash-kv__v${
                agentPanel.lintTri === false ? " dash-kv__v--pink" : ""
              }${agentPanel.lintTri === true ? " dash-kv__v--cyan" : ""}`}
            >
              {agentPanel.lintLabel}
            </span>
          </div>
          <div className="dash-kv">
            <span className="dash-kv__k">Build</span>
            <span
              className={`dash-kv__v${
                agentPanel.buildTri === false ? " dash-kv__v--pink" : ""
              }${agentPanel.buildTri === true ? " dash-kv__v--cyan" : ""}`}
            >
              {agentPanel.buildLabel}
            </span>
          </div>
          <div className="dash-kv dash-kv--stack">
            <span className="dash-kv__k">Fehlermeldung</span>
            <span className="dash-kv__v dash-l4-mono" title={agentPanel.errMsg}>
              {clipText(agentPanel.errClip, 160)}
            </span>
          </div>
          {agentPanel.recommendationLine ? (
            <div className="dash-kv dash-kv--stack">
              <span className="dash-kv__k">Nächster Schritt</span>
              <span className="dash-kv__v dash-l4-mono" title={agentPanel.recommendationLine}>
                {clipText(agentPanel.recommendationLine, 140)}
              </span>
            </div>
          ) : null}
          {agentPanel.timingLine ? (
            <div className="dash-kv dash-kv--stack">
              <span className="dash-kv__k">Zeitstempel</span>
              <span className="dash-kv__v dash-l4-mono" title={agentPanel.timingLine}>
                {clipText(agentPanel.timingLine, 140)}
              </span>
            </div>
          ) : null}
          <div className="dash-kv">
            <span className="dash-kv__k">Fehlerart</span>
            <span className="dash-kv__v dash-kv__v--cyan" title={agentPanel.errCat}>
              {clipText(agentPanel.errCat, 36)}
            </span>
          </div>
          <div className="dash-kv dash-kv--stack">
            <span className="dash-kv__k">Recovery</span>
            <span className="dash-kv__v dash-l4-mono" title={agentPanel.reflectionLine}>
              {clipText(agentPanel.reflectionLine, 120)}
            </span>
          </div>
          <div className="dash-kv">
            <span className="dash-kv__k">Blockgrund</span>
            <span
              className={`dash-kv__v${agentPanel.isBlocked ? " dash-kv__v--pink" : ""}`}
              title={agentPanel.blockLine}
            >
              {clipText(agentPanel.blockLine, 64)}
            </span>
          </div>
          <div className="dash-kv">
            <span className="dash-kv__k">Retries</span>
            <span className="dash-kv__v">{agentPanel.retryLabel}</span>
          </div>
          <div className="dash-kv dash-kv--stack">
            <span className="dash-kv__k">Fehlerschleife</span>
            <span className="dash-kv__v dash-l4-mono" title={agentPanel.loopLine}>
              {clipText(agentPanel.loopLine, 120)}
            </span>
          </div>
          <div className="dash-kv dash-kv--stack">
            <span className="dash-kv__k">Datei / Scope</span>
            <span className="dash-kv__v dash-l4-mono" title={agentPanel.filesLine}>
              {clipText(agentPanel.filesLine, 120)}
            </span>
          </div>
          <div className="dash-sub dash-l4-runs-h">Patterns</div>
          <div className="dash-code dash-l4-runs dash-l4-runs--short">
            {agentPats.length === 0 && <div className="dash-code__line">Keine Patterns</div>}
            {agentPats
              .filter((p) => p != null && typeof p === "object")
              .slice(-5)
              .map((p, idx) => (
                <div key={`pat-${idx}-${String(p.kind ?? "")}`} className="dash-code__line">
                  {clipText(`${String(p.kind ?? "unbekannt")}`, 40)}
                </div>
              ))}
          </div>
          <div className="dash-sub dash-l4-runs-h">Fehlerhistorie</div>
          <div className="dash-code dash-l4-runs dash-l4-runs--short">
            {agentErrs.length === 0 && <div className="dash-code__line">Keine Fehlerhistorie</div>}
            {agentErrs
              .filter((e) => e != null && typeof e === "object")
              .slice(-5)
              .map((e, idx) => (
                <div key={`err-${idx}-${String(e.type ?? e.error_class ?? "")}`} className="dash-code__line">
                  {clipText(
                    [e.error_class || e.type, e.message].filter(Boolean).join(" · ") || "Eintrag",
                    48
                  )}
                </div>
              ))}
          </div>
          <input
            className="dash-l4-task"
            value={agentL4Task}
            onChange={(e) => setAgentL4Task(e.target.value)}
            placeholder=""
            disabled={agentL4Busy}
            autoComplete="off"
          />
          <div className="dash-l4-actions">
            <button
              type="button"
              className="dash-btn dash-btn--sm"
              disabled={agentL4Busy}
              onClick={() => {
                const t = agentL4Task.trim();
                if (t) {
                  agentL4Post("/api/agent/task", { task: t });
                }
              }}
            >
              Task
            </button>
            <button
              type="button"
              className="dash-btn dash-btn--sm"
              disabled={agentL4Busy}
              onClick={() => agentL4Post("/api/agent/scan", {})}
            >
              Scan
            </button>
            <button
              type="button"
              className="dash-btn dash-btn--sm"
              disabled={agentL4Busy}
              onClick={() => agentL4Post("/api/agent/run-build", {})}
            >
              Build
            </button>
            <button
              type="button"
              className="dash-btn dash-btn--sm dash-btn--pink"
              disabled={agentL4Busy}
              onClick={() => agentL4Post("/api/agent/fix", { max: 3 })}
            >
              Fix
            </button>
            <button
              type="button"
              className="dash-btn dash-btn--sm"
              disabled={agentL4Busy}
              onClick={() => {
                const t = agentL4Task.trim();
                if (t) {
                  agentL4Post("/api/agent/plan", { task: t });
                }
              }}
            >
              Plan
            </button>
            <button
              type="button"
              className="dash-btn dash-btn--sm"
              disabled={agentL4Busy}
              onClick={() => agentL4Post("/api/agent/run-lint", {})}
            >
              Lint
            </button>
            <button
              type="button"
              className="dash-btn dash-btn--sm"
              disabled={agentL4Busy}
              onClick={() => agentL4Post("/api/agent/reflection", {})}
            >
              Refl
            </button>
          </div>
          <div className="dash-sub dash-l4-runs-h">Runs</div>
          <div className="dash-code dash-l4-runs">
            {agentL4Logs.length === 0 && <div className="dash-code__line">—</div>}
            {agentL4Logs
              .filter((e) => e != null && typeof e === "object")
              .slice(-8)
              .map((entry, idx) => (
                <div
                  key={`l4-${String(entry.at ?? entry.runId ?? "r")}-${idx}`}
                  className="dash-code__line"
                >
                  {clipText(
                    `${String(entry.phase ?? "—")} ${entry.ok === false ? "✗" : entry.ok === true ? "✓" : ""}`.trim(),
                    36
                  )}
                </div>
              ))}
          </div>
        </div>

        <div className="dash-panel">
          <h3 className="dash-panel__title">Stats</h3>
          <div className="dash-kv">
            <span className="dash-kv__k">Gelöst</span>
            <span className="dash-kv__v dash-kv__v--cyan">{learningStats.solved}</span>
          </div>
          <div className="dash-kv">
            <span className="dash-kv__k">Erfolg</span>
            <span className="dash-kv__v dash-kv__v--pink">{learningStats.successRate}</span>
          </div>
          <div className="dash-kv">
            <span className="dash-kv__k">Memory</span>
            <span className="dash-kv__v">{learningStats.memoryHits}</span>
          </div>
        </div>

        <div className="dash-panel">
          <h3 className="dash-panel__title">Quality Eval</h3>
          <div className="dash-kv">
            <span className="dash-kv__k">Score</span>
            <span className={`dash-kv__v ${qualityScoreClass}`.trim()}>
              {qualityEval.avgScore != null ? `${qualityEval.avgScore}%` : "—"}
            </span>
          </div>
          {qualityTrend ? (
            <div className="dash-kv">
              <span className="dash-kv__k">Trend</span>
              <span className={`dash-kv__v ${qualityTrend.cls}`.trim()}>{qualityTrend.text}</span>
            </div>
          ) : null}
          {qualityEval.lastAutofix ? (
            <div className="dash-kv">
              <span className="dash-kv__k">Auto-Fix</span>
              <span
                className={`dash-kv__v ${qualityEval.lastAutofix.statusOk ? "dash-quality-score--high" : "dash-quality-score--low"}`.trim()}
                title={
                  [
                    qualityEval.lastAutofix.taskLabel ? `Task: ${qualityEval.lastAutofix.taskLabel}` : null,
                    qualityEval.lastAutofix.checksCount
                      ? `${qualityEval.lastAutofix.checksCount} Check(s), Auto-Fix ${qualityEval.lastAutofix.autoFixOn ? "an" : "aus"}`
                      : null,
                    "Letzter Lauf inkl. optional Re-Eval",
                  ]
                    .filter(Boolean)
                    .join("\n") || undefined
                }
              >
                {qualityEval.lastAutofix.statusLabel}
                {qualityEval.lastAutofix.checkScore != null
                  ? ` · ${qualityEval.lastAutofix.checkScore}% Checks`
                  : " · —"}
                {` · Fehler ${qualityEval.lastAutofix.initialFailed}→${qualityEval.lastAutofix.finalFailed}`}
                {` · ${qualityEval.lastAutofix.fixRounds} Fix-Rd`}
                {qualityEval.lastAutofix.evalScore != null
                  ? ` · Eval ${qualityEval.lastAutofix.evalScore}%`
                  : ""}
                {qualityEval.lastAutofix.taskLabel ? ` · ${qualityEval.lastAutofix.taskLabel}` : ""}
                {qualityEval.lastAutofix.at ? ` @ ${qualityEval.lastAutofix.at}` : ""}
              </span>
            </div>
          ) : null}
          <div className="dash-kv">
            <span className="dash-kv__k">Cases</span>
            <span className="dash-kv__v">{qualityEval.totalCases || "—"}</span>
          </div>
          <div className="dash-kv">
            <span className="dash-kv__k">Last Run</span>
            <span className="dash-kv__v">{qualityEval.lastRunAt || "—"}</span>
          </div>
          <button
            type="button"
            className="dash-btn dash-btn--block"
            onClick={runQualityEvalSuite}
            disabled={qualityEval.loading}
          >
            {qualityEval.loading && qualityEval.loadingKind === "suite"
              ? "Suite läuft…"
              : "Suite ausführen"}
          </button>
          <button
            type="button"
            className="dash-btn dash-btn--block dash-btn--pink"
            style={{ marginTop: 8 }}
            onClick={runQualityAutofixThenEval}
            disabled={qualityEval.loading}
          >
            {qualityEval.loading && qualityEval.loadingKind === "chain"
              ? "Auto-Fix + Re-Eval…"
              : "Auto-Fix + Re-Eval"}
          </button>
          <div className="dash-sub">Eval-Historie</div>
          <div className="dash-code dash-l4-runs dash-l4-runs--short">
            {qualityEval.history.length === 0 && <div className="dash-code__line">—</div>}
            {qualityEval.history.slice(0, 5).map((h, idx) => (
              <div key={`qe-${idx}-${String(h?.timestamp || "")}`} className="dash-code__line">
                {String(h?.timestamp || "—")} · Score {Number(h?.avg_score ?? 0)}%
              </div>
            ))}
          </div>
          <div className="dash-sub">Auto-Fix Verlauf</div>
          <div className="dash-code dash-l4-runs dash-l4-runs--short">
            {qualityEval.taskGraphTop.length === 0 && <div className="dash-code__line">—</div>}
            {qualityEval.taskGraphTop.map((row, idx) => {
              const g = mapQualityGraphEntry(row);
              const fullTask = String(row?.task || "").trim();
              return (
                <div
                  key={`tg-${idx}-${String(row?.timestamp || "")}`}
                  className="dash-code__line"
                  title={fullTask || undefined}
                >
                  {g
                    ? `${String(row?.timestamp || "—")} · ${g.statusLabel} · ${g.checkScore ?? "?"}% · ${g.initialFailed}→${g.finalFailed} · ${g.fixRounds} Rd${g.evalScore != null ? ` · Eval ${g.evalScore}%` : ""}${g.taskLabel ? ` · ${g.taskLabel}` : ""}`
                    : "—"}
                </div>
              );
            })}
          </div>
        </div>

        <div className="dash-panel">
          <h3 className="dash-panel__title">Issues</h3>
          {(Array.isArray(problems) ? problems : []).map((item) => (
            <div key={`p-${String(item)}`} className="dash-issue">
              <span className="dash-issue__tag">!</span>
              <span>{item}</span>
            </div>
          ))}
        </div>

        <div className="dash-panel dash-panel--grow">
          <h3 className="dash-panel__title">Projektstruktur</h3>
          {(Array.isArray(project) ? project : []).map((item) => (
            <div key={`s-${String(item)}`} className="dash-tree">
              {item}
            </div>
          ))}
          <div className="dash-sub">Facts</div>
          {(Array.isArray(facts) ? facts : []).map((item) => (
            <div key={`f-${String(item)}`} className="dash-tree dash-tree--sub">
              {item}
            </div>
          ))}
          <div className="dash-sub">Host</div>
          <div className="dash-code">
            {codeActivity.length === 0 && <div className="dash-code__line">—</div>}
            {codeActivity
              .filter((e) => e != null && typeof e === "object")
              .slice(-6)
              .map((entry, idx) => (
                <div
                  key={`${String(entry.time ?? "t")}-${idx}-${String(entry.action ?? "")}`}
                  className="dash-code__line"
                >
                  [{String(entry.time ?? "—")}] {String(entry.action ?? "—")} |{" "}
                  {String(entry.status ?? "—")}
                </div>
              ))}
          </div>
        </div>
      </aside>
      </div>
      <AdminDashboardWrapper apiBase={API_BASE} />
      {designStudioOpen ? (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 11000,
            background: "rgba(15, 18, 28, 0.45)",
          }}
        >
          <DesignStudio onClose={() => setDesignStudioOpen(false)} />
        </div>
      ) : null}
      {rainerAgentOpen ? (
        <RainerAgent apiBase={API_BASE} adminToken={RAMBO_ADMIN_TOKEN} onClose={() => setRainerAgentOpen(false)} />
      ) : null}
    </div>
  );
}

export default App;


