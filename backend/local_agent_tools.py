"""
Nur-Lesen-Werkzeuge fuer den Lokal-Agent (kein Schreiben, kein freies Shell).

Alle Pfade relativ zum uebergebenen Projekt-Root (rambo_builder_local).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

SKIP_DIR_PARTS = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "dist-installer",
        ".venv",
        "venv",
    }
)


def normalize_project_rel(rel: str) -> str | None:
    """Oeffentliche Pfad-Normalisierung relativ zum Projektroot."""
    return _normalize_rel(rel)


def _normalize_rel(rel: str) -> str | None:
    r = str(rel or "").strip().replace("\\", "/").lstrip("./")
    if not r or ".." in r.split("/"):
        return None
    if r.startswith("/") or ":" in r.split("/", 1)[0]:
        return None
    return r


def safe_read_project_file(root: Path, rel: str, max_chars: int = 16_000) -> tuple[bool, str]:
    rel_clean = _normalize_rel(rel)
    if not rel_clean:
        return False, "Ungueltiger relativer Pfad."
    root = root.resolve()
    path = (root / rel_clean).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return False, "Pfad liegt ausserhalb des Projektroots."
    if not path.is_file():
        return False, "Datei nicht gefunden."
    try:
        size = path.stat().st_size
    except OSError as e:
        return False, str(e)
    if size > 2_000_000:
        return False, "Datei zu gross (>2MB); bitte kleinere Datei oder anderen Ausschnitt."
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return False, str(e)
    max_chars = max(256, min(int(max_chars or 16_000), 100_000))
    if len(text) > max_chars:
        head = max_chars // 4
        tail = max_chars - head
        text = text[:head] + "\n\n...[MITTE GEKUERZT]...\n\n" + text[-tail:]
    return True, text


def safe_search_project(
    root: Path,
    pattern: str,
    glob_pat: str = "*.py",
    *,
    max_matches: int = 40,
    max_files: int = 500,
    max_line_len: int = 400,
) -> tuple[bool, str]:
    pat = str(pattern or "").strip()
    if not pat or len(pat) > 240:
        return False, "Suchbegriff fehlt oder zu lang."
    g = str(glob_pat or "*.py").strip() or "*.py"
    if ".." in g or g.startswith("/"):
        return False, "Glob ungueltig."
    if "**" not in g:
        glob_full = "**/" + g.lstrip("/")
    else:
        glob_full = g
    root = root.resolve()
    max_matches = max(1, min(int(max_matches), 200))
    max_files = max(1, min(int(max_files), 2000))
    rg = None
    for cand in ("rg", "rg.exe"):
        try:
            p = subprocess.run(
                [cand, "--version"],
                capture_output=True,
                text=True,
                timeout=3,
                cwd=str(root),
            )
            if p.returncode == 0:
                rg = cand
                break
        except (OSError, subprocess.TimeoutExpired):
            continue
    if rg:
        try:
            cp = subprocess.run(
                [
                    rg,
                    "-n",
                    "--glob",
                    g,
                    "--max-count",
                    str(max_matches),
                    "--max-filesize",
                    "800K",
                    pat,
                    ".",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(root),
            )
            out = (cp.stdout or "").strip()
            if cp.returncode not in (0, 1):
                err = (cp.stderr or cp.stdout or "rg fehlgeschlagen")[:800]
                return False, err
            if not out:
                return True, "(keine Treffer)"
            lines = out.splitlines()[:max_matches]
            return True, "\n".join(lines)
        except subprocess.TimeoutExpired:
            return False, "Suche-Timeout."
        except OSError as e:
            return False, str(e)
    # Fallback: reine Python-Suche
    hits: list[str] = []
    n_files = 0
    try:
        for path in root.glob(glob_full):
            if n_files >= max_files:
                hits.append("(Suche abgebrochen: Dateilimit)")
                break
            try:
                if not path.is_file():
                    continue
            except OSError:
                continue
            if any(part in SKIP_DIR_PARTS for part in path.parts):
                continue
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                continue
            if path.stat().st_size > 800_000:
                continue
            n_files += 1
            try:
                with path.open("r", encoding="utf-8", errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        if pat in line:
                            hits.append(f"{rel}:{i}:{line.rstrip()[:max_line_len]}")
                            if len(hits) >= max_matches:
                                break
            except OSError:
                continue
            if len(hits) >= max_matches:
                break
    except OSError as e:
        return False, str(e)
    if not hits:
        return True, "(keine Treffer)"
    return True, "\n".join(hits)
