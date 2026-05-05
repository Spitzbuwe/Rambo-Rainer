const W = 800;
const H = 600;

function buildSvgDocument(elements, backgroundColor) {
  const parts = [
    `<?xml version="1.0" encoding="UTF-8"?>`,
    `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`,
    `<rect x="0" y="0" width="${W}" height="${H}" fill="${escapeAttr(backgroundColor || "#ffffff")}"/>`,
  ];
  for (const el of elements) {
    if (el.type === "rect") {
      parts.push(
        `<rect x="${el.x}" y="${el.y}" width="${el.width}" height="${el.height}" fill="${escapeAttr(el.fill)}" stroke="${escapeAttr(el.stroke)}" stroke-width="${el.strokeWidth || 0}"/>`,
      );
    } else if (el.type === "circle") {
      const r = el.width / 2;
      const cx = el.x + r;
      const cy = el.y + r;
      parts.push(
        `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${escapeAttr(el.fill)}" stroke="${escapeAttr(el.stroke)}" stroke-width="${el.strokeWidth || 0}"/>`,
      );
    } else if (el.type === "text") {
      const y = el.y + (el.fontSize || 16);
      parts.push(
        `<text x="${el.x}" y="${y}" font-size="${el.fontSize || 16}" font-family="${escapeAttr(el.fontFamily || "Arial")}" fill="${escapeAttr(el.fill)}">${escapeXml(el.text || "")}</text>`,
      );
    } else if (el.type === "image" && el.href) {
      parts.push(
        `<image href="${escapeAttr(el.href)}" x="${el.x}" y="${el.y}" width="${el.width}" height="${el.height}" preserveAspectRatio="xMidYMid meet"/>`,
      );
    }
  }
  parts.push(`</svg>`);
  return parts.join("");
}

function escapeAttr(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;");
}

function escapeXml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function downloadSvg(elements, backgroundColor, filename = "canvas-export.svg") {
  const svg = buildSvgDocument(elements, backgroundColor);
  const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function loadImage(href) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = href;
  });
}

/** PNG-Export (800×600), Reihenfolge wie `elements`. */
export async function downloadPng(elements, backgroundColor, filename = "canvas-export.png") {
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  ctx.fillStyle = backgroundColor || "#ffffff";
  ctx.fillRect(0, 0, W, H);

  for (const el of elements) {
    if (el.type === "rect") {
      ctx.fillStyle = el.fill || "#667eea";
      ctx.fillRect(el.x, el.y, el.width, el.height);
      if (el.strokeWidth > 0) {
        ctx.strokeStyle = el.stroke || "#000";
        ctx.lineWidth = el.strokeWidth;
        ctx.strokeRect(el.x, el.y, el.width, el.height);
      }
    } else if (el.type === "circle") {
      const r = el.width / 2;
      const cx = el.x + r;
      const cy = el.y + r;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fillStyle = el.fill || "#667eea";
      ctx.fill();
      if (el.strokeWidth > 0) {
        ctx.strokeStyle = el.stroke || "#000";
        ctx.lineWidth = el.strokeWidth;
        ctx.stroke();
      }
    } else if (el.type === "text") {
      ctx.fillStyle = el.fill || "#111";
      ctx.font = `${el.fontWeight || "normal"} ${el.fontSize || 16}px ${el.fontFamily || "Arial"}`;
      ctx.fillText(el.text || "", el.x, el.y + (el.fontSize || 16));
    } else if (el.type === "image" && el.href) {
      const img = await loadImage(el.href);
      if (img) ctx.drawImage(img, el.x, el.y, el.width, el.height);
    }
  }

  await new Promise((resolve) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        resolve();
        return;
      }
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      resolve();
    }, "image/png");
  });
}
