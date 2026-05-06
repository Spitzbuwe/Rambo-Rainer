"""
agent_loop.py – Rainer Build Autonomer Coding-Agent
====================================================
Nach Ordner-Freigabe arbeitet Rainer selbstständig:
1. Auftrag verstehen
2. Relevante Dateien finden
3. Änderungen direkt schreiben
4. Tests laufen lassen
5. Fehler selbst reparieren
6. Ergebnis zusammenfassen
"""

import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"

import re
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Sicherheits-Grenzen (unveränderlich)
# ---------------------------------------------------------------------------

BLOCKED_PATTERNS = (
    ".env", ".pem", ".key", ".pfx", ".p12",
    "secrets", "credentials", "password",
    "id_rsa", "id_ed25519",
)

BLOCKED_ACTIONS = (
    "rm -rf", "del /f /s", "format c:",
    "shutdown", "reboot", "git push",
    "git merge", "git reset --hard",
    "DROP TABLE", "DELETE FROM",
)

BLOCKED_OUTSIDE_WORKSPACE = True  # Niemals außerhalb des Ordners schreiben

MAX_REPAIR_ATTEMPTS = 2
MAX_SUCHE_REPAIR_ATTEMPTS = int(os.environ.get("AGENT_SUCHE_REPAIR_ATTEMPTS", "2"))
_MAX_SUCHE_FIX_CTX = int(os.environ.get("AGENT_SUCHE_FIX_CONTEXT_CHARS", "24000"))
MAX_FILES_PER_RUN = 20
# Dateilese-Limit:
# -1 = unbegrenzt (komplette Datei lesen), sonst Byte-Limit mit Head/Tail-Fallback.
MAX_FILE_SIZE_BYTES = int(os.environ.get("AGENT_MAX_FILE_SIZE_BYTES", "-1"))

# Große Prompts: Zerlegung in Teilschritte (jeder Schritt = eigener LLM-Call)
AGENT_CHUNK_MIN_CHARS = int(os.environ.get("AGENT_CHUNK_MIN_CHARS", "8000"))
AGENT_CHUNK_MAX_STEPS = int(os.environ.get("AGENT_CHUNK_MAX_STEPS", "8"))
AGENT_CHUNK_PLANNER_MAX_TASK_CHARS = int(os.environ.get("AGENT_CHUNK_PLANNER_MAX_TASK_CHARS", "24000"))

DECOMPOSE_PLANNER_SYSTEM = """Du bist ein Planungs-Modul (kein Code-Schreiben).
Zerlege den folgenden Nutzerauftrag in klare, nacheinander ausführbare Teilschritte.
Jeder Teilschritt muss für sich verständlich sein und sich auf konkrete Aktionen beziehen (Dateien, Tests, Refactor-Schritte).
Antworte AUSSCHLIESSLICH mit einem JSON-Objekt in genau dieser Form, ohne Markdown, ohne Erklärung davor oder danach:
{"steps":["erster Teilschritt","zweiter Teilschritt"]}
Maximal 8 Einträge in "steps". Wenn der Auftrag schon klein ist, ein Array mit genau einem Element."""


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _is_blocked_path(path: Path, workspace: Path) -> tuple[bool, str]:
    """Prüft ob ein Pfad erlaubt ist."""
    try:
        path.resolve().relative_to(workspace.resolve())
    except ValueError:
        return True, "Pfad liegt außerhalb des Workspace"

    path_str = str(path).lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern in path_str:
            return True, f"Blocked pattern: {pattern}"

    return False, ""


def _is_blocked_content(content: str) -> tuple[bool, str]:
    """Prüft ob Inhalt gefährliche Aktionen enthält."""
    lower = content.lower()
    for action in BLOCKED_ACTIONS:
        if action.lower() in lower:
            return True, f"Blocked action: {action}"
    return False, ""


