"""
Lokale LLM-Provider: Ollama, LM Studio (OpenAI-kompatibel), optional llama.cpp.

Externe APIs sind nur vorbereitet (Katalog); Aufruf nur mit explizitem allow_external —
keine gespeicherten API-Keys in diesem Modul.
Konfiguration: Umgebungsvariablen und optional data/config/rainer_llm.json (Projektroot).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

import requests

try:
    from openai import OpenAI as _OpenAIClient  # type: ignore
except ImportError:  # pragma: no cover
    _OpenAIClient = None

PROVIDER_OLLAMA = "ollama"
PROVIDER_LM_STUDIO = "lm_studio"
PROVIDER_LLAMACPP = "llama_cpp"
# Vorbereitet, nur nutzbar wenn allow_external explizit true (derzeit kein Aufruf implementiert)
PROVIDER_GROQ = "groq"
PROVIDER_OPENAI_API = "openai_api"
PROVIDER_ANTHROPIC_API = "anthropic_api"
_LOCAL_ACTIVE_IDS = {PROVIDER_OLLAMA, PROVIDER_LM_STUDIO, PROVIDER_LLAMACPP}
_EXTERNAL_IDS = {PROVIDER_OPENAI_API, PROVIDER_ANTHROPIC_API}

DEFAULT_OLLAMA_URL = os.getenv("RAINER_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
# LM Studio: OpenAI-kompatible API (lokaler Server)
DEFAULT_LM_STUDIO_URL = os.getenv("RAINER_LMSTUDIO_BASE_URL", "http://127.0.0.1:48999/v1")
# Health/Liste: immer OpenAI-Pfad …/v1/models (nicht Root http://127.0.0.1:48999/ oder …/48999 ohne v1)
DEFAULT_LM_STUDIO_HEALTH_MODELS_URL = DEFAULT_LM_STUDIO_URL.rstrip("/") + "/models"
DEFAULT_LM_STUDIO_MODEL = os.getenv(
    "RAINER_LMSTUDIO_MODEL",
    "qwen3-coder-30b-a3b-instruct",
)
DEFAULT_LM_STUDIO_API_KEY = os.getenv("RAINER_LMSTUDIO_API_KEY", "lm-studio")
DEFAULT_LLAMACPP_URL = os.getenv("RAINER_LLAMACPP_BASE_URL", "http://127.0.0.1:8080/v1")

_SESSION = requests.Session()
_LLM_HEALTH_CACHE: dict[str, Any] | None = None
_LLM_HEALTH_CACHE_AT: float = 0.0
_LLM_HEALTH_TTL_SEC = float(os.getenv("RAINER_LLM_HEALTH_CACHE_SEC", "45"))
_GEN_CACHE: dict[str, dict[str, Any]] = {}
CACHE_TTL_SEC = int(os.getenv("OLLAMA_CACHE_TTL_SEC", os.getenv("RAINER_LLM_CACHE_TTL_SEC", "300")))
CACHE_MAX = int(os.getenv("RAINER_LLM_CACHE_MAX_ITEMS", "500"))

_TIMEOUT_GEN = int(os.getenv("OLLAMA_TIMEOUT_SEC", os.getenv("RAINER_LLM_TIMEOUT_SEC", "60")))
_RETRY = int(os.getenv("OLLAMA_RETRY_COUNT", os.getenv("RAINER_LLM_RETRY_COUNT", "2")))


def _project_root() -> Path:
    raw = os.getenv("RAINER_PROJECT_DIR") or os.getenv("RAINER_APP_DIR")
    if raw:
        return Path(str(raw)).resolve()
    return Path(__file__).resolve().parents[1]


def _config_path() -> Path:
    return _project_root() / "data" / "config" / "rainer_llm.json"


def _truthy(val: Any) -> bool:
    if val is True:
        return True
    if val is False or val is None:
        return False
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def _load_json_config() -> dict[str, Any]:
    p = _config_path()
    if not p.is_file():
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_merged_settings() -> dict[str, Any]:
    """Env überschreibt JSON-Konfiguration."""
    jc = _load_json_config()
    allow_external = _truthy(os.getenv("RAINER_ALLOW_EXTERNAL_LLM")) or _truthy(jc.get("allow_external"))
    active = str(os.getenv("RAINER_LLM_PROVIDER") or jc.get("active_provider") or PROVIDER_LM_STUDIO).strip().lower()
    if active in _EXTERNAL_IDS and not allow_external:
        active = PROVIDER_LM_STUDIO
    if active not in _LOCAL_ACTIVE_IDS and active not in _EXTERNAL_IDS:
        active = PROVIDER_LM_STUDIO
    if active in _EXTERNAL_IDS and allow_external:
        # Externe Nutzung ist vorbereitet, Endpunkt-Calls folgen später — bis dahin lokaler OpenAI-kompatibler Pfad (LM Studio)
        active = PROVIDER_LM_STUDIO
    return {
        "active_provider": active,
        "allow_external": bool(allow_external),
        "ollama_base_url": str(os.getenv("RAINER_OLLAMA_BASE_URL") or jc.get("ollama_base_url") or DEFAULT_OLLAMA_URL).rstrip("/"),
        "lm_studio_base_url": _normalize_openai_base(
            str(os.getenv("RAINER_LMSTUDIO_BASE_URL") or jc.get("lm_studio_base_url") or DEFAULT_LM_STUDIO_URL)
        ),
        "llamacpp_base_url": _normalize_openai_base(
            str(os.getenv("RAINER_LLAMACPP_BASE_URL") or jc.get("llamacpp_base_url") or DEFAULT_LLAMACPP_URL)
        ),
        "lm_studio_model": str(
            os.getenv("RAINER_LMSTUDIO_MODEL") or jc.get("lm_studio_model") or DEFAULT_LM_STUDIO_MODEL
        ).strip(),
        "lm_studio_api_key": str(
            os.getenv("RAINER_LMSTUDIO_API_KEY") or jc.get("lm_studio_api_key") or DEFAULT_LM_STUDIO_API_KEY
        ).strip(),
        "llamacpp_model": str(os.getenv("RAINER_LLAMACPP_MODEL") or jc.get("llamacpp_model") or "").strip(),
        "ollama_fallback_model": os.getenv("OLLAMA_FALLBACK_MODEL", jc.get("ollama_fallback_model") or "qwen2.5-coder:3b"),
        "ollama_agent_fallbacks": [
            m.strip()
            for m in os.getenv(
                "OLLAMA_LOCAL_AGENT_MODEL_FALLBACKS",
                ",".join(
                    jc.get("ollama_agent_fallbacks")
                    if isinstance(jc.get("ollama_agent_fallbacks"), list)
                    else [
                        "deepseek-coder:33b",
                        "deepseek-coder:7b",
                        "mistral:latest",
                        "llama3.2:latest",
                    ]
                ),
            ).split(",")
            if m.strip()
        ],
    }


def _normalize_openai_base(url: str) -> str:
    u = str(url or "").strip().rstrip("/")
    if not u:
        return DEFAULT_LM_STUDIO_URL.rstrip("/")
    if not u.endswith("/v1"):
        u = u + "/v1"
    return u


def _openai_models_endpoint_url(base_v1_url: str) -> str:
    """GET …/v1/models (Erreichbarkeit, Modellliste). Entspricht bei Standardport DEFAULT_LM_STUDIO_HEALTH_MODELS_URL."""
    return _normalize_openai_base(base_v1_url).rstrip("/") + "/models"


def _openai_chat_completions_url(base_v1_url: str) -> str:
    """POST …/v1/chat/completions."""
    return _normalize_openai_base(base_v1_url).rstrip("/") + "/chat/completions"


def _pick_best_ollama_model(base_url: str) -> str:
    forced = str(
        os.getenv("GROQ_MODEL")
        or os.getenv("OLLAMA_MODEL")
        or os.getenv("OLLAMA_MODEL_TURBO")
        or ""
    ).strip()
    if forced:
        return forced
    preferred = [
        "llama-3.3-70b-versatile",
        "gemma3:12b-it-qat",
        "gemma3:12b",
        "qwen2.5-coder:latest",
        "qwen2.5-coder:7b",
        "deepseek-r1:8b",
    ]
    try:
        r = _SESSION.get(f"{base_url}/api/tags", timeout=3)
        if r.status_code == 200:
            available = {str(m.get("name") or "").strip() for m in list((r.json() or {}).get("models") or [])}
            for model in preferred:
                if model in available:
                    return model
    except requests.RequestException:
        pass
    return "llama-3.3-70b-versatile"


def _openai_list_models(base_v1_url: str) -> list[str]:
    url = _openai_models_endpoint_url(base_v1_url)
    try:
        r = _SESSION.get(url, timeout=3)
        if r.status_code != 200:
            return []
        data = r.json() or {}
        out = []
        for item in data.get("data") or []:
            if isinstance(item, dict) and item.get("id"):
                out.append(str(item["id"]))
        return out
    except requests.RequestException:
        return []


def _openai_pick_model(base_v1_url: str, configured: str) -> str:
    if configured:
        return configured
    models = _openai_list_models(base_v1_url)
    return models[0] if models else "local-model"


def _cache_get(key: str) -> Optional[str]:
    ent = _GEN_CACHE.get(key)
    if not ent:
        return None
    if time.time() - float(ent.get("ts", 0)) > CACHE_TTL_SEC:
        _GEN_CACHE.pop(key, None)
        return None
    return ent.get("text")


def _cache_set(key: str, text: str) -> None:
    _GEN_CACHE[key] = {"ts": time.time(), "text": text}
    if len(_GEN_CACHE) > CACHE_MAX:
        oldest = next(iter(_GEN_CACHE.keys()))
        _GEN_CACHE.pop(oldest, None)


def _fmt_err(provider_label: str, model: str, err: Any, *, provider_id: str = "") -> str:
    pid = f" [{provider_id}]" if provider_id else ""
    return (
        f"⚠️ Lokaler Provider{pid} **{provider_label}** (Modell: {model}) nicht erreichbar oder Antwort ungueltig: {err}\n\n"
        "Hinweis: Ollama starten (`ollama serve`) und ein Modell bereitstellen, oder LM Studio mit geladenem Modell "
        f"und Server z. B. unter {DEFAULT_LM_STUDIO_URL} (bzw. Ollama: {DEFAULT_OLLAMA_URL})."
    )


def get_available_providers() -> list[dict[str, Any]]:
    """Lokale Provider + vorbereitete externe Eintraege (extern nur sichtbar/aktivierbar mit allow_external)."""
    s = load_merged_settings()
    allow_ex = bool(s.get("allow_external"))
    out: list[dict[str, Any]] = [
        {
            "id": PROVIDER_OLLAMA,
            "label": "Ollama",
            "kind": "ollama",
            "base_url": s["ollama_base_url"],
            "enabled": True,
            "local_only": True,
        },
        {
            "id": PROVIDER_LM_STUDIO,
            "label": "LM Studio",
            "kind": "openai_compatible",
            "base_url": s["lm_studio_base_url"],
            "enabled": True,
            "local_only": True,
        },
        {
            "id": PROVIDER_LLAMACPP,
            "label": "llama.cpp (OpenAI-Server, optional)",
            "kind": "openai_compatible",
            "base_url": s["llamacpp_base_url"],
            "enabled": True,
            "local_only": True,
        },
        {
            "id": "groq",
            "label": "Groq (Cloud, kostenlos)",
            "kind": "groq",
            "base_url": "https://api.groq.com/openai/v1",
            "enabled": bool(__import__('os').environ.get("GROQ_API_KEY")),
            "local_only": False,
        },
        {
            "id": PROVIDER_OPENAI_API,
            "label": "OpenAI API (vorbereitet, nicht automatisch)",
            "kind": "cloud_openai",
            "base_url": "",
            "enabled": bool(allow_ex),
            "local_only": False,
            "prepared_only": True,
            "requires_allow_external": True,
        },
        {
            "id": PROVIDER_ANTHROPIC_API,
            "label": "Anthropic API (vorbereitet, nicht automatisch)",
            "kind": "cloud_anthropic",
            "base_url": "",
            "enabled": bool(allow_ex),
            "local_only": False,
            "prepared_only": True,
            "requires_allow_external": True,
        },
    ]
    return out


def allow_external_llm() -> bool:
    """True nur wenn Umgebung oder data/config explizit erlauben (keine Speicherung von Keys hier)."""
    return bool(load_merged_settings().get("allow_external"))


def get_active_provider() -> dict[str, Any]:
    import os as _os
    if _os.environ.get("GROQ_API_KEY"):
        return {
            "id": "groq",
            "label": "Groq (Cloud, kostenlos)",
            "kind": "groq",
            "base_url": "https://api.groq.com/openai/v1",
            "model": _os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        }
    s = load_merged_settings()
    pid = s["active_provider"]
    providers = {p["id"]: p for p in get_available_providers()}
    meta = providers.get(pid, providers[PROVIDER_LM_STUDIO])
    model = ""
    if pid == PROVIDER_OLLAMA:
        model = _pick_best_ollama_model(s["ollama_base_url"])
    elif pid == PROVIDER_LM_STUDIO:
        model = _openai_pick_model(s["lm_studio_base_url"], s["lm_studio_model"])
    elif pid == PROVIDER_LLAMACPP:
        model = _openai_pick_model(s["llamacpp_base_url"], s["llamacpp_model"])
    return {
        "id": pid,
        "label": meta.get("label", pid),
        "kind": meta.get("kind", ""),
        "base_url": meta.get("base_url", ""),
        "model": model,
    }


def check_provider_health(provider_id: Optional[str] = None) -> dict[str, Any]:
    if provider_id == "groq":
        import os as _os, requests as _req
        key = _os.environ.get("GROQ_API_KEY", "")
        if not key:
            return {"reachable": False, "model": "", "chat_available": False, "coding_available": False, "detail": "Kein GROQ_API_KEY"}
        try:
            r = _req.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}"}, timeout=5)
            if r.status_code == 200:
                return {"reachable": True, "model": _os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"), "chat_available": True, "coding_available": True, "detail": ""}
        except Exception as e:
            return {"reachable": False, "model": "", "chat_available": False, "coding_available": False, "detail": str(e)}
        return {"reachable": False, "model": "", "chat_available": False, "coding_available": False, "detail": "HTTP Fehler"}
    """
    Erreichbarkeit und Modellinfo für einen Provider.
    provider_id None → aktiver Provider.
    """
    s = load_merged_settings()
    pid = provider_id or s["active_provider"]
    hint = ""
    reachable = False
    model = ""
    chat_ok = False
    coding_ok = False
    detail = ""

    try:
        if pid == PROVIDER_OLLAMA:
            base = s["ollama_base_url"]
            r = _SESSION.get(f"{base}/api/tags", timeout=3)
            reachable = r.status_code == 200
            if reachable:
                model = _pick_best_ollama_model(base)
                chat_ok = coding_ok = bool(model)
            else:
                detail = f"HTTP {r.status_code}"
        elif pid in (PROVIDER_LM_STUDIO, PROVIDER_LLAMACPP):
            base_v1 = s["lm_studio_base_url"] if pid == PROVIDER_LM_STUDIO else s["llamacpp_base_url"]
            cfg_model = s["lm_studio_model"] if pid == PROVIDER_LM_STUDIO else s["llamacpp_model"]
            try:
                r0 = _SESSION.get(_openai_models_endpoint_url(base_v1), timeout=3)
                reachable = r0.status_code == 200
                models = _openai_list_models(base_v1) if reachable else []
                model = cfg_model or (models[0] if models else "")
                chat_ok = coding_ok = reachable and bool(model)
                detail = "OK" if reachable else f"HTTP {r0.status_code}"
            except requests.RequestException as ex:
                detail = str(ex)
                reachable = False
        elif pid in _EXTERNAL_IDS:
            reachable = False
            model = "—"
            chat_ok = coding_ok = False
            detail = "Externer Provider nur vorbereitet — nicht implementiert / Keys werden nicht gespeichert."
        else:
            detail = "unbekannter Provider"
    except requests.RequestException as ex:
        detail = str(ex)
        hint = str(ex)

    if not reachable:
        hint = hint or "Server nicht erreichbar oder keine Modelle geladen."

    return {
        "provider_id": pid,
        "reachable": reachable,
        "model": model or "—",
        "chat_available": bool(chat_ok and reachable),
        "coding_available": bool(coding_ok and reachable),
        "detail": detail,
        "hint": hint,
    }


def summarize_llm_health() -> dict[str, Any]:
    """Übersicht für UI und /api/status (gecached — alle Provider prüfen ist sonst langsam)."""
    global _LLM_HEALTH_CACHE, _LLM_HEALTH_CACHE_AT
    now = time.monotonic()
    if (
        _LLM_HEALTH_CACHE is not None
        and _LLM_HEALTH_TTL_SEC > 0
        and (now - _LLM_HEALTH_CACHE_AT) < _LLM_HEALTH_TTL_SEC
    ):
        return dict(_LLM_HEALTH_CACHE)

    s = load_merged_settings()
    active = get_active_provider()
    ah = check_provider_health(active["id"])
    per_provider = []
    for p in get_available_providers():
        h = check_provider_health(p["id"])
        per_provider.append(
            {
                "id": p["id"],
                "label": p["label"],
                "reachable": h["reachable"],
                "model": h["model"],
                "chat_available": h["chat_available"],
                "coding_available": h["coding_available"],
                "detail": h.get("detail") or "",
            }
        )
    out: dict[str, Any] = {
        "active_provider": active["id"],
        "active_model": ah.get("model") or active.get("model") or "—",
        "provider_reachable": ah.get("reachable", False),
        "chat_available": ah.get("chat_available", False),
        "coding_available": ah.get("coding_available", False),
        "allow_external": bool(s.get("allow_external")),
        "providers": per_provider,
        "hint_if_unreachable": (
            "Kein lokales Modell erreichbar. Ollama oder LM Studio starten und Modell laden."
            if not ah.get("reachable")
            else ""
        ),
    }
    _LLM_HEALTH_CACHE = out
    _LLM_HEALTH_CACHE_AT = now
    return dict(out)


def _ollama_generate(
    base_url: str,
    model: str,
    system_prompt: str,
    user_text: str,
    *,
    temperature: float,
    num_ctx: int,
    fallback_model: str,
    extra_fallbacks: list[str],
) -> str:
    composed = user_text.strip()
    cache_key = f"ollama|{model}|{hash(composed)}|{hash(system_prompt)}"
    hit = _cache_get(cache_key)
    if hit is not None:
        return hit

    last_error: Any = None

    def _post(mname: str):
        return _SESSION.post(
            f"{base_url}/api/generate",
            json={
                "model": mname,
                "system": system_prompt,
                "prompt": composed,
                "stream": False,
                "temperature": temperature,
                "num_ctx": num_ctx,
            },
            timeout=_TIMEOUT_GEN,
        )

    for attempt in range(max(1, _RETRY + 1)):
        try:
            response = _post(model)
            response.raise_for_status()
            payload = response.json() or {}
            text = str(payload.get("response") or "").strip()
            _cache_set(cache_key, text)
            return text
        except Exception as ex:
            last_error = ex
            if attempt < _RETRY:
                time.sleep(0.35 * (attempt + 1))

    if fallback_model and fallback_model != model:
        try:
            response = _post(fallback_model)
            response.raise_for_status()
            payload = response.json() or {}
            text = str(payload.get("response") or "").strip()
            if text:
                return text
        except Exception as ex:
            last_error = ex

    seen = {model, fallback_model}
    for alt in extra_fallbacks:
        if alt in seen:
            continue
        seen.add(alt)
        try:
            response = _post(alt)
            response.raise_for_status()
            payload = response.json() or {}
            text = str(payload.get("response") or "").strip()
            if text:
                return text
        except Exception as ex:
            last_error = ex
            continue

    return _fmt_err("Ollama", model, last_error, provider_id=PROVIDER_OLLAMA)


def _openai_sdk_chat_completion(
    base_v1_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
) -> str:
    """OpenAI-Python-Client (LM Studio / OpenAI-kompatibel)."""
    base = _normalize_openai_base(base_v1_url).rstrip("/")
    key = str(api_key or "").strip() or "lm-studio"
    client = _OpenAIClient(base_url=base, api_key=key)
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
    )
    ch0 = (resp.choices[0].message.content if resp.choices else None) or ""
    return str(ch0).strip()


def _openai_compatible_generate(
    base_v1_url: str,
    model: str,
    system_prompt: str,
    user_text: str,
    *,
    temperature: float,
    label: str,
    provider_id: str = "",
    max_tokens: int = 2048,
    api_key: Optional[str] = None,
) -> str:
    composed = user_text.strip()
    cache_key = f"{label}|{model}|{hash(composed)}|{hash(system_prompt)}|{max_tokens}|{temperature}"
    hit = _cache_get(cache_key)
    if hit is not None:
        return hit

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": composed},
    ]
    last_error: Any = None

    if _OpenAIClient is not None and api_key is not None:
        for attempt in range(max(1, _RETRY + 1)):
            try:
                text = _openai_sdk_chat_completion(
                    base_v1_url,
                    api_key,
                    model,
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if text:
                    _cache_set(cache_key, text)
                    return text
                last_error = "kein Text (OpenAI SDK)"
            except Exception as ex:
                last_error = ex
                if attempt < _RETRY:
                    time.sleep(0.35 * (attempt + 1))
        # Fallback: HTTP ohne SDK
        last_error = last_error or "OpenAI SDK"

    url = _openai_chat_completions_url(base_v1_url)
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    ak = str(api_key or "").strip()
    if ak:
        headers["Authorization"] = f"Bearer {ak}"

    for attempt in range(max(1, _RETRY + 1)):
        try:
            r = _SESSION.post(url, json=body, headers=headers, timeout=_TIMEOUT_GEN)
            r.raise_for_status()
            data = r.json() or {}
            choices = data.get("choices") or []
            if not choices:
                last_error = "leere Antwort"
                break
            msg = (choices[0] or {}).get("message") or {}
            text = str(msg.get("content") or "").strip()
            if text:
                _cache_set(cache_key, text)
                return text
            last_error = "kein Text in choices"
        except Exception as ex:
            last_error = ex
            if attempt < _RETRY:
                time.sleep(0.35 * (attempt + 1))
    return _fmt_err(label, model, last_error, provider_id=provider_id or "")


def generate_chat_response(prompt: str, extra_context: str = "") -> str:
    """Kurzer Chat (Konversation) über den aktiven lokalen Provider."""
    s = load_merged_settings()
    from system_prompts import SYSTEM_PROMPT_LOKAL_AGENT

    system_prompt = SYSTEM_PROMPT_LOKAL_AGENT
    user_text = str(prompt or "").strip()
    if extra_context:
        user_text = user_text + "\n\nKontext:\n" + extra_context.strip()

    pid = s["active_provider"]
    if pid == PROVIDER_OLLAMA:
        model = _pick_best_ollama_model(s["ollama_base_url"])
        return _ollama_generate(
            s["ollama_base_url"],
            model,
            system_prompt,
            user_text,
            temperature=0.45,
            num_ctx=8192,
            fallback_model=str(s.get("ollama_fallback_model") or ""),
            extra_fallbacks=s.get("ollama_agent_fallbacks") or [],
        )
    if pid == PROVIDER_LM_STUDIO:
        base = s["lm_studio_base_url"]
        model = _openai_pick_model(base, s["lm_studio_model"])
        return _openai_compatible_generate(
            base,
            model,
            system_prompt,
            user_text,
            temperature=0.2,
            label="LM Studio",
            provider_id=PROVIDER_LM_STUDIO,
            max_tokens=2048,
            api_key=s.get("lm_studio_api_key"),
        )
    if pid == PROVIDER_LLAMACPP:
        base = s["llamacpp_base_url"]
        model = _openai_pick_model(base, s["llamacpp_model"])
        return _openai_compatible_generate(
            base,
            model,
            system_prompt,
            user_text,
            temperature=0.45,
            label="llama.cpp",
            provider_id=PROVIDER_LLAMACPP,
        )
    return _fmt_err("Provider", str(pid), "nicht unterstützt", provider_id=str(pid))


_INTENT_CLASSIFIER_SYSTEM = (
    "Du klassifizierst die Nutzerabsicht für eine IDE-KI (Rainer). "
    "Antworte NUR mit einem JSON-Objekt, kein Fließtext, keine Markdown-Codefences.\n"
    "Schema: {\"intent\":\"chat|read|change|unclear\",\"confidence\":0.0,\"reason_de\":\"max 80 Zeichen\"}\n"
    "- chat: Smalltalk, allgemeine Frage, Hilfe ohne konkreten Projektordner\n"
    "- read: Projekt/Code verstehen, Analyse, Erklären, Review, Dateien lesen — keine Änderung am Repo\n"
    "- change: implementieren, fixen, Refactor, Dateien im Projekt schreiben/ändern\n"
    "- unclear: widersprüchlich oder zu wenig Information\n"
    "confidence: 0.0–1.0 wie sicher die Zuordnung ist."
)


def generate_intent_classification_response(user_text: str) -> str:
    """
    Kurze JSON-Intent-Klassifikation (für unklare Prompts). Nutzt lokalen LLM, niedrige Temperatur.
    """
    s = load_merged_settings()
    system_prompt = _INTENT_CLASSIFIER_SYSTEM
    user_text = str(user_text or "").strip()[:12000]
    if not user_text:
        return ""
    _max = int(os.getenv("RAINER_INTENT_LLM_MAX_TOKENS", "220"))
    pid = s["active_provider"]
    if pid == PROVIDER_OLLAMA:
        model = _pick_best_ollama_model(s["ollama_base_url"])
        return _ollama_generate(
            s["ollama_base_url"],
            model,
            system_prompt,
            user_text,
            temperature=0.05,
            num_ctx=4096,
            fallback_model=str(s.get("ollama_fallback_model") or ""),
            extra_fallbacks=s.get("ollama_agent_fallbacks") or [],
        )
    if pid == PROVIDER_LM_STUDIO:
        base = s["lm_studio_base_url"]
        model = _openai_pick_model(base, s["lm_studio_model"])
        return _openai_compatible_generate(
            base,
            model,
            system_prompt,
            user_text,
            temperature=0.05,
            label="Intent",
            provider_id=PROVIDER_LM_STUDIO,
            max_tokens=_max,
            api_key=s.get("lm_studio_api_key"),
        )
    if pid == PROVIDER_LLAMACPP:
        base = s["llamacpp_base_url"]
        model = _openai_pick_model(base, s["llamacpp_model"])
        return _openai_compatible_generate(
            base,
            model,
            system_prompt,
            user_text,
            temperature=0.05,
            label="Intent-llama",
            provider_id=PROVIDER_LLAMACPP,
            max_tokens=_max,
        )
    return _fmt_err("Provider", str(pid), "nicht unterstützt", provider_id=str(pid))


def generate_coding_response(
    prompt: str,
    context: str = "",
    model_override: Optional[str] = None,
    *,
    local_agent_mode: bool = False,
    default_coding_system: Optional[str] = None,
) -> str:
    """
    Ausführlichere Generierung (Coding / Architektur-Stil oder Lokal-Agent-Modus).
    Entspricht dem früheren call_ollama_intelligent-Verhalten.
    """
    s = load_merged_settings()
    default_system = default_coding_system or (
        "Du bist ein Senior Developer und Architect.\n\n"
        "Deine Aufgaben:\n"
        "1. Analysiere das Problem LOGISCH\n"
        "2. Waehle beste Technologie + erklaere WARUM\n"
        "3. Designe optimale Architektur\n"
        "4. Zeige alle Trade-Offs (Pro/Con)\n"
        "5. Schlag Verbesserungen vor\n"
        "6. Generiere Production-Code\n\n"
        "ANTWORTE IM STIL:\n"
        "  🎯 [Problem-Analyse]\n"
        "  🏆 [Tech-Empfehlung mit Begruendung]\n"
        "  🏗️ [Architektur-Design]\n"
        "  ✅ [Trade-Offs: Pro/Con]\n"
        "  💡 [5 Verbesserungsvorschlaege]\n"
        "  [Code-Block mit Production-Code]\n"
        "  ✓ FERTIG! 🚀"
    )
    if local_agent_mode:
        from system_prompts import SYSTEM_PROMPT_LOKAL_AGENT

        system_prompt = SYSTEM_PROMPT_LOKAL_AGENT
    else:
        system_prompt = default_system

    composed_prompt = str(prompt or "").strip()
    extra = str(context or "").strip()
    if extra:
        composed_prompt = composed_prompt + "\n\nKontext:\n" + extra

    pid = s["active_provider"]
    temperature = 0.45 if local_agent_mode else 0.7
    num_ctx = 8192 if local_agent_mode else 4096
    lm_temp = 0.2

    if pid == PROVIDER_OLLAMA:
        model = str(model_override or "").strip() or _pick_best_ollama_model(s["ollama_base_url"])
        return _ollama_generate(
            s["ollama_base_url"],
            model,
            system_prompt,
            composed_prompt,
            temperature=temperature,
            num_ctx=num_ctx,
            fallback_model=str(s.get("ollama_fallback_model") or ""),
            extra_fallbacks=s.get("ollama_agent_fallbacks") if local_agent_mode else [],
        )
    if pid == PROVIDER_LM_STUDIO:
        base = s["lm_studio_base_url"]
        model = str(model_override or "").strip() or _openai_pick_model(base, s["lm_studio_model"])
        # num_ctx nicht direkt in OpenAI-API — ignorieren
        return _openai_compatible_generate(
            base,
            model,
            system_prompt,
            composed_prompt,
            temperature=lm_temp,
            label="LM Studio",
            provider_id=PROVIDER_LM_STUDIO,
            max_tokens=2048,
            api_key=s.get("lm_studio_api_key"),
        )
    if pid == PROVIDER_LLAMACPP:
        base = s["llamacpp_base_url"]
        model = str(model_override or "").strip() or _openai_pick_model(base, s["llamacpp_model"])
        return _openai_compatible_generate(
            base,
            model,
            system_prompt,
            composed_prompt,
            temperature=temperature,
            label="llama.cpp",
            provider_id=PROVIDER_LLAMACPP,
        )
    return _fmt_err("Provider", str(pid), "nicht unterstützt", provider_id=str(pid))


def is_llm_failure_message(text: str) -> bool:
    """True wenn Antwort ein lokaler Verfügbarkeits-/Generierungsfehler ist (⚠️ …)."""
    t = str(text or "").strip()
    return t.startswith("⚠️") and ("nicht erreichbar" in t or "ungueltig" in t)


def generate_image_via_openai(
    *,
    prompt: str,
    size: str = "1024x1024",
    timeout: int = 120,
) -> dict[str, Any]:
    """POST /v1/images/generations (OpenAI-kompatibel). Keys: OPENAI_API_KEY oder RAINER_IMAGE_API_KEY."""
    key = str(os.getenv("RAINER_IMAGE_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return {
            "ok": False,
            "error": "Kein API-Key: OPENAI_API_KEY oder RAINER_IMAGE_API_KEY setzen.",
        }
    base = str(os.getenv("RAINER_IMAGE_BASE_URL") or "https://api.openai.com/v1").strip().rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    model = str(os.getenv("RAINER_IMAGE_MODEL") or "dall-e-3").strip()
    allowed_d3 = {"1024x1024", "1792x1024", "1024x1792"}
    allowed_d2 = {"256x256", "512x512", "1024x1024"}
    sz = str(size or "1024x1024").strip()
    if model.startswith("dall-e-3"):
        if sz not in allowed_d3:
            sz = "1024x1024"
    else:
        if sz not in allowed_d2:
            sz = "1024x1024"
    url = base.rstrip("/") + "/images/generations"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body: dict[str, Any] = {"model": model, "prompt": str(prompt or "").strip(), "n": 1, "size": sz}
    try:
        r = _SESSION.post(url, headers=headers, json=body, timeout=timeout)
        if r.status_code >= 400:
            try:
                err_js = r.json()
                err_obj = err_js.get("error")
                if isinstance(err_obj, dict):
                    err_msg = str(err_obj.get("message") or err_obj)[:800]
                else:
                    err_msg = str(err_obj or err_js)[:800]
            except Exception:
                err_msg = (r.text or str(r.status_code))[:800]
            return {"ok": False, "error": f"Bild-API HTTP {r.status_code}: {err_msg}"}
        data = r.json() or {}
        items = list(data.get("data") or [])
        if not items or not isinstance(items[0], dict):
            return {"ok": False, "error": "Leere Antwort von Bild-API."}
        first = items[0]
        remote = str(first.get("url") or "").strip()
        b64 = str(first.get("b64_json") or "").strip()
        return {
            "ok": True,
            "remote_url": remote,
            "b64_json": b64,
            "provider": "openai_compatible",
            "model": model,
            "size": sz,
        }
    except requests.RequestException as exc:
        return {"ok": False, "error": f"Netzwerkfehler Bild-API: {exc}"}
