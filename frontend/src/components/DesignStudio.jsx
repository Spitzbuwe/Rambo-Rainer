import React, { useCallback, useState, useRef } from "react";
import ChatPanel from "./ChatPanel.jsx";
import Canvas from "./Canvas.jsx";
import DesignStudio3D from "./DesignStudio3D.jsx";
import { createInitialCanvasState, normalizeCanvasState } from "../store/canvasStore.js";
import "./DesignStudio.css";

/** Gleiche Erweiterungen wie K.5 Code-IDE (ChatPanel). */
const CODE_UPLOAD_ACCEPT = ".py,.js,.jsx,.html,.css,.ts,.tsx";

export default function DesignStudio({ onClose }) {
  const [studioTab, setStudioTab] = useState("2d");
  const [messages, setMessages] = useState([]);
  const [canvasState, setCanvasState] = useState(() => createInitialCanvasState());
  /** Für K.5: lokales Dateiobjekt wie im Hauptchat (`pendingLocalFile`). */
  const [uploadedFile, setUploadedFile] = useState(null);
  const codeFileInputRef = useRef(null);

  const handleChatMessage = (message) => {
    setMessages((prev) => [...prev, message]);
  };

  const handleCanvasChange = useCallback((update) => {
    setCanvasState((prev) => {
      const normalized = normalizeCanvasState(prev);
      const next = typeof update === "function" ? update(normalized) : update;
      return normalizeCanvasState(next);
    });
  }, []);

  const handleCodeFileSelected = (event) => {
    const file = event?.target?.files?.[0];
    if (!file) return;
    setUploadedFile(file);
    if (event.target) event.target.value = "";
  };

  const clearUploadedCodeFile = () => {
    setUploadedFile(null);
    if (codeFileInputRef.current) codeFileInputRef.current.value = "";
  };

  return (
    <div className="design-studio">
      <div className="design-studio-header">
        <div className="design-studio-header__row">
          {typeof onClose === "function" ? (
            <button type="button" className="design-studio-back" onClick={onClose}>
              ← Control Center
            </button>
          ) : (
            <span className="design-studio-back-spacer" aria-hidden />
          )}
          <h1>🎨 Rambo Design Studio</h1>
          <div className="design-studio-tabs" role="tablist" aria-label="Studio-Ansicht">
            <button
              type="button"
              role="tab"
              aria-selected={studioTab === "2d"}
              className={studioTab === "2d" ? "design-studio-tab design-studio-tab--on" : "design-studio-tab"}
              onClick={() => setStudioTab("2d")}
            >
              2D / Canvas
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={studioTab === "3d"}
              className={studioTab === "3d" ? "design-studio-tab design-studio-tab--on" : "design-studio-tab"}
              onClick={() => setStudioTab("3d")}
            >
              3D
            </button>
          </div>
          <div className="design-studio-code-upload" aria-label="Code-Datei für K.5">
            <input
              ref={codeFileInputRef}
              id="design-studio-code-file"
              type="file"
              accept={CODE_UPLOAD_ACCEPT}
              className="design-studio-code-file-input"
              onChange={handleCodeFileSelected}
            />
            <label htmlFor="design-studio-code-file" className="design-studio-code-file-label">
              Code-Datei
            </label>
            {uploadedFile?.name ? (
              <span className="design-studio-code-file-name" title={uploadedFile.name}>
                {uploadedFile.name}
                <button
                  type="button"
                  className="design-studio-code-file-clear"
                  onClick={clearUploadedCodeFile}
                  aria-label="Code-Datei entfernen"
                >
                  ×
                </button>
              </span>
            ) : (
              <span className="design-studio-code-file-hint">Optional für Code-IDE</span>
            )}
          </div>
        </div>
      </div>

      {studioTab === "3d" ? (
        <div className="design-studio-container design-studio-container--3d">
          <DesignStudio3D />
        </div>
      ) : (
        <div className="design-studio-container">
          <div className="chat-panel-wrapper">
            <ChatPanel
              messages={messages}
              onMessage={handleChatMessage}
              canvasState={canvasState}
              onCanvasUpdate={(newState) => setCanvasState(normalizeCanvasState(newState))}
              uploadedFile={uploadedFile}
            />
          </div>
          <div className="canvas-wrapper">
            <Canvas state={canvasState} onChange={handleCanvasChange} />
          </div>
        </div>
      )}
    </div>
  );
}