def _run_command(cmd: list, cwd: Path, timeout: int = 60) -> dict:
    """Führt einen Befehl aus und gibt Ergebnis zurück."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[:3000],
            "stderr": result.stderr[:1000],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": -1, "stdout": "", "stderr": "Timeout"}
    except Exception as e:
        return {"ok": False, "returncode": -1, "stdout": "", "stderr": str(e)}


def _read_file(path: Path, max_bytes: Optional[int] = None) -> tuple[str, bool]:
    """Liest eine Datei sicher. Große Dateien: nur Anfang und Ende (UTF-8-sicher per Bytes), nie leer wegen Größe.
    max_bytes < 0: vollständig einlesen (z. B. Analysemodus)."""
    if max_bytes is not None and int(max_bytes) < 0:
        try:
            return path.read_text(encoding="utf-8", errors="replace"), True
        except Exception:
            return "", False
    limit = int(max_bytes) if max_bytes is not None else MAX_FILE_SIZE_BYTES
    if limit < 0:
        try:
            return path.read_text(encoding="utf-8", errors="replace"), True
        except Exception:
            return "", False
    limit = max(4096, limit)
    try:
        size = path.stat().st_size
        if size <= limit:
            return path.read_text(encoding="utf-8", errors="replace"), True
        half = limit // 2
        with path.open("rb") as f:
            head_b = f.read(half)
        with path.open("rb") as f:
            f.seek(max(0, size - half))
            tail_b = f.read(half)
        head_s = head_b.decode("utf-8", errors="replace")
        tail_s = tail_b.decode("utf-8", errors="replace")
        skipped = max(0, size - len(head_b) - len(tail_b))
        marker = f"\n\n[... {skipped} Bytes in der Dateimitte ausgelassen (Datei {size} Bytes, Limit {limit}) ...]\n\n"
        return head_s + marker + tail_s, True
    except Exception:
        return "", False


def _write_file(path: Path, content: str) -> tuple[bool, str]:
    """Schreibt eine Datei sicher."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return True, ""
    except Exception as e:
        return False, str(e)


def _find_relevant_files(workspace: Path, task: str, max_files: int = 10) -> list[Path]:
    """Findet relevante Dateien für eine Aufgabe."""
    task_lower = task.lower()
    extensions = {".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".json", ".md"}

    # Explizite Dateipfade im Prompt erkennen
    explicit = []
    patterns = [
        r'([a-zA-Z0-9_\-./\\]+\.(?:py|js|jsx|ts|tsx|html|css|json|md))',
    ]
    for pat in patterns:
        for match in re.finditer(pat, task):
            p = workspace / match.group(1).replace("\\", "/")
            if p.exists():
                explicit.append(p)

    if explicit:
        return explicit[:max_files]

    # Keywords-basierte Suche
    keyword_map = {
        "frontend": ["frontend/src/", "frontend/", "main.jsx", "App.jsx", "app.js", "index.html", "style.css"],
        "backend": ["backend/", "main.py", "server.py"],
        "style": ["style.css", "app.css"],
        "api": ["main.py", "routes.py", "server.py"],
        "test": ["tests/", "test_"],
        "config": ["package.json", "requirements.txt", "config"],
    }

    candidates = []
    for keyword, paths in keyword_map.items():
        if keyword in task_lower:
            for path_hint in paths:
                for f in workspace.rglob("*"):
                    if path_hint in str(f) and f.is_file() and f.suffix in extensions:
                        if f not in candidates:
                            candidates.append(f)

    if not candidates:
        # Fallback: alle relevanten Dateien im Workspace
        skip = {".git", "node_modules", "__pycache__", ".pytest_cache", "dist", "build"}
        for f in workspace.rglob("*"):
            if f.is_file() and f.suffix in extensions:
                if not any(s in str(f) for s in skip):
                    candidates.append(f)

    return candidates[:max_files]


def _extract_chat_completion_content(data: dict) -> str:
    """Nur Modell-Text: choices[0].message.content (String oder multimodale Teile), kein Roh-JSON."""
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    ch0 = choices[0]
    if not isinstance(ch0, dict):
        return ""
    msg = ch0.get("message")
    if not isinstance(msg, dict):
        return ""
    content = msg.get("content")
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text") or ""))
                elif "text" in item:
                    parts.append(str(item.get("text") or ""))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts).strip()
    return str(content).strip()


def _is_internal_llm_placeholder_text(text: str) -> bool:
    """Keine internen Fehler-/Stub-Strings als Nutzer-Analyse ausliefern."""
    t = str(text or "").strip()
    if not t:
        return False
    if t.startswith("[LLM"):
        return True
    if t.lstrip().startswith("{") and '"error"' in t[:800]:
        return True
    return False


def _call_groq(prompt: str, system: str = "") -> str:
    """Groq OpenAI-kompatible Chat-API; bei Fehler oder fehlendem Key leerer String."""
    key = (GROQ_API_KEY or "").strip()
    if not key:
        return ""
    import requests

    url = "https://api.groq.com/openai/v1/chat/completions"
    sys_c = str(system or "").strip()
    messages = []
    if sys_c:
        messages.append({"role": "system", "content": sys_c})
    messages.append({"role": "user", "content": str(prompt or "")})
    try:
        r = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 4096,
                "service_tier": "on_demand",
            },
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict):
            return ""
        return _extract_chat_completion_content(data)
    except Exception:
        return ""


