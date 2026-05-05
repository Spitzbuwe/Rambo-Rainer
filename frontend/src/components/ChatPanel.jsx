import React, { useState, useRef, useEffect } from "react";
import { chatService } from "../services/chatService.js";
import { aiCanvasService } from "../services/aiCanvasService.js";
import { imageService } from "../services/imageService.js";
import { meshService } from "../services/meshService.js";
import { createInitialCanvasState, normalizeCanvasState } from "../store/canvasStore.js";
import { parseCanvasCommand } from "../utils/commandParser.js";
import { parseImageIntent } from "../utils/imageIntentParser.js";
import { parse3DIntent, is3DIntent, isTextTo3dChatPrompt } from "../utils/meshIntentParser.js";
import { parseCodeIntent, isCodeIntent } from "../utils/codeIntentParser.js";
import { codeService } from "../services/codeService.js";
import CodeViewer from "./CodeViewer.jsx";
import DepthMapViewer from "./DepthMapViewer.jsx";
import MeshPreview from "./MeshPreview.jsx";
import { executeCanvasAction } from "../utils/canvasActions.js";
import "./ChatPanel.css";

const CODE_FILE_EXTENSIONS = [".py", ".js", ".jsx", ".html", ".css", ".ts", ".tsx"];

function formatCodePipelineErrorMessage(rawError) {
  const msg = String(rawError?.message || rawError || "").trim();
  if (!msg) return "⚠️ Code-Verarbeitung fehlgeschlagen.";
  if (
    /ollama.*nicht erreichbar/i.test(msg) ||
    msg.includes("HTTP 503") ||
    msg.includes("503")
  ) {
    return "❌ Ollama ist nicht erreichbar. Bitte lokal `ollama serve` starten und erneut versuchen.";
  }
  if (/timeout|HTTP 504|504/i.test(msg)) {
    return "⏱️ Ollama-Timeout bei Code-Verarbeitung. Bitte erneut versuchen.";
  }
  if (/extrahiert|keine verwertbare antwort|502|HTTP 502/i.test(msg)) {
    return "⚠️ Ollama-Antwort war leer oder unbrauchbar. Bitte Prompt präzisieren und erneut ausführen.";
  }
  return `⚠️ Code-Verarbeitung fehlgeschlagen: ${msg}`;
}

const SUGGESTED_COMMANDS = [
  '🎨 "Erstelle eine rote Box"',
  '🟢 "Erstelle einen grünen Kreis"',
  '✏️ "Erstelle einen Text"',
  '❌ "Lösche das letzte Element"',
];

