"""Release-Hinweise — kein stiller EXE-Build."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


class ExecutableCreator:
    """Erzeugt BUILD_RELEASE.md inkl. PyInstaller-Anleitung und Build-Status."""

    @staticmethod
    def write_release_notes(root: Path, build_result: dict[str, Any] | None = None) -> dict:
        root = Path(root).resolve()
        br = build_result or {}
        status = str(br.get("status") or ("OK" if br.get("ok") else "UNKNOWN"))
        err_lines = br.get("errors") or []
        err_block = ""
        if err_lines:
            err_block = "\n## py_compile / Import — Fehler\n\n" + "\n".join(f"- `{e}`" for e in err_lines[:20])

        fc = br.get("files_checked", br.get("checked_files", "–"))
        ic = br.get("import_check") or {}
        ic_line = ""
        if isinstance(ic, dict) and not ic.get("skipped"):
            ic_line = f"- **Import-Smoke:** `{'OK' if ic.get('ok') else 'FAILED'}` — {ic.get('module', ic.get('error', ''))}"

        entry = "src/main.py" if (root / "src" / "main.py").is_file() else "src/generated_app.py"
        parts: list[str] = [
            "# BUILD & Release (Sandbox)",
            "",
            "Dieses Verzeichnis wurde von **Rainer Build 3.0** als lokale Implementation erzeugt.",
            "",
            "## Sandbox-Pfad",
            "",
            f"`{root}`",
            "",
            "## Build-Status (automatisch)",
            "",
            f"- **Status:** `{status}`",
            f"- **Gepruefte Python-Dateien (Anzahl):** {fc}",
        ]
        if ic_line:
            parts.append(ic_line)
        parts.extend(
            [
                "",
                "## Dependencies",
                "",
                "- Siehe `requirements.txt` im Sandbox-Ordner.",
                "- Keine automatische Installation durch Rainer.",
                "",
                "## Setup (lokal ausfuehren)",
                "",
                "```powershell",
                f"Set-Location -LiteralPath '{root}'",
                "python -m venv .venv",
                ".\\.venv\\Scripts\\Activate.ps1",
                "pip install -r requirements.txt",
                f"python {entry.replace('/', chr(92))}",
                "```",
                "",
                "## EXE bauen (PyInstaller) — manuell",
                "",
                "```powershell",
                "python -m pip install --upgrade pip",
                "python -m pip install pyinstaller",
                f"pyinstaller --onefile {entry}",
                "```",
                "",
                "Ergebnis liegt typisch unter `dist/`. **Kein** stilles Signieren oder Installer durch Rainer.",
                "",
                "## Hinweis",
                "",
                "Fuer Produktion: Versionierung, Code-Signing, CI/CD und eigene QA.",
                err_block,
                "",
            ]
        )
        text = "\n".join(parts)
        p = root / "BUILD_RELEASE.md"
        try:
            p.write_text(text, encoding="utf-8", newline="\n")
        except OSError as ex:
            _log.exception("BUILD_RELEASE.md schreiben fehlgeschlagen")
            raise OSError(f"Konnte BUILD_RELEASE.md nicht schreiben: {p}") from ex
        _log.info("Release Notes geschrieben: %s", p)
        return {"artifact": str(p), "hint": "PyInstaller- und Setup-Schritte siehe BUILD_RELEASE.md"}


def write_release_notes(root: Path, build_result: dict[str, Any] | None = None) -> dict:
    """Abwaertskompatibler Wrapper."""
    return ExecutableCreator.write_release_notes(root, build_result)


def create_exe_from_python(_root: Path) -> dict:
    return {"ok": False, "skipped": True, "reason": "PyInstaller nicht automatisch ausgefuehrt"}


def create_exe_from_csharp(_root: Path) -> dict:
    return {"ok": False, "skipped": True, "reason": "MSBuild nicht automatisch ausgefuehrt"}


def create_installer(_root: Path) -> dict:
    return {"ok": False, "skipped": True, "reason": "Installer-Erstellung nicht automatisch"}