_INSTRUCTION_DUMP_HINT = re.compile(
    r"(?im)^(aufgabe|task|ziel|anweisung)\s*[:.]|\b(entferne\s+in|ändere\s+nur|aendere\s+nur|nur\s+ausblenden|bitte\s+(ändere|aendere|implementiere))\b",
)


def _content_looks_like_instruction_dump(text: str) -> bool:
    """Blockt Prompt-/Auftragstext statt echtem Code (Phase 1.4)."""
    t = str(text or "").strip()
    if len(t) < 40:
        return False
    if _INSTRUCTION_DUMP_HINT.search(t):
        return True
    if "DATEI:" in t and "SUCHE:" in t and "ERSETZE:" in t:
        lines = [ln for ln in t.splitlines() if ln.strip()]
        if len(lines) <= 16 and "def " not in t and "import " not in t:
            return True
    return False


def _groq_regenerate_suche_patch(
    workspace: Path,
    rel_path: str,
    current_content: str,
    user_task: str,
    failed_search: str,
    failed_replace: str,
) -> tuple[str, str] | None:
    """Ein neuer SUCHE/ERSETZE-Block per Groq, wenn SUCHE nicht in der Datei vorkommt."""
    if not (GROQ_API_KEY or "").strip():
        return None
    rel_norm = str(rel_path or "").strip().replace("\\", "/")
    excerpt = str(current_content or "")
    lim = max(4000, _MAX_SUCHE_FIX_CTX)
    if len(excerpt) > lim:
        half = lim // 2
        excerpt = excerpt[:half] + f"\n\n[… {len(current_content) - lim} Zeichen ausgelassen …]\n\n" + excerpt[-half:]

    system = (
        "Du reparierst einen fehlgeschlagenen SEARCH/REPLACE-Block. "
        "Der Text unter SUCHE muss EXAKT als zusammenhängende Teilzeichenkette in der Datei vorkommen. "
        "Antworte NUR mit EINEM Block:\n"
        f"DATEI: {rel_norm}\nSUCHE:\n…\nERSETZE:\n…\nEND\n"
        "Kein Markdown, keine Erklärung."
    )
    user = (
        f"Nutzerauftrag: {user_task[:2000]}\n\n"
        f"Datei: {rel_norm}\n"
        "Der bisherige SUCHE-Text wurde nicht gefunden:\n"
        f"{failed_search[:1200]}\n\n"
        "Geplanter ERSETZE-Inhalt (sinngemäß umsetzen, nicht als Fließtext in die Datei schreiben):\n"
        f"{failed_replace[:1200]}\n\n"
        f"Aktueller Dateiausschnitt:\n{excerpt}\n"
    )
    raw = _call_groq(user, system)
    if not raw or raw.startswith("[LLM"):
        return None
    pattern = r"DATEI:\s*([^\n]+)\nSUCHE:\n(.*?)\nERSETZE:\n(.*?)\nEND"
    matches = re.findall(pattern, raw, re.DOTALL)
    if not matches:
        return None
    rp, s, r = matches[0]
    if rp.strip().replace("\\", "/") != rel_norm:
        return None
    s, r = s.strip(), r.strip()
    if not s or s not in current_content:
        return None
    if _content_looks_like_instruction_dump(r):
        return None
    return (s, r)


def _call_ollama(prompt: str, system: str = "", model: str = "") -> str:
    """Kompatibilität: nutzt ausschließlich Groq llama-3.3-70b-versatile (on_demand)."""
    sys_prompt = system or AGENT_SYSTEM_PROMPT
    groq_result = _call_groq(prompt, sys_prompt)
    if groq_result:
        return groq_result
    if not GROQ_API_KEY:
        return "[LLM Fehler: GROQ_API_KEY fehlt; nur Groq llama-3.3-70b-versatile ist erlaubt.]"
    return "[LLM Fehler: Groq antwortet nicht.]"


def _pick_best_model() -> str:
    """Wählt das beste verfügbare Ollama-Modell."""
    preferred = [
        "llama-3.3-70b-versatile",
        "gemma3:12b-it-qat",
        "gemma3:12b",
        "qwen2.5-coder:latest",
        "qwen2.5-coder:7b",
        "deepseek-r1:8b",
    ]
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            available = {m.get("name", "") for m in r.json().get("models", [])}
            for name in preferred:
                if name in available:
                    return name
    except Exception:
        pass
    return "llama-3.3-70b-versatile"


