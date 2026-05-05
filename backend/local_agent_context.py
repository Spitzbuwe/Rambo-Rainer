"""
Kontext-Packaging fuer Lokal-Agent (Rainer Build 3.0): Workspace-Baum, Tags.
"""
from __future__ import annotations

from pathlib import Path

SKIP_TOP = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "dist-installer",
        ".venv",
        "venv",
        ".idea",
        "Downloads",
    }
)


def build_workspace_tree_snippet(root: Path, max_lines: int = 42) -> str:
    """Kompakter Ueberblick ueber Projektroot (1–2 Ebenen, begrenzt)."""
    root = root.resolve()
    lines: list[str] = [f"{root.name}/"]
    n = 1
    try:
        entries = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError:
        return "(Verzeichnis nicht lesbar)"
    for p in entries:
        if n >= max_lines:
            lines.append("… (weitere Eintraege ausgelassen)")
            break
        name = p.name
        if name in SKIP_TOP or name.startswith("."):
            continue
        if p.is_dir():
            lines.append(f"├── {name}/")
            n += 1
            if name in ("backend", "frontend", "tests") and n < max_lines - 4:
                try:
                    sub = sorted(
                        (x for x in p.iterdir() if not x.name.startswith(".")),
                        key=lambda x: (not x.is_dir(), x.name.lower()),
                    )[:10]
                    for s in sub:
                        if n >= max_lines:
                            break
                        suf = "/" if s.is_dir() else ""
                        lines.append(f"│   ├── {s.name}{suf}")
                        n += 1
                except OSError:
                    pass
        else:
            lines.append(f"├── {name}")
            n += 1
    return "\n".join(lines)


def parse_search_result_lines(text: str) -> list[dict[str, int | str]]:
    """Parst Zeilen im Format `rel/path.py:42:rest` (rg oder Fallback)."""
    hits: list[dict[str, int | str]] = []
    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s or s.startswith("("):
            continue
        if s.count(":") < 2:
            continue
        rel, lno, content = s.split(":", 2)
        rel = rel.strip()
        lno = lno.strip()
        if not rel or not lno.isdigit():
            continue
        hits.append({"file": rel, "line": int(lno), "content": content.strip()[:500]})
    return hits
