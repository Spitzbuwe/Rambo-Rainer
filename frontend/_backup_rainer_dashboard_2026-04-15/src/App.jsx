import React, { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import AgentAvatar from "./components/AgentAvatar";

const API_BASE = "http://127.0.0.1:5001";

const INTEGRATIONS = [
  "Web-Suche",
  "Wikipedia-Lookup",
  "Screenshot",
  "Datei-Konvertierung",
  "Python-Ausführung",
  "Bildgenerierung (Flux)",
  "UNIV-CONVERTER v1.0 [ONLINE]",
];

function App() {
  const [modelMode, setModelMode] = useState("turbo");
  const [status, setStatus] = useState({
    backend_status: "Verbinde...",
    system_mode: "Lokal & Autark",
    rainer_core: "Aktiv",
    model: "Llama3",
  });
  const [autopilotActive, setAutopilotActive] = useState(false);
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
  const [memoryData] = useState({
    facts: ["System lokal aufgesetzt", "Ollama aktiv", "Pollinations aktiv"],
    problems: ["Keine Meldungen"],
    project: ["backend/server.py", "src/App.jsx", "src/App.css"],
  });
  const chatRef = useRef(null);

  const fetchWeather = async () => {
    setWeather((prev) => ({ ...prev, loading: true }));
    try {
      const res = await fetch(`${API_BASE}/api/weather?city=Idar-Oberstein`);
      const data = await res.json();
      const nextTemp =
        typeof data?.temperature === "number" ? `${Math.round(data.temperature)}°C` : "--";
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
    if (!chatRef.current) return;
    chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages, loading]);

  useEffect(() => {
    const fetchCodeActivity = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/code-activity`);
        const data = await res.json();
        setCodeActivity(Array.isArray(data?.entries) ? data.entries : []);
      } catch {
        // optional telemetry
      }
    };
    fetchCodeActivity();
    const interval = setInterval(fetchCodeActivity, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/status`);
        if (!res.ok) {
          setStatus((s) => ({ ...s, backend_status: `HTTP ${res.status}` }));
          return;
        }
        const data = await res.json();
        setStatus((s) => ({
          ...s,
          backend_status: String(data?.backend_status || "Verbunden"),
          system_mode: String(data?.system_mode || s.system_mode),
          rainer_core: String(data?.rainer_core || s.rainer_core),
          model: String(data?.model || s.model),
        }));
      } catch {
        setStatus((s) => ({ ...s, backend_status: "Getrennt" }));
      }
    };
    fetchStatus();
    const t = setInterval(fetchStatus, 10000);
    return () => clearInterval(t);
  }, []);

  const avatarStatus = useMemo(() => {
    if (status.backend_status !== "Verbunden") return "error";
    if (isConverting) return "converting";
    if (loading) return "thinking";
    if (autopilotActive) return "searching";
    return "idle";
  }, [autopilotActive, isConverting, loading, status.backend_status]);

  const activeModelLabel = useMemo(
    () => (modelMode === "brain" ? "DeepSeek-R1 8B (Brain)" : "Llama 3.2 (Speed-Mode)"),
    [modelMode]
  );

  const WeatherWidget = () => (
    <div className="rr-panel">
      <h3>Wetter</h3>
      <p>
        Ort: <span>{weather.city}</span>
      </p>
      <p>
        Temp: <span>{weather.temperature}</span>
      </p>
      <p>
        Status: <span>{weather.status}</span>
      </p>
      <button
        type="button"
        className="rr-weather-btn"
        onClick={fetchWeather}
        disabled={weather.loading}
      >
        {weather.loading ? "Sync..." : "Aktualisieren"}
      </button>
    </div>
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

  const appendCacheBuster = (url, cacheKey) => {
    const raw = String(url || "").trim();
    if (!raw) return "";
    const stableKey = encodeURIComponent(String(cacheKey || "base"));
    return `${raw}${raw.includes("?") ? "&" : "?"}cb=${stableKey}`;
  };

  const handleSend = async () => {
    const value = input.trim();
    if (!value) return;
    setLoading(true);
    const conversionIntent =
      /wandle\s+.+\s+in\s+[a-zA-Z0-9\.]+\s+um/i.test(value) ||
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
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: value, modelMode, autopilot: autopilotActive }),
      });
      const data = await res.json();
      const conversionOutput = String(data?.conversion_output || "").trim();
      const responseText = String(data?.response || data?.message || "Keine Antwort erhalten.").trim();
      const renderedText = conversionOutput
        ? `${responseText}\n\nAusgabe: ${conversionOutput}`
        : responseText;
      const resolvedImageUrl = String(
        data?.imageUrl || data?.image_url || extractImageUrlFromText(data?.message || data?.response)
      ).trim();
      const aiMessageId = `a-${Date.now()}`;

      setMessages((prev) => [
        ...prev,
        {
          id: aiMessageId,
          sender: "ai",
          text: renderedText,
          type: String(data?.type || (resolvedImageUrl ? "image" : "text")),
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
        solved: prev.solved + 1,
        successRate: "100%",
        memoryHits: prev.memoryHits + (resolvedImageUrl ? 1 : 0),
      }));
    } catch {
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
    } finally {
      setIsConverting(false);
      setLoading(false);
    }
  };

  const uploadFile = async (event) => {
    const selectedFile = event?.target?.files?.[0];
    if (!selectedFile) return;

    setIsUploading(true);
    setUploadedFileName("");
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

      const res = await fetch(`${API_BASE}/api/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json().catch(() => ({}));

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

      setUploadedFileName(data.filename || selectedFile.name);
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
          text: `Upload fehlgeschlagen: ${err.message}`,
          image_url: "",
          time: new Date().toLocaleTimeString(),
        },
      ]);
    } finally {
      setIsUploading(false);
      if (event?.target) event.target.value = "";
    }
  };

  return (
    <div className="rr-dashboard">
      <aside className="rr-sidebar-left">
        <div className="rr-panel">
          <h3>Status</h3>
          <p>
            Backend: <span>{status.backend_status}</span>
          </p>
          <p>
            System: <span>{status.system_mode}</span>
          </p>
          <p>
            Rainer-Core: <span>{status.rainer_core}</span>
          </p>
        </div>

        <div className="rr-panel">
          <h3>Modell</h3>
          <div className="rr-mode-switch">
            <button
              type="button"
              className={`rr-mode-btn turbo ${modelMode === "turbo" ? "active" : ""}`}
              onClick={() => setModelMode("turbo")}
            >
              Turbo Mode
            </button>
            <button
              type="button"
              className={`rr-mode-btn brain ${modelMode === "brain" ? "active" : ""}`}
              onClick={() => setModelMode("brain")}
            >
              Brain Mode
            </button>
          </div>
          <p className="rr-muted">Aktiv: {activeModelLabel}</p>
        </div>

        <WeatherWidget />

        <div className="rr-panel">
          <h3>System-Ressourcen</h3>
          <p>
            CPU: <span>{Math.floor(Math.random() * 20 + 10)}%</span>
          </p>
          <p>
            RAM: <span>4.2 / 16 GB</span>
          </p>
        </div>
      </aside>

      <main className="rr-center">
        <div className="rr-center-top">
          <h2 className="rr-main-title">RAINER OS - CYBER DASHBOARD</h2>
          <AgentAvatar status={avatarStatus} autopilotActive={autopilotActive} />
        </div>

        <div className="rr-panel rr-satellite-feed">
          <h3>Live Satellite Feed</h3>
          <img
            src="https://image.pollinations.ai/prompt/cyberpunk%20satellite%20feed?width=768&height=256&nologo=true"
            alt="Cyberpunk Satellite Feed"
            className="rr-satellite-image"
          />
        </div>

        <div className="rr-chat-head">
          <span className="rr-chat-title">Chat-Verlauf</span>
          {isUploading && <span className="rr-upload-badge">Lade Datei...</span>}
          {!isUploading && uploadedFileName && (
            <span className="rr-upload-badge ready">Datei bereit</span>
          )}
          <label className="rr-toggle">
            <input
              type="checkbox"
              checked={autopilotActive}
              onChange={(e) => setAutopilotActive(e.target.checked)}
            />
            <span>Autopilot</span>
          </label>
        </div>
        <div className="rr-chat" ref={chatRef}>
          {messages.map((msg) => {
            const directImageUrl = String(msg.imageUrl || msg.image_url || "").trim();
            const textImageUrl = extractImageUrlFromText(msg.text);
            const urlRegex = /(https?:\/\/image\.pollinations\.ai[^\s]+)/g;
            const parsedImageMatch = String(msg.text || "").match(urlRegex);
            const parsedImageUrl = parsedImageMatch?.[0] || "";
            const finalImageUrl = directImageUrl || parsedImageUrl || textImageUrl;
            const normalizedType = String(msg.type || "").toLowerCase();
            const shouldRenderImage =
              normalizedType === "image" || (!normalizedType && Boolean(finalImageUrl));
            const retryCount = imageRetries[msg.id] || 0;
            const imageSrc = finalImageUrl
              ? appendCacheBuster(finalImageUrl, `${msg.id}-${retryCount}`)
              : "";
            const proxyImageSrc = imageSrc
              ? `${API_BASE}/api/proxy-image?url=${encodeURIComponent(imageSrc)}`
              : "";
            const isImageStillLoading = shouldRenderImage && imageLoading[msg.id] !== false;
            const isImageFailed = shouldRenderImage && imageFailed[msg.id] === true;

            return (
              <div key={msg.id} className={`rr-msg ${msg.sender}`}>
                <div className="rr-msg-head">
                  <strong>{msg.sender === "user" ? "MATTHIAS" : "RAINER"}</strong>
                  <span>{msg.time}</span>
                </div>
                {msg.text && <p>{msg.text}</p>}
                {shouldRenderImage && (
                  <>
                    {isImageStillLoading && !isImageFailed && <p>Bild lädt...</p>}
                    {isImageFailed && (
                      <div className="rr-image-fallback">
                        <p>Bild konnte nicht geladen werden.</p>
                        <button
                          type="button"
                          onClick={() => {
                            setImageFailed((prev) => ({ ...prev, [msg.id]: false }));
                            setImageLoading((prev) => ({ ...prev, [msg.id]: true }));
                            setImageRetries((prev) => ({
                              ...prev,
                              [msg.id]: (prev[msg.id] || 0) + 1,
                            }));
                          }}
                        >
                          Neu laden
                        </button>
                      </div>
                    )}
                    {proxyImageSrc && !isImageFailed && (
                      <div className="image-wrapper">
                        <img
                          src={proxyImageSrc}
                          crossOrigin="anonymous"
                          referrerPolicy="no-referrer"
                          alt="KI Bild"
                          className="cyber-image"
                          onLoad={() => {
                            setImageLoading((prev) => ({ ...prev, [msg.id]: false }));
                            setImageFailed((prev) => ({ ...prev, [msg.id]: false }));
                          }}
                          onError={() => {
                            setImageLoading((prev) => ({ ...prev, [msg.id]: false }));
                            setImageFailed((prev) => ({ ...prev, [msg.id]: true }));
                          }}
                        />
                      </div>
                    )}
                  </>
                )}
              </div>
            );
          })}
          {loading && <div className="rr-loading">Autopilot analysiert...</div>}
        </div>

        <div className="rr-input-row">
          <input
            id="file-upload"
            type="file"
            className="rr-file-input"
            onChange={uploadFile}
          />
          <label htmlFor="file-upload" className="rr-upload-label" title="Datei hochladen">
            +
          </label>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Befehl eingeben..."
          />
          <button type="button" onClick={handleSend}>
            Senden
          </button>
          <button
            type="button"
            className="rr-space-btn"
            onClick={() => setInput("Generiere ein Weltraum-Bild")}
          >
            🌌 Space
          </button>
        </div>
      </main>

      <aside className="rr-sidebar-right">
        <div className="rr-panel">
          <h3>Learning Stats</h3>
          <p>
            Gelöst: <span>{learningStats.solved}</span>
          </p>
          <p>
            Erfolgsrate: <span>{learningStats.successRate}</span>
          </p>
          <p>
            Memory Hits: <span>{learningStats.memoryHits}</span>
          </p>
        </div>

        <div className="rr-panel">
          <h3>Probleme</h3>
          {memoryData.problems.map((item) => (
            <p key={`p-${item}`}>
              {item}
            </p>
          ))}
        </div>

        <div className="rr-panel">
          <h3>Projektstruktur</h3>
          {memoryData.project.map((item) => (
            <p key={`s-${item}`}>
              {item}
            </p>
          ))}
          <div className="rr-sub">Facts</div>
          {memoryData.facts.map((item) => (
            <p key={`f-${item}`}>
              {item}
            </p>
          ))}
        </div>

        <div className="rr-panel">
          <h3>Integrationen</h3>
          {INTEGRATIONS.map((item) => (
            <p key={item} className={item.includes("UNIV-CONVERTER") ? "rr-badge-online" : ""}>
              {item}
            </p>
          ))}
          {isUploading && <p className="rr-processing">PROCESSING...</p>}
          {isConverting && <p className="rr-processing">PROCESSING...</p>}
        </div>

        <div className="rr-panel">
          <h3>Live-Code-View</h3>
          <div className="rr-code-terminal">
            {codeActivity.length === 0 && (
              <p className="rr-code-line">Warte auf Code-Aktivität...</p>
            )}
            {codeActivity.slice(-8).map((entry, idx) => (
              <p key={`${entry.time}-${idx}`} className="rr-code-line">
                [{entry.time}] {entry.action} | {entry.status} | {entry.file}
              </p>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}

export default App;
