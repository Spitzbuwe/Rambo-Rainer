import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App.jsx";

class RenderBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      const e = this.state.error;
      const text = String(e?.message || e || "Error");
      return (
        <div
          style={{
            minHeight: "100vh",
            margin: 0,
            boxSizing: "border-box",
            background: "#0a0606",
            color: "#f47171",
            padding: 24,
            fontFamily: "ui-monospace, monospace",
            fontSize: 13,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {text}
        </div>
      );
    }
    return this.props.children;
  }
}

const container = document.getElementById("root");
if (container) {
  ReactDOM.createRoot(container).render(
    <React.StrictMode>
      <RenderBoundary>
        <App />
      </RenderBoundary>
    </React.StrictMode>
  );
}
