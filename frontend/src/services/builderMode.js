/**
 * Builder-Mode: Intent-Erkennung über POST /api/builder-mode.
 * Nutzung z. B. vor Chat-Verarbeitung; apiBase wie in der App ("" = Vite-Proxy).
 */
export async function checkBuilderMode(apiBase, input) {
  const base = String(apiBase ?? "").replace(/\/$/, "");
  const url = `${base}/api/builder-mode`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input: String(input ?? "") }),
  });
  if (!res.ok) {
    throw new Error(`builder-mode HTTP ${res.status}`);
  }
  const raw = await res.text();
  if (!raw || !raw.trim()) return {};
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}
