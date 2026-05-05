"""
Intent-Anreicherung: Nutzer-Modus, Session-Kontext, LLM-Rueckfall bei unklarem Routing.
Keine Flask-Abhaengigkeit.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

# Buttons / API: Frontend sendet user_mode bei erneutem Senden
SUGGESTED_INTENT_ACTIONS: list[dict[str, str]] = [
    {"id": "chat", "label": "Nur Fragen / Chat", "user_mode": "chat"},
    {"id": "read", "label": "Projekt nur lesen & erklären", "user_mode": "read"},
    {"id": "change", "label": "Im Projekt Code ändern", "user_mode": "change"},
]

_INTENT_CONFIDENCE_MIN = float(os.getenv("RAINER_INTENT_CONFIDENCE_MIN", "0.52"))


def intent_llm_enabled() -> bool:
    return str(os.getenv("RAINER_INTENT_LLM", "1")).strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def normalize_conversation_history_payload(raw: Any) -> str:
    """Flacht conversation_history aus Request zu einem kurzen DE-Text."""
    if not raw:
        return ""
    lines: list[str] = []
    if isinstance(raw, str):
        s = raw.strip()
        return s[:6000] if s else ""
    if isinstance(raw, list):
        for item in raw[-8:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or item.get("from") or "").strip().lower()
            text = str(item.get("content") or item.get("text") or item.get("message") or "").strip()
            if not text:
                continue
            if role in ("user", "human", "nutzer"):
                lines.append(f"Nutzer: {text[:1500]}")
            elif role in ("assistant", "ai", "rainer", "bot"):
                lines.append(f"Assistent: {text[:1500]}")
            else:
                lines.append(text[:1500])
    out = "\n".join(lines).strip()
    return out[:8000] if out else ""


def correction_block(data: dict[str, Any]) -> str:
    c = data.get("user_correction") or data.get("correction") or data.get("feedback_text")
    if not c:
        return ""
    s = str(c).strip()
    if not s:
        return ""
    return f"[Korrektur/Rückmeldung vom Nutzer: {s[:2000]}]"


def compose_augmented_user_message(cleaned_prompt: str, data: dict[str, Any]) -> str:
    """Erweitert den sichtbaren Auftrag für LLM-Antworten (nicht für Regex-Routing)."""
    parts = []
    hist = normalize_conversation_history_payload(data.get("conversation_history"))
    if hist:
        parts.append("--- Bisheriger Verlauf (Auszug) ---\n" + hist)
    cb = correction_block(data)
    if cb:
        parts.append(cb)
    if not parts:
        return cleaned_prompt
    return "\n\n".join(parts) + "\n\n--- Aktuelle Anfrage ---\n" + cleaned_prompt


def apply_user_mode_override(
    pk: str,
    user_mode: str | None,
    *,
    is_risky: bool,
) -> str:
    """
    Expliziter UI-Modus hat Vorrang vor Regelklassifikation (ausser Riskant).
    user_mode: auto | chat | read | change
    """
    if is_risky or pk == "risky_project_task":
        return pk
    if not user_mode:
        return pk
    m = str(user_mode).strip().lower()
    if m in ("", "auto", "automatic"):
        return pk
    if m in ("chat", "conversation", "talk"):
        return "chat"
    if m in ("read", "analyze", "analysis", "explain", "erklaer", "lesen"):
        return "project_read"
    if m in ("change", "edit", "code", "implement", "fix", "schreib"):
        return "project_task"
    return pk


def map_llm_intent_to_pk(intent: str, confidence: float) -> str | None:
    if confidence < _INTENT_CONFIDENCE_MIN:
        return None
    i = str(intent or "").strip().lower()
    if i in ("chat", "talk", "conversation"):
        return "chat"
    if i in ("read", "analyze", "analysis", "explain"):
        return "project_read"
    if i in ("change", "edit", "code", "implement", "fix", "project"):
        return "project_task"
    if i in ("unclear", "unknown", "ambiguous"):
        return None
    return None


def parse_intent_json_blob(raw: str) -> dict[str, Any] | None:
    if not raw or not str(raw).strip():
        return None
    text = str(raw).strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def clarification_message_with_modes() -> str:
    base = (
        "Ich bin mir bei der Absicht noch nicht sicher. "
        "Wähle unten einen **Modus** und sende dieselbe oder eine präzisere Frage erneut — "
        "oder schreib einen Satz: nur erklären, oder konkret welche Datei ich ändern soll."
    )
    return base


def run_llm_intent_refinement(cleaned_prompt: str, history_block: str) -> str | None:
    """
    Liefert project_task | project_read | chat bei Erfolg, sonst None.
    """
    if not intent_llm_enabled():
        return None
    import concurrent.futures

    from model_providers import generate_intent_classification_response, is_llm_failure_message

    combined = str(cleaned_prompt or "").strip()
    hb = (history_block or "").strip()
    if hb:
        combined = (hb + "\n\n---\nAktuelle Anfrage:\n" + combined)[:12000]
    if not combined:
        return None
    sec = float(os.getenv("RAINER_INTENT_LLM_TIMEOUT_SEC", "10"))
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(generate_intent_classification_response, combined)
            raw = fut.result(timeout=max(2.0, sec))
    except Exception:
        return None
    if not raw or is_llm_failure_message(raw):
        return None
    obj = parse_intent_json_blob(raw)
    if not obj:
        return None
    try:
        conf = float(obj.get("confidence", 0))
    except (TypeError, ValueError):
        conf = 0.0
    intent = str(obj.get("intent") or "").strip()
    return map_llm_intent_to_pk(intent, conf)