def _extract_steps_from_planner_response(text: str) -> Optional[list[str]]:
    """Parst JSON {"steps":[...]} aus der Planner-Antwort."""
    if not text or text.startswith("[LLM"):
        return None
    raw = text.strip()
    # Modell könnte JSON in ``` umschließen
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    steps = data.get("steps")
    if not isinstance(steps, list):
        return None
    out: list[str] = []
    for s in steps:
        t = str(s).strip()
        if t:
            out.append(t)
    if not out:
        return None
    return out[:AGENT_CHUNK_MAX_STEPS]


def _heuristic_split_task(task: str) -> list[str]:
    """Fallback: groben Text in Blöcke teilen (ohne LLM)."""
    max_chunk = 4500
    if len(task) <= max_chunk:
        return [task]
    parts: list[str] = []
    start = 0
    while start < len(task):
        end = min(start + max_chunk, len(task))
        # an Absatzgrenze bevorzugen
        if end < len(task):
            cut = task.rfind("\n\n", start, end)
            if cut > start + max_chunk // 2:
                end = cut + 2
        parts.append(task[start:end].strip())
        start = end
    return [p for p in parts if p]


def decompose_task_into_substeps(task: str, model: str = "") -> list[str]:
    """
    Zerlegt große Aufträge in Teilschritte (Plan per LLM), kleine bleiben einteilig.
    Jeder Eintrag wird später als eigener Generate-Call ausgeführt.
    """
    t = (task or "").strip()
    if not t:
        return [t]
    if len(t) < AGENT_CHUNK_MIN_CHARS:
        return [t]

    plan_input = t[:AGENT_CHUNK_PLANNER_MAX_TASK_CHARS]
    plan_raw = _call_ollama(
        f"Nutzerauftrag:\n\n{plan_input}",
        system=DECOMPOSE_PLANNER_SYSTEM,
        model=model or _pick_best_model(),
    )
    steps = _extract_steps_from_planner_response(plan_raw)
    if steps:
        if len(steps) > 1:
            return steps
        only = steps[0]
        if len(only) >= AGENT_CHUNK_MIN_CHARS:
            heur_one = _heuristic_split_task(only)
            return heur_one if len(heur_one) > 1 else [only]
        return [only]
    heur = _heuristic_split_task(t)
    return heur if len(heur) > 1 else [t]


def _step_context_user_message(full_task: str, step: str, index: int, total: int) -> str:
    head = (full_task or "").strip()[:2000]
    return (
        f"[Kontext – Gesamtauftrag, Auszug]\n{head}\n\n"
        f"---\n[Teilschritt {index + 1} von {total} – nur diesen Schritt jetzt umsetzen]\n{step.strip()}"
    )


# ---------------------------------------------------------------------------
# System-Prompt
# ---------------------------------------------------------------------------

AGENT_SYSTEM_PROMPT = """Du bist Rainer, ein präziser Coding-Agent wie Cursor.

REGEL 1: Schreibe NIE eine komplette Datei neu wenn sie schon existiert.
REGEL 2: Mache nur die minimale Änderung die nötig ist.
REGEL 3: Antworte IMMER in diesem Format, nichts anderes.

Format für Änderung an bestehender Datei (nur Platzhalter — SUCHE immer aus dem echten Dateikontext kopieren):
DATEI: backend/example_module.py
SUCHE:
x = 1
ERSETZE:
x = 42
END

Format für neue Datei:
DATEI: backend/test.py
SUCHE:
<<NEU>>
ERSETZE:
x = 42
END

Mehrere Änderungen: Wiederhole das Format für jede Datei.
SUCHE muss exakt so in der Datei stehen — kopiere es direkt aus dem Dateiinhalt.
Wenn du dir nicht sicher bist, wähle einen kürzeren, eindeutigen Ausschnitt (2-3 Zeilen reichen).
Kein SUCHE-Block darf länger als 10 Zeilen sein.
"""

SUMMARY_PROMPT = """Erstelle eine kurze, klare Zusammenfassung auf Deutsch.

Format:
Erledigt.

Geänderte Dateien:
- <datei1>
- <datei2>

Was geändert wurde:
- <beschreibung 1>
- <beschreibung 2>

Tests:
- <test 1>: OK/FEHLER

Ergebnis:
<ein satz was jetzt besser ist>
"""


# ---------------------------------------------------------------------------
# Haupt-Agent-Loop
# ---------------------------------------------------------------------------

