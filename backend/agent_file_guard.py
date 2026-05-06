"""
Rainer Build — Coding-Agent-Schutzregeln (Pfad, Patch, keine Prompt-Dumps).

Wird von write_action und main (Pfad-Extraktion) importiert; kein Import von main.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Relativ zu rambo_builder_local — nur Patch/Diff-Logik fuer grosse existierende Dateien
PROTECTED_RELATIVE_SUFFIXES: tuple[str, ...] = (
    "backend/main.py",
    "frontend/app.js",
    "backend/routes.py",
    "backend/write_action.py",
    "backend/agent_file_guard.py",
)

# Ab dieser Groesse einer *bestehenden* Datei: Voller Ersatz nur mit Patch-Markern
PROTECTED_EXISTING_MIN_CHARS = 2500

# Maximale Schreibgroesse (Prompts nicht als Datei speichern)
MAX_PROPOSED_WRITE_CHARS = 1_500_000

RAINER_BUILD_AGENT_RULES_EXTENDED = """
Rainer Build — verbindliche Agent-Regeln (Erweiterung)

0) Lokal-Agent (Ollama): Antworten nur beraten/planen; der Server schreibt aus diesem Chat
   keine Projektdateien. Zum Anwenden von Patches nutzt der Nutzer den Direktmodus (Guards/Apply).

1) Vollständiger Ersatz wichtiger Dateien ist verboten, wenn ein Patch/Diff gemeint ist.
   Nutze unified diff (---/+++/@@), V4A/SEARCH-REPLACE-Blöcke oder kleine, klar begrenzte Snippets.

2) Vor jedem Schreiben: existiert die Datei schon?
   - Ja + geschützter Pfad (backend/main.py, frontend/app.js, …): nur Patch-artige Änderungen
     oder sehr kleine Ersetzungen; sonst Schreiben ablehnen.
   - Nein: neue Datei erlaubt, Inhalt trotzdem kein kompletter Prompt-Text.

3) Große Prompts niemals als Dateiinhalt speichern (kein „Prompt als .txt/.md/.json“-Dump).

4) Zielpfad für lokale Bearbeitung: wenn im Auftrag ZIELORDNER … ENDE_ZIELORDNER steht,
   nur dort enthaltene Pfadangaben verwenden (kein Mischen mit Pfaden ausserhalb des Blocks).

5) backend/main.py, frontend/app.js und weitere Kernmodule nur gemäss Regel 1–2 bearbeiten.

6) Nach erfolgreichem Schreiben: automatisch py_compile (Python) bzw. node --check (JavaScript)
   im Projekt rambo_builder_local — bei Fehler: letzten Inhalt wiederherstellen und Hinweis liefern.

7) Wenn Checks oder Tests fehlschlagen: Wiederherstellung aus Backup (falls vorhanden) und
   konkreter Reparaturvorschlag (Diff prüfen, Zeilenende, Syntax).
