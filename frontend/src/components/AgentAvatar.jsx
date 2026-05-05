import React from "react";

const MODE = {
  idle: {
    core: "radial-gradient(circle, rgba(56,189,248,0.9) 0%, rgba(30,64,175,0.7) 45%, rgba(15,23,42,0.2) 100%)",
    ring: "rgba(59,130,246,0.45)",
    glow: "0 0 26px rgba(56,189,248,0.45)",
    speed: "6.5s",
  },
  thinking: {
    core: "radial-gradient(circle, rgba(186,230,253,0.98) 0%, rgba(6,182,212,0.88) 35%, rgba(14,116,144,0.5) 100%)",
    ring: "rgba(34,211,238,0.7)",
    glow: "0 0 42px rgba(34,211,238,0.85)",
    speed: "2.1s",
  },
  searching: {
    core: "radial-gradient(circle, rgba(125,211,252,0.95) 0%, rgba(37,99,235,0.72) 50%, rgba(15,23,42,0.2) 100%)",
    ring: "rgba(56,189,248,0.8)",
    glow: "0 0 38px rgba(34,211,238,0.7)",
    speed: "3s",
  },
  error: {
    core: "radial-gradient(circle, rgba(248,113,113,0.95) 0%, rgba(220,38,38,0.8) 50%, rgba(15,23,42,0.2) 100%)",
    ring: "rgba(248,113,113,0.82)",
    glow: "0 0 34px rgba(239,68,68,0.76)",
    speed: "1.15s",
  },
  converting: {
    core: "radial-gradient(circle, rgba(244,114,182,0.98) 0%, rgba(217,70,239,0.85) 45%, rgba(88,28,135,0.38) 100%)",
    ring: "rgba(236,72,153,0.8)",
    glow: "0 0 44px rgba(236,72,153,0.85)",
    speed: "1.35s",
  },
};

export default function AgentAvatar({ status = "idle", autopilotActive = false }) {
  const mode = MODE[status] ? status : "idle";
  const style = MODE[mode];
  const searching = mode === "searching";
  const error = mode === "error";

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        maxWidth: "470px",
        aspectRatio: "1 / 1",
        margin: "0 auto",
        borderRadius: "26px",
        overflow: "hidden",
        background:
          "radial-gradient(circle at center, rgba(8,47,73,0.36), rgba(15,23,42,0.9) 58%, rgba(2,6,23,0.95) 100%)",
        boxShadow: autopilotActive ? "0 0 28px rgba(74,222,128,0.46)" : "0 0 18px rgba(34,211,238,0.2)",
        border: autopilotActive ? "1px solid rgba(74,222,128,0.72)" : "1px solid rgba(34,211,238,0.22)",
      }}
    >
      <style>{`
        @keyframes holoPulse {
          0% { transform: scale(0.93); opacity: 0.68; }
          50% { transform: scale(1.03); opacity: 1; }
          100% { transform: scale(0.93); opacity: 0.68; }
        }

        @keyframes holoRotate {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }

        @keyframes holoScan {
          0% { transform: rotate(0deg); opacity: 0.08; }
          50% { opacity: 0.72; }
          100% { transform: rotate(360deg); opacity: 0.08; }
        }

        @keyframes holoGlitch {
          0%, 100% { transform: translateX(0); }
          20% { transform: translateX(-2px); }
          40% { transform: translateX(2px); }
          60% { transform: translateX(-1px); }
          80% { transform: translateX(1px); }
        }
      `}</style>

      <div
        style={{
          position: "absolute",
          inset: "10%",
          borderRadius: "50%",
          border: `1px solid ${style.ring}`,
          animation: "holoRotate 12s linear infinite",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: "19%",
          borderRadius: "50%",
          border: `1px dashed ${style.ring}`,
          animation: "holoRotate 17s linear infinite reverse",
        }}
      />

      {searching && (
        <div
          style={{
            position: "absolute",
            inset: "9%",
            borderRadius: "50%",
            background: "conic-gradient(from 0deg, transparent 0%, rgba(34,211,238,0.52) 12%, transparent 24%)",
            animation: "holoScan 1.9s linear infinite",
          }}
        />
      )}

      <div
        style={{
          position: "absolute",
          inset: mode === "thinking" ? "30%" : "34%",
          borderRadius: "50%",
          background: style.core,
          boxShadow: style.glow,
          animation: `holoPulse ${style.speed} ease-in-out infinite${error ? ", holoGlitch 0.26s ease-in-out infinite" : ""}`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: "0",
          background: "radial-gradient(circle at center, rgba(186,230,253,0.14), transparent 52%)",
          pointerEvents: "none",
        }}
      />
    </div>
  );
}
