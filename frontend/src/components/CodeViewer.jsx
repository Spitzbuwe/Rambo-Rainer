import React from "react";
import "./CodeViewer.css";

export default function CodeViewer({ code, language, filename }) {
  const getLanguageClass = (lang) => {
    const map = {
      python: "language-python",
      javascript: "language-javascript",
      jsx: "language-javascript",
      html: "language-html",
      css: "language-css",
      typescript: "language-typescript",
      tsx: "language-typescript",
    };
    return map[lang] || "language-plaintext";
  };

  const langLabel = typeof language === "string" ? language : "text";

  return (
    <div className="code-viewer">
      <div className="code-header">
        <span className="code-filename">{filename}</span>
        <span className="code-language">{langLabel.toUpperCase()}</span>
      </div>
      <pre className={`code-block ${getLanguageClass(langLabel)}`}>
        <code>{code}</code>
      </pre>
    </div>
  );
}