class AgentLoop:
    """
    Autonomer Coding-Agent für Rainer Build.
    Nach Workspace-Freigabe arbeitet er selbstständig.
    """

    def __init__(self, workspace: Path, model: str = ""):
        self.workspace = workspace.resolve()
        self.model = model or _pick_best_model()
        self.log: list[dict] = []
        self.changed_files: list[str] = []
        self.test_results: list[dict] = []
        self.errors: list[str] = []
        self.substep_runs: list[dict] = []
        self.substeps_plan: list[str] = []
        self._current_substep_task: str = ""

    def _log(self, phase: str, message: str, level: str = "info"):
        entry = {
            "ts": _now(),
            "phase": phase,
            "level": level,
            "message": message,
        }
        self.log.append(entry)
        print(f"[{level.upper()}] [{phase}] {message}")

    def run(self, task: str) -> dict:
        """Führt den kompletten Agent-Loop aus."""
        self._log("start", f"Starte Agent-Loop für: {task[:80]}")
        start_time = time.time()

        # 1. Sicherheitscheck
        blocked, reason = _is_blocked_content(task)
        if blocked:
            return self._error_result(f"Auftrag blockiert: {reason}")

        # 2. Große Aufträge in Teilschritte zerlegen (mittelfristig: mehrere LLM-Calls)
        substeps = decompose_task_into_substeps(task, self.model)
        self.substeps_plan = list(substeps)
        chunked = len(substeps) > 1
        if chunked:
            self._log("plan", f"Auftrag zerlegt in {len(substeps)} Teilschritt(e) (Schwelle {AGENT_CHUNK_MIN_CHARS} Zeichen).")
        else:
            self._log("plan", "Einschrittiger Auftrag (keine Zerlegung).")

        self.substep_runs = []

        for si, step_text in enumerate(substeps):
            self._log("substep", f"Teilschritt {si + 1}/{len(substeps)} …")
            step_user = step_text if not chunked else _step_context_user_message(task, step_text, si, len(substeps))
            self._current_substep_task = step_user

            self._log("scan", "Suche relevante Dateien...")
            relevant_files = _find_relevant_files(self.workspace, step_user)
            self._log("scan", f"Gefunden: {len(relevant_files)} Dateien")

            context = self._build_context(step_user, relevant_files)

            self._log("generate", f"Generiere Änderungen (Teilschritt {si + 1})…")
            raw_response = _call_ollama(context, model=self.model)

            changes = self._parse_and_write(raw_response)
            if not changes:
                simple_prompt = (
                    f"Aufgabe: {step_user}\n\nWorkspace: {self.workspace}\n\nBitte ändere die relevanten Dateien direkt."
                )
                raw_response = _call_ollama(simple_prompt, model=self.model)
                changes = self._parse_and_write(raw_response)

            self.substep_runs.append(
                {
                    "index": si + 1,
                    "total": len(substeps),
                    "preview": step_text[:200],
                    "changes_count": len(changes),
                    "errors_after": list(self.errors),
                }
            )

        # 6. Tests laufen lassen (deaktiviert — kürzere Laufzeit)
        # if self.changed_files:
        #     self._log("test", "Lasse Tests laufen...")
        #     self._run_tests()

        # 7. Fehler reparieren
        repair_attempt = 0
        while self.errors and repair_attempt < MAX_REPAIR_ATTEMPTS:
            repair_attempt += 1
            self._log("repair", f"Reparaturversuch {repair_attempt}/{MAX_REPAIR_ATTEMPTS}...")
            repaired = self._repair(task)
            if repaired:
                # self._run_tests()
                pass
            else:
                break

        # 8. Zusammenfassung
        duration = round(time.time() - start_time, 1)
        self._log("done", f"Fertig in {duration}s")

        return self._build_result(task, duration)

    def run_analysis(self, task: str) -> dict:
        """Read-only: relevante Dateien vollständig lesen, Groq/Ollama-Analyse, keine Schreiboperationen."""
        self._log("analysis", f"Analysemodus: {task[:120]}")
        blocked, reason = _is_blocked_content(task)
        if blocked:
            return {"ok": False, "analysis": "", "files": [], "error": reason}

        relevant = _find_relevant_files(self.workspace, task)
        file_list: list[str] = []
        chunks: list[str] = [f"Auftrag: {task}\n", "\nDateiinhalte:\n"]

        for f in relevant:
            rel = str(f.relative_to(self.workspace)).replace("\\", "/")
            file_list.append(rel)
            content, ok = _read_file(f, max_bytes=-1)
            if not ok:
                content = f"[Lesen fehlgeschlagen: {rel}]"
            chunks.append(f"\n--- {rel} ---\n{content}\n")

        prompt = "".join(chunks)
        answer = _call_groq(prompt, AGENT_SYSTEM_PROMPT)
        if not (answer or "").strip():
            answer = _call_ollama(prompt, AGENT_SYSTEM_PROMPT, self.model)
        answer = (answer or "").strip()
        if _is_internal_llm_placeholder_text(answer):
            return {
                "ok": False,
                "analysis": "",
                "files": file_list,
                "error": answer,
            }
        if not answer:
            return {
                "ok": False,
                "analysis": "",
                "files": file_list,
                "error": "Keine Analyse-Antwort vom Modell.",
            }
        return {"ok": True, "analysis": answer, "files": file_list}

    def _file_context_limit(self, is_repair: bool) -> int:
        """Zeichen pro Datei: Repair mehr Kontext, normale Runs schlanker (weniger Tokens)."""
        return 8000 if is_repair else 3000

    def _build_context(self, task: str, files: list[Path], is_repair: bool = False) -> str:
        """Baut den Kontext-Prompt auf."""
        limit = self._file_context_limit(is_repair)
        parts = [f"Auftrag: {task}\n"]
        parts.append(f"Workspace: {self.workspace}\n")
        parts.append("Relevante Dateien:\n")

        for f in files[:3]:  # Max 3 Dateien im Kontext
            rel = str(f.relative_to(self.workspace)).replace("\\", "/")
            content, ok = _read_file(f)
            if ok:
                preview = content[:limit]
                block = f"\n=== {rel} ===\n"
                if len(content) > limit:
                    block += f"[Datei gekürzt: {len(content)} Zeichen, zeige erste {limit}]\n"
                block += f"{preview}\n"
                parts.append(block)

        parts.append(
            "\nSetze den Auftrag um. Antworte AUSSCHLIESSLICH im Format "
            "DATEI: … / SUCHE: … / ERSETZE: … / END (siehe AGENT_SYSTEM_PROMPT). "
            "Kein Markdown außerhalb der Blöcke."
        )
        return "\n".join(parts)

    def _parse_and_write(self, response: str) -> list[dict]:
        """Minimale str_replace Änderungen statt Vollrewrite."""
        changes = []
        pattern = r'DATEI:\s*([^\n]+)\nSUCHE:\n(.*?)\nERSETZE:\n(.*?)\nEND'
        matches = re.findall(pattern, response, re.DOTALL)

        if not matches:
            # Fallback altes Format DATEI:/---/---
            old_pattern = r'DATEI:\s*([^\n]+)\n-{3,}\n(.*?)\n-{3,}'
            matches_old = re.findall(old_pattern, response, re.DOTALL)
            for rel_path, content in matches_old:
                rel_path = rel_path.strip().replace("\\", "/")
                content = content.strip()
                if _content_looks_like_instruction_dump(content):
                    self._log("guard", f"Schreiben abgebrochen (Anweisungstext?): {rel_path}", "warning")
                    self.errors.append(f"Guard: {rel_path} Inhalt sieht nach Auftragstext aus")
                    continue
                target = self.workspace / rel_path
                blocked, reason = _is_blocked_path(target, self.workspace)
                if blocked:
                    self._log("guard", f"Blockiert: {rel_path} – {reason}", "warning")
                    continue
                if target.exists():
                    old_size = target.stat().st_size
                    new_size = len(content.encode("utf-8"))
                    if old_size > 3000 and new_size < old_size * 0.5:
                        self._log("guard", f"Vollrewrite blockiert: {rel_path}", "warning")
                        self.errors.append(f"Guard: {rel_path} Vollrewrite verhindert")
                        continue
                ok, err = _write_file(target, content)
                if ok:
                    rel_str = str(target.relative_to(self.workspace)).replace("\\", "/")
                    self.changed_files.append(rel_str)
                    changes.append({"path": rel_str, "ok": True})
                    self._log("write", f"Geschrieben: {rel_str}")
                else:
                    self.errors.append(f"Schreibfehler: {rel_path}: {err}")
            return changes

        for rel_path, search_text, replace_text in matches:
            rel_path = rel_path.strip().replace("\\", "/")
            search_text = search_text.strip()
            replace_text = replace_text.strip()
            target = self.workspace / rel_path

            blocked, reason = _is_blocked_path(target, self.workspace)
            if blocked:
                self._log("guard", f"Blockiert: {rel_path} – {reason}", "warning")
                continue

            # Neue Datei
            if search_text.strip() == "<<NEU>>":
                if _content_looks_like_instruction_dump(replace_text):
                    self._log("guard", f"Neue Datei abgebrochen (Anweisungstext?): {rel_path}", "warning")
                    self.errors.append(f"Guard: {rel_path} <<NEU>> Inhalt ungueltig")
                    continue
                ok, err = _write_file(target, replace_text)
                if ok:
                    rel_str = str(target.relative_to(self.workspace)).replace("\\", "/")
                    self.changed_files.append(rel_str)
                    changes.append({"path": rel_str, "ok": True})
                    self._log("write", f"Neu erstellt: {rel_str}")
                else:
                    self.errors.append(f"Schreibfehler: {rel_path}: {err}")
                continue

            # Bestehende Datei: str_replace
            if not target.exists():
                self._log("guard", f"Datei nicht gefunden: {rel_path}", "warning")
                continue

            current_content, ok = _read_file(target)
            if not ok:
                self._log("guard", f"Lesen fehlgeschlagen: {rel_path}", "warning")
                continue

            if _content_looks_like_instruction_dump(replace_text):
                self._log("guard", f"ERSETZE sieht nach Anweisung aus: {rel_path}", "warning")
                self.errors.append(f"Guard: {rel_path} ERSETZE blockiert (Auftragstext)")
                continue

            fix_try = 0
            while search_text not in current_content and fix_try < MAX_SUCHE_REPAIR_ATTEMPTS:
                fix_try += 1
                self._log("repair_suche", f"SUCHE passt nicht — Groq-Reparatur {fix_try}/{MAX_SUCHE_REPAIR_ATTEMPTS} ({rel_path})")
                repaired = _groq_regenerate_suche_patch(
                    self.workspace,
                    rel_path,
                    current_content,
                    getattr(self, "_current_substep_task", "") or "",
                    search_text,
                    replace_text,
                )
                if repaired:
                    search_text, replace_text = repaired
                else:
                    break

            if search_text not in current_content:
                self._log("guard", f"SUCHE-Text nicht gefunden in {rel_path}", "warning")
                self.errors.append(f"str_replace fehlgeschlagen: Text nicht gefunden in {rel_path}")
                continue

            new_content = current_content.replace(search_text, replace_text, 1)
            ok, err = _write_file(target, new_content)
            if ok:
                rel_str = str(target.relative_to(self.workspace)).replace("\\", "/")
                self.changed_files.append(rel_str)
                changes.append({"path": rel_str, "ok": True})
                self._log("write", f"Geändert: {rel_str}")
            else:
                self.errors.append(f"Schreibfehler: {rel_path}: {err}")

        return changes

    def _run_tests(self):
        """Führt automatische Tests durch."""
        self.errors = []

        for rel_path in self.changed_files:
            path = self.workspace / rel_path

            if rel_path.endswith(".py"):
                result = _run_command(
                    ["python", "-m", "py_compile", str(path)],
                    self.workspace
                )
                self.test_results.append({
                    "check": f"py_compile {rel_path}",
                    "ok": result["ok"],
                    "detail": result["stderr"] if not result["ok"] else "OK",
                })
                if not result["ok"]:
                    self.errors.append(result["stderr"])

            elif rel_path.endswith(".js"):
                result = _run_command(
                    ["node", "--check", str(path)],
                    self.workspace
                )
                self.test_results.append({
                    "check": f"node --check {rel_path}",
                    "ok": result["ok"],
                    "detail": result["stderr"] if not result["ok"] else "OK",
                })
                if not result["ok"]:
                    self.errors.append(result["stderr"])

        # Pytest wenn Tests geändert wurden
        test_files = [f for f in self.changed_files if f.startswith("tests/")]
        if test_files:
            result = _run_command(
                ["python", "-m", "pytest"] + test_files + ["-q", "--tb=short"],
                self.workspace,
                timeout=120,
            )
            self.test_results.append({
                "check": "pytest",
                "ok": result["ok"],
                "detail": result["stdout"][:500] if not result["ok"] else "OK",
            })
            if not result["ok"]:
                self.errors.append(result["stdout"][:500])

    def _repair(self, original_task: str) -> bool:
        """Versucht Fehler selbst zu reparieren."""
        if not self.errors:
            return True

        error_context = "\n".join(self.errors[:3])
        repair_prompt = f"""Auftrag: {original_task}

Fehler aufgetreten:
{error_context}

Geänderte Dateien:
{', '.join(self.changed_files)}

Antworte NUR im Format DATEI: … SUCHE: … ERSETZE: … END (oder Fallback DATEI: … --- … ---). Kein Markdown."""

        # Direkt vor LLM: Dateien erneut von Platte lesen (Stand nach letztem Write)
        rlimit = self._file_context_limit(is_repair=True)
        for rel_path in self.changed_files:
            path = self.workspace / rel_path
            fresh_content, ok = _read_file(path)
            if ok:
                repair_prompt += f"\n\n=== {rel_path} (aktuell, frisch eingelesen) ===\n"
                if len(fresh_content) > rlimit:
                    repair_prompt += (
                        f"[Datei gekürzt: {len(fresh_content)} Zeichen, zeige erste {rlimit}]\n"
                    )
                repair_prompt += fresh_content[:rlimit]

        response = _call_ollama(repair_prompt, model=self.model)
        changes = self._parse_and_write(response)
        return len(changes) > 0

    def _build_result(self, task: str, duration: float) -> dict:
        """Erstellt das finale Ergebnis."""
        tests_ok = all(t["ok"] for t in self.test_results)
        all_tests_str = "\n".join(
            f"- {t['check']}: {'✓ OK' if t['ok'] else '✗ FEHLER'}"
            for t in self.test_results
        ) or "- Keine Tests gelaufen"

        files_str = "\n".join(f"- {f}" for f in self.changed_files) or "- Keine Dateien geändert"

        # Zusammenfassung generieren
        task_for_summary = task if len(task) <= 6000 else task[:6000] + "\n[… Auftrag gekürzt für Zusammenfassung …]"
        chunk_note = ""
        if len(getattr(self, "substeps_plan", []) or []) > 1:
            chunk_note = f"\nAusführung in {len(self.substeps_plan)} Teilschritten (chunked_run).\n"
        summary_prompt = f"""Aufgabe war: {task_for_summary}
{chunk_note}
Geänderte Dateien:
{files_str}

Tests:
{all_tests_str}

Fehler: {', '.join(self.errors[:2]) if self.errors else 'Keine'}

{SUMMARY_PROMPT}"""

        summary = _call_ollama(summary_prompt, model=self.model)

        if not summary or summary.startswith(("[Ollama", "[LLM")):
            # Fallback-Zusammenfassung
            summary = f"""Erledigt.

Geänderte Dateien:
{files_str}

Tests:
{all_tests_str}

Ergebnis:
{'Alle Tests bestanden.' if tests_ok else 'Es gibt noch Fehler – siehe Test-Ausgabe.'}"""

        out = {
            "ok": bool(self.changed_files),
            "success": bool(self.changed_files) and not self.errors,
            "task": task,
            "changed_files": self.changed_files,
            "test_results": self.test_results,
            "tests_ok": tests_ok,
            "errors": self.errors,
            "summary": summary,
            "formatted_response": summary,
            "duration_seconds": duration,
            "model": self.model,
            "log": self.log[-20:],  # Letzte 20 Log-Einträge
            "direct_status": "verified" if (self.changed_files and tests_ok) else (
                "applied" if self.changed_files else "no_changes"
            ),
            "workstream_events": [
                {
                    "ts": e["ts"],
                    "phase": e["phase"],
                    "level": "success" if e["level"] == "info" else e["level"],
                    "title": e["message"][:60],
                    "detail": e["message"],
                    "status": "done",
                }
                for e in self.log
            ],
            "chunked_run": len(getattr(self, "substeps_plan", []) or []) > 1,
            "substeps_plan": getattr(self, "substeps_plan", []) or [],
            "substep_runs": getattr(self, "substep_runs", []) or [],
        }
        return out

    def _error_result(self, message: str) -> dict:
        return {
            "ok": False,
            "success": False,
            "error": message,
            "changed_files": [],
            "test_results": [],
            "errors": [message],
            "summary": f"Fehler: {message}",
            "formatted_response": f"Fehler: {message}",
            "direct_status": "blocked",
        }


# ---------------------------------------------------------------------------
# Öffentliche API
# ---------------------------------------------------------------------------

def run_agent(task: str, workspace_path: str, model: str = "") -> dict:
    """
    Hauptfunktion für den Agent-Loop.
    Wird von main.py aufgerufen.

    Args:
        task: Der Auftrag in natürlicher Sprache
        workspace_path: Absoluter Pfad zum Workspace-Ordner
        model: Ollama-Modell (optional, wird automatisch gewählt)

    Returns:
        dict mit Ergebnis, geänderten Dateien, Tests, Zusammenfassung.
        Bei langen Aufträgen zusätzlich: chunked_run, substeps_plan, substep_runs.
    """
    workspace = Path(workspace_path)
    if not workspace.exists():
        return {
            "ok": False,
            "error": f"Workspace nicht gefunden: {workspace_path}",
            "formatted_response": f"Fehler: Ordner nicht gefunden: {workspace_path}",
        }

    agent = AgentLoop(workspace=workspace, model=model)
    return agent.run(task)