export default function ChatPanel({
  messages,
  onMessage,
  canvasState,
  onCanvasUpdate,
  uploadedFile,
}) {
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [aiPending, setAiPending] = useState(false);
  const [mode, setMode] = useState("turbo");
  const [ollamaStatus, setOllamaStatus] = useState("offline");
  const messagesEndRef = useRef(null);

  useEffect(() => {
    aiCanvasService.checkOllamaStatus().then((s) => {
      setOllamaStatus(s.status === "ok" ? "ok" : "offline");
    });
  }, []);

  useEffect(() => {
    const el = messagesEndRef.current;
    if (el && typeof el.scrollIntoView === "function") {
      el.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    const text = inputValue.trim();
    if (!text) return;

    const userMessage = {
      id: `local-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };

    onMessage(userMessage);
    setInputValue("");
    setIsLoading(true);

    try {
      const lowerName = String(uploadedFile?.name || "").toLowerCase();
      const hasCodeFile =
        !!uploadedFile?.name && CODE_FILE_EXTENSIONS.some((ext) => lowerName.endsWith(ext));

      if (hasCodeFile) {
        const codeIntent = parseCodeIntent(text);
        if (isCodeIntent(codeIntent)) {
          try {
            const fileText = await uploadedFile.text();
            const uploadResult = await codeService.uploadCode(uploadedFile.name, fileText);
            const processResult = await codeService.processCode(
              uploadResult.file_id,
              codeIntent.action,
              text,
            );

            let responseContent = "";
            let codeViewerPayload = null;

            if (codeIntent.action === "explain_code") {
              responseContent = `Code: ${codeIntent.label}\n\n${processResult.result}`;
              codeViewerPayload = {
                code: fileText,
                language: uploadResult.language,
                filename: uploadResult.filename,
              };
            } else {
              responseContent = `Code: ${codeIntent.label}\n\nCode aktualisiert (v${processResult.version}).`;
              codeViewerPayload = {
                code: processResult.result,
                language: uploadResult.language,
                filename: uploadResult.filename,
              };
            }

            onMessage({
              id: `code-${Date.now()}`,
              role: "assistant",
              content: responseContent,
              timestamp: new Date().toISOString(),
              action: "code_process",
              file_id: uploadResult.file_id,
              codeViewer: codeViewerPayload,
            });
            return;
          } catch (codeError) {
            onMessage({
              id: `code-err-${Date.now()}`,
              role: "assistant",
              content: formatCodePipelineErrorMessage(codeError),
              timestamp: new Date().toISOString(),
            });
            return;
          }
        }
      }

      const command = parseCanvasCommand(text);

      const applyChatServiceResponse = async () => {
        const response = await chatService.sendMessage(text);
        console.log("📥 Response received:", response);
        console.log("TYPE CHECK:", response.type, "PATH:", response.depth_map_path);
        if (response.error) {
          console.error("AI Error:", response.error);
          onMessage({
            id: `chat-err-${Date.now()}`,
            role: "assistant",
            content: `⚠️ Chat: ${response.error}`,
            timestamp: new Date().toISOString(),
          });
          return;
        }
        console.log("✅ Message passed to onMessage");
        const base = {
          id: response.id ?? `a-${Date.now()}`,
          role: "assistant",
          content:
            typeof response.content === "string"
              ? response.content
              : JSON.stringify(response.content ?? response),
          timestamp: response.timestamp ?? new Date().toISOString(),
        };
        if (
          response.type === "depth_map" ||
          response.type === "mesh_mvp" ||
          response.type === "text_to_3d_mvp"
        ) {
          base.type = response.type;
          base.action = response.action;
          base.depth_map_path = response.depth_map_path;
          base.depth_map_download_url = response.depth_map_download_url || response.depth_map_path;
          base.depth_map_filename = response.depth_map_filename || "depth_map.png";
          base.mesh_filename = response.mesh_filename || null;
          base.mesh_download_url = response.mesh_download_url || null;
          base.mesh_format = response.mesh_format || null;
          base.mesh_vertices = response.mesh_vertices ?? null;
          base.mesh_faces = response.mesh_faces ?? null;
          base.stl_filename = response.stl_filename || null;
          base.stl_download_url = response.stl_download_url || null;
          base.glb_filename = response.glb_filename || null;
          base.glb_download_url = response.glb_download_url || null;
          base.job_id = response.job_id ?? null;
        }
        onMessage(base);
      };

      const hasUploadedFile = !!uploadedFile?.name &&
        (uploadedFile?.type?.startsWith("image/") ||
         /\.(jpg|jpeg|jpe|jfif|png|gif|webp|bmp|tif|tiff)$/i.test(uploadedFile?.name));

      if (command.recognized && typeof onCanvasUpdate === "function") {
        const base = canvasState ?? createInitialCanvasState();
        const { state: newState, message: actionMessage } = executeCanvasAction(base, command);
        onCanvasUpdate(newState);
        onMessage({
          id: `a-${Date.now()}`,
          role: "assistant",
          content: actionMessage,
          timestamp: new Date().toISOString(),
        });
        return;
      }
      if (isTextTo3dChatPrompt(text)) {
        await applyChatServiceResponse();
        return;
      }
      if (hasUploadedFile) {
        const imageIntent = parseImageIntent(text);
        if (imageIntent.recognized) {
          try {
            const result = await imageService.processImage(uploadedFile.name, imageIntent.action);
            onMessage({
              id: `img-${Date.now()}`,
              role: "assistant",
              content: `✨ ${result.message}\n\n📥 Datei: ${result.result}`,
              timestamp: new Date().toISOString(),
              action: "image_processed",
            });
            return;
          } catch (imageError) {
            onMessage({
              id: `img-err-${Date.now()}`,
              role: "assistant",
              content: `⚠️ Verarbeitung fehlgeschlagen: ${imageError.message}`,
              timestamp: new Date().toISOString(),
            });
            return;
          }
        }

        const meshIntent = parse3DIntent(text);
        if (is3DIntent(meshIntent)) {
          try {
            const result = await meshService.processMesh(uploadedFile.name, meshIntent.action);
            if (!result || typeof result !== "object" || Array.isArray(result)) {
              throw new Error("Ungültige Response vom Server");
            }
            const resolvedPath =
              result.depth_map_path ||
              result.depth_map_download_url ||
              result.download_url ||
              (result.result_file ? `/api/download/${encodeURIComponent(result.result_file)}` : "");
            onMessage({
              id: `mesh-${Date.now()}`,
              role: "assistant",
              content: `🟦 ${result.message || "Depth-Map generiert"}\n\n📁 Status: ${result.status || result.pipeline_status || "success"}\n📄 Datei: ${result.result_file || result.result_filename || "N/A"}`,
              timestamp: new Date().toISOString(),
              action: "mesh_process",
              job_id: result.job_id || null,
              type: "depth_map",
              depth_map_path: resolvedPath,
              depth_map_download_url: resolvedPath,
              depth_map_filename: result.result_file || result.result_filename || "depth_map.png",
              mesh_filename: result.mesh_filename || null,
              mesh_download_url: result.mesh_download_url || null,
              mesh_format: result.mesh_format || null,
              mesh_vertices: result.mesh_vertices ?? null,
              mesh_faces: result.mesh_faces ?? null,
              stl_filename: result.stl_filename || null,
              stl_download_url: result.stl_download_url || null,
              glb_filename: result.glb_filename || null,
              glb_download_url: result.glb_download_url || null,
            });
            return;
          } catch (meshError) {
            onMessage({
              id: `mesh-err-${Date.now()}`,
              role: "assistant",
              content: `⚠️ 3D-Verarbeitung fehlgeschlagen: ${meshError.message}`,
              timestamp: new Date().toISOString(),
            });
            return;
          }
        }
      }

      if (!command.recognized && typeof onCanvasUpdate === "function") {
        setAiPending(true);
        try {
          const aiResult = await aiCanvasService.generateCanvas(text, mode, canvasState?.elements ?? []);
          const base = normalizeCanvasState(canvasState ?? createInitialCanvasState());
          const elements = Array.isArray(aiResult.elements) ? aiResult.elements : [];
          onCanvasUpdate({
            ...base,
            elements,
            selectedId: elements[0]?.id ?? null,
          });
          onMessage({
            id: `a-${Date.now()}`,
            role: "assistant",
            content: `✨ ${aiResult.message || "Canvas aktualisiert"}`,
            timestamp: new Date().toISOString(),
          });
        } catch (aiError) {
          console.error("AI Error:", aiError);
          const errorMsg = aiError?.message || "Fehler bei KI-Generierung";
          let response = {
            id: Date.now() + 1,
            role: "assistant",
            content: `⚠️ ${errorMsg}`,
            timestamp: new Date().toISOString(),
          };

          if (errorMsg.includes("503")) {
            response.content = "❌ Ollama läuft nicht. Starte: ollama serve";
          } else if (errorMsg.includes("504") || errorMsg.includes("Timeout")) {
            response.content =
              "⏱️ Ollama antwortet zu langsam. Versuche: \n- Andere Apps schließen\n- Einfacheres Kommando\n- Turbo-Mode nutzen";
          } else if (errorMsg.includes("JSON")) {
            response.content = "📄 JSON-Parsing fehlgeschlagen. Schau Backend-Terminal.";
          }

          onMessage(response);
        } finally {
          setAiPending(false);
        }
      } else if (!command.recognized) {
        await applyChatServiceResponse();
      } else {
        onMessage({
          id: `hint-${Date.now()}`,
          role: "assistant",
          content: command.suggestion ?? "Canvas ist nicht mit dem Chat verbunden.",
          timestamp: new Date().toISOString(),
        });
      }
    } catch (error) {
      onMessage({
        id: `err-${Date.now()}`,
        role: "assistant",
        content: `❌ Fehler: ${error.message}`,
        timestamp: new Date().toISOString(),
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <h2>💬 Designer Assistant</h2>
        <p>Beschreibe dein Design</p>
      </div>

      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <div className="empty-icon">🎨</div>
            <p>Starten Sie ein neues Design</p>
            <p className="empty-hint">Z. B. &quot;Erstelle eine rote Box&quot; oder frei mit dem Assistenten chatten</p>
            {(canvasState?.elements?.length ?? 0) === 0 && (
              <div className="suggested-commands">
                {SUGGESTED_COMMANDS.map((cmd) => (
                  <button
                    key={cmd}
                    type="button"
                    className="suggested-btn"
                    onClick={() => {
                      const inner = cmd.match(/"([^"]+)"/);
                      setInputValue(inner ? inner[1] : cmd);
                    }}
                  >
                    {cmd}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          messages.map((msg) => {
            if (msg.role === "assistant") {
              console.log(`🔍 Render msg id=${msg.id} type=${msg.type} depth_map_path=${msg.depth_map_path}`);
            }
            const msgType = String(msg.type || "").toLowerCase();
            const isMeshType = msgType === "mesh_mvp" || msgType === "text_to_3d_mvp";
            const hasMeshCardData = Boolean(
              msg.mesh_download_url ||
                msg.mesh_filename ||
                msg.mesh_format ||
                msg.mesh_vertices != null ||
                msg.mesh_faces != null ||
                msg.stl_download_url ||
                msg.glb_download_url
            );
            return (
            <div key={msg.id} className={`message message-${msg.role}`}>
              <div className="message-avatar">{msg.role === "user" ? "👤" : "🤖"}</div>
              <div className="message-content">
                {msg.mesh_download_url || msg.glb_download_url ? (
                  <MeshPreview
                    meshUrl={msg.mesh_download_url}
                    meshFilename={msg.mesh_filename}
                    meshFormat={msg.mesh_format}
                    meshVertices={msg.mesh_vertices}
                    meshFaces={msg.mesh_faces}
                    stlUrl={msg.stl_download_url}
                    stlFilename={msg.stl_filename}
                    glbUrl={msg.glb_download_url}
                    glbFilename={msg.glb_filename}
                  />
                ) : null}
                {hasMeshCardData && !msg.mesh_download_url && !msg.glb_download_url ? (
                  <div className="mesh-preview-fallback-warning">
                    ⚠️ Mesh wurde erzeugt, aber kein Download-Link ist vorhanden.
                  </div>
                ) : null}
                {isMeshType && !hasMeshCardData ? (
                  <div className="mesh-preview-fallback-warning">
                    ⚠️ 3D-Ergebnis erkannt, aber keine Mesh-Daten für Vorschau/Download verfügbar.
                  </div>
                ) : null}
                {msg.type === "depth_map" && msg.depth_map_path ? (
                  <DepthMapViewer
                    depthMapPath={msg.depth_map_path}
                    depthMapDownloadUrl={msg.depth_map_download_url || msg.depth_map_path}
                    imagePreview={msg.depth_map_path}
                  />
                ) : null}
                {msg.type === "depth_map" && !msg.depth_map_path ? (
                  <div
                    style={{
                      padding: "10px",
                      background: "#2d2d30",
                      borderRadius: "4px",
                      color: "#999",
                      fontSize: "12px",
                      marginBottom: "8px",
                    }}
                  >
                    📊 3D-Vorschau wird vorbereitet...
                  </div>
                ) : null}
                <p>{msg.content}</p>
                {msg.codeViewer && typeof msg.codeViewer.code === "string" ? (
                  <>
                    <CodeViewer
                      code={msg.codeViewer.code}
                      language={msg.codeViewer.language}
                      filename={msg.codeViewer.filename}
                    />
                    {msg.file_id ? (
                      <button
                        type="button"
                        className="code-download-btn"
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
                        Bearbeitete Datei herunterladen
                      </button>
                    ) : null}
                  </>
                ) : null}
                <span className="message-time">
                  {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : ""}
                </span>
              </div>
            </div>
            );
          })
        )}
        {isLoading && (
          <div className="chat-loading" role="status">
            <div className="loading-spinner">⏳</div>
            <p>Ollama generiert Canvas… (dies kann 10-60 Sekunden dauern)</p>
            <small>Je nach Hardware und Modell</small>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-mode-selector" role="toolbar" aria-label="Ollama-Modus">
        <button
          type="button"
          className={`mode-btn${mode === "turbo" ? " active" : ""}`}
          onClick={() => setMode("turbo")}
          title="Schnell (Llama / Turbo-Modell)"
        >
          🚀 Turbo
        </button>
        <button
          type="button"
          className={`mode-btn${mode === "brain" ? " active" : ""}`}
          onClick={() => setMode("brain")}
          title="Ausführlicher (Brain-Modell, z. B. DeepSeek-R1)"
        >
          🧠 Brain
        </button>
        <span className="mode-status">{ollamaStatus === "ok" ? "✅ Ollama" : "❌ Offline"}</span>
      </div>

      <form className="chat-input-form" onSubmit={handleSendMessage}>
        <input
          type="text"
          placeholder="Beschreibe dein Design oder gib einen Befehl..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          disabled={isLoading}
          className="chat-input"
          aria-label="Chat-Eingabe"
        />
        <button
          type="submit"
          disabled={isLoading}
          className="chat-send-btn"
          aria-label="Nachricht senden"
        >
          {isLoading ? "⏳" : "➤"}
        </button>
      </form>
    </div>
  );
}