""".strip()


def extract_relative_path_from_zielordner_block(task: str) -> str | None:
    """
    Liest ausschliesslich aus einem Block ZIELORDNER ... ENDE_ZIELORDNER (case-insensitive).
    Gibt den ersten plausiblen relativen Pfad unterhalb von rambo_builder_local zurueck.
    """
    raw = str(task or "")
    m = re.search(r"(?is)ZIELORDNER\s*(.*?)ENDE_ZIELORDNER", raw)
    if not m:
        return None
    inner = m.group(1)
    lines_kept = []
    for ln in inner.splitlines():
        tl = ln.strip().lower()
        if not tl:
            continue
        if "irrelevant" in tl or "ignorier" in tl or tl.startswith("#"):
            continue
        lines_kept.append(ln)
    low_inner = "\n".join(lines_kept).replace("\\", "/")
    candidates: list[str] = []
    marker = "rambo_builder_local/"
    pos = 0
    while True:
        ix = low_inner.lower().find(marker, pos)
        if ix < 0:
            break
        tail = low_inner[ix + len(marker) :]
        tail = re.split(r"[\s\"'`<>|,\n\r;]", tail.strip())[0] if tail.strip() else ""
        tail = tail.strip().lstrip("./").replace("\\", "/")
        if tail and ".." not in tail and ":" not in tail.split("/")[0]:
            candidates.append(tail)
        pos = ix + 1
    for line in lines_kept:
        line = line.strip().replace("\\", "/")
        if not line or line.startswith("#"):
            continue
        for pat in (
            r"^([\w./-]+\.(?:py|js|mjs|cjs|ts|tsx|jsx|css|html|json|md|txt|yml|yaml|toml))$",
            r"^(backend/[\w./-]+\.(?:py|js|ts|tsx|jsx|json))$",
            r"^(frontend/[\w./-]+\.(?:js|ts|tsx|jsx|css|html))$",
        ):
            mm = re.match(pat, line, re.IGNORECASE)
            if mm:
                cand = mm.group(1).lstrip("./")
                if ".." not in cand and ":" not in cand:
                    candidates.append(cand)
    for c in candidates:
        c = c.strip().lstrip("./")
        if c and ".." not in c:
            return c
    return None


def _relative_under_rambo_builder(resolved: Path) -> str | None:
    cur = resolved.resolve()
    for p in [cur] + list(cur.parents):
        if p.name == "rambo_builder_local":
            try:
                return cur.relative_to(p).as_posix()
            except ValueError:
                continue
    return None


def is_protected_existing_write(resolved: Path) -> bool:
    rel = _relative_under_rambo_builder(resolved)
    if not rel:
        return False
    low = rel.lower()
    return any(low.endswith(s.lower()) or low == s.lower() for s in PROTECTED_RELATIVE_SUFFIXES)


def _looks_like_patch_or_small_edit(previous: str | None, proposed: str) -> bool:
    t = proposed or ""
    if len(t) < 400 and (previous is None or len(t) <= max(800, int(len(previous or "") * 0.25))):
        return True
    if "*** Begin Patch" in t or "*** Update File" in t:
        return True
    if "\n@@" in t or t.startswith("@@"):
        return True
    if "--- " in t and "+++ " in t:
        return True
    if "diff --git" in t:
        return True
    return False


def validate_write_payload(
    resolved: Path,
    proposed_content: str,
    previous: str | None,
    had_file: bool,
) -> tuple[bool, str | None]:
    """False, Fehlertext wenn Schreiben nicht erlaubt."""
    prop = proposed_content or ""
    if len(prop) > MAX_PROPOSED_WRITE_CHARS:
        return False, (
            f"Schreibabweisung: Inhalt zu gross ({len(prop)} Zeichen). "
            "Grosse Prompts nicht als Datei speichern (Regel 3)."
        )
    if looks_like_full_prompt_dump(prop):
        return False, (
            "Schreibabweisung: Inhalt sieht nach komplettem Auftrags-/Prompt-Text aus (Regel 3). "
            "Bitte nur Zielcode oder Patch liefern."
        )
    if looks_like_instruction_instead_of_code(prop):
        return False, (
            "Schreibabweisung: Inhalt sieht nach Auftrags-/Anweisungstext statt Dateiinhalt aus. "
            "Bitte echten Code/Dateiinhalt oder einen Patch liefern."
        )
    if had_file and looks_like_code_file_downgrade_to_plain_text(resolved, previous, prop):
        return False, (
            "Schreibabweisung: Bestehende Code-Datei wuerde durch Nicht-Code/Prompt-Text ersetzt. "
            "Bitte nur gezielte Codeaenderungen oder Patch anwenden."
        )
    if had_file and is_protected_existing_write(resolved):
        prev = previous or ""
        if len(prev) >= PROTECTED_EXISTING_MIN_CHARS and not _looks_like_patch_or_small_edit(
            previous, prop
        ):
            return False, (
                f"Schreibabweisung: {resolved.name} ist geschuetzt und bereits gross "
                f"({len(prev)} Zeichen). Nur Patch/Diff oder kleine Aenderung (Regeln 1–2, 5)."
            )
    return True, None


def looks_like_full_prompt_dump(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 4000:
        return False
    head = t[:1200].lower()
    markers = (
        "du arbeitest im projekt",
        "du arbeitest im ordner",
        "ziel:",
        "wichtig:",
        "phase 0:",
        "phase 1:",
        "ausgabeformat:",
        "arbeite direkt im ordner",
    )
    hits = sum(1 for m in markers if m in head)
    if hits >= 3:
        return True
    if ("\"task\"" in head or "'task'" in head) and "prompt" in head:
        return True
    return False


def looks_like_instruction_instead_of_code(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    head = t[:600].lower()
    strong_markers = (
        "aufgabe:",
        "entferne in ",
        "nur ausblenden",
        "nicht löschen",
        "nicht löschen.",
        "bitte ändere",
        "bitte aendere",
    )
    marker_hits = sum(1 for m in strong_markers if m in head)
    has_file_path = ("frontend/" in head or "backend/" in head) and (".jsx" in head or ".py" in head or ".js" in head or ".css" in head)
    code_signals = ("import " in head or "export default" in head or "function " in head or "class " in head or "<div" in head)
    if marker_hits >= 2 and has_file_path and not code_signals:
        return True
    if t.count("\n") <= 2 and marker_hits >= 1 and has_file_path and not code_signals:
        return True
    return False


def _looks_like_code_blob(text: str) -> bool:
    t = (text or "").lower()
    if not t.strip():
        return False
    signals = (
        "import ",
        "export ",
        "function ",
        "const ",
        "let ",
        "class ",
        "return ",
        "=>",
        "{",
        "}",
    )
    hits = sum(1 for s in signals if s in t)
    return hits >= 4


def looks_like_code_file_downgrade_to_plain_text(resolved: Path, previous: str | None, proposed: str) -> bool:
    ext = resolved.suffix.lower()
    if ext not in {".js", ".jsx", ".ts", ".tsx", ".py", ".css", ".html"}:
        return False
    prev = previous or ""
    prop = proposed or ""
    if len(prev.strip()) < 40:
        return False
    if not _looks_like_code_blob(prev):
        return False
    if _looks_like_code_blob(prop):
        return False
    low = prop.strip().lower()
    if low.startswith("aufgabe:") or low.startswith("erstellt:") or "schritte:" in low or "notizen:" in low:
        return True
    # auch ohne Marker: sehr kurzer Freitext statt Code in bestehender Code-Datei blocken
    if len(prop.strip()) < 800 and "\n" in prop and (";" not in prop and "{" not in prop and "}" not in prop):
        return True
    return False


def find_rambo_builder_root(resolved: Path) -> Path | None:
    cur = resolved.resolve()
    for p in [cur] + list(cur.parents):
        if p.name == "rambo_builder_local" and (p / "backend").is_dir():
            return p
    return None


def run_post_write_language_checks(resolved: Path) -> tuple[bool, str | None]:
    """
    py_compile fuer .py, node --check fuer .js/.mjs/.cjs unterhalb rambo_builder_local.
    Rueckgabe: (ok, stderr_oder_hinweis)
    """
    suf = resolved.suffix.lower()
    root = find_rambo_builder_root(resolved)
    if not root:
        return True, None
    try:
        resolved.relative_to(root)
    except ValueError:
        return True, None
    if suf == ".py":
        cp = subprocess.run(
            [sys.executable, "-m", "py_compile", str(resolved)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if cp.returncode != 0:
            msg = (cp.stderr or cp.stdout or "py_compile fehlgeschlagen").strip()[:800]
            return False, msg
        return True, None
    if suf in {".js", ".mjs", ".cjs"}:
        cp = subprocess.run(
            ["node", "--check", str(resolved)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if cp.returncode != 0:
            msg = (cp.stderr or cp.stdout or "node --check fehlgeschlagen").strip()[:800]
            return False, msg
        return True, None
    return True, None
