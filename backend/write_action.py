"""
Mini-Phase 2: zentraler Text-Schreibpfad + Watchdog (ohne Import von main).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from uuid import uuid4

from agent_file_guard import run_post_write_language_checks, validate_write_payload

DIRECT_WRITE_ACTION_TIMEOUT_SEC = 30


def _read_utf8(path: Path):
    try:
        if not path.exists():
            return "", False
        return path.read_text(encoding="utf-8"), True
    except OSError:
        return "", False


def _safe_unlink_path(path):
    if not path:
        return
    try:
        p = Path(path) if not isinstance(path, Path) else path
        if p.is_file():
            p.unlink()
    except OSError:
        pass


def execute_write_action(
    resolved,
    proposed_content,
    display_path,
    *,
    backup=True,
    cleanup_success_backup=True,
):
    """
    Text-Schreibpfad: mkdir, write, Verifikation (NL-normalisiert), optionales Backup/Restore.
    Inhalt wird als Unix-Zeilenenden (\\n) geschrieben; Lesen wird zum Vergleich normalisiert.

    cleanup_success_backup: True = Backup-Datei nach erfolgreichem Write loeschen (Standard).
    Rueckgabe: dict ok, error, lines, restored, backup_path (nur wenn cleanup_success_backup False).
    """
    def norm_nl(text):
        return (text or "").replace("\r\n", "\n")

    if not isinstance(resolved, Path):
        return {"ok": False, "error": "Interner Fehler: kein gueltiger Dateipfad.", "lines": 0, "restored": False}

    normalized = norm_nl(proposed_content or "")
    backup_path = None
    previous = None
    had_file = False
    try:
        if resolved.exists():
            had_file = True
            previous, _ = _read_utf8(resolved)
        allowed, verr = validate_write_payload(resolved, normalized, previous, had_file)
        if not allowed:
            return {"ok": False, "error": verr or "Schreibabweisung (Agent-Regeln).", "lines": 0, "restored": False}
        if had_file and backup and previous is not None:
            backup_path = resolved.parent / (resolved.name + f".rambo-bak-{uuid4().hex[:10]}")
            try:
                backup_path.write_text(previous, encoding="utf-8")
            except OSError:
                backup_path = None

        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(normalized, encoding="utf-8")
        read_back, _ = _read_utf8(resolved)
        if norm_nl(read_back) != normalized:
            if previous is not None:
                try:
                    resolved.write_text(previous, encoding="utf-8")
                except OSError:
                    pass
            _safe_unlink_path(backup_path)
            return {
                "ok": False,
                "error": (
                    f"Inhalt nach Schreiben nicht verifizierbar ({display_path}). "
                    "Bitte Encoding/Zeilenenden pruefen."
                ),
                "lines": 0,
                "restored": had_file,
            }

        chk_ok, chk_msg = run_post_write_language_checks(resolved)
        if not chk_ok:
            if previous is not None:
                try:
                    resolved.write_text(previous, encoding="utf-8")
                except OSError:
                    pass
            _safe_unlink_path(backup_path)
            return {
                "ok": False,
                "error": (
                    "Post-Check (py_compile / node --check) fehlgeschlagen; Datei zurueckgesetzt. "
                    + (chk_msg or "")
                )[:2000],
                "lines": 0,
                "restored": had_file,
            }

        lines = normalized.count("\n") + (1 if normalized else 0)
        kept = None
        if backup_path and backup_path.is_file():
            if cleanup_success_backup:
                _safe_unlink_path(backup_path)
            else:
                kept = str(backup_path)
        return {"ok": True, "error": None, "lines": lines, "restored": False, "backup_path": kept}
    except OSError as e:
        if previous is not None:
            try:
                resolved.write_text(previous, encoding="utf-8")
            except OSError:
                pass
        _safe_unlink_path(backup_path)
        msg = getattr(e, "strerror", None) or str(e)
        return {
            "ok": False,
            "error": f"Datei konnte nicht geschrieben werden ({display_path}): {msg}",
            "lines": 0,
            "restored": had_file,
        }


def run_write_action_with_watchdog(
    resolved,
    proposed_content,
    display_path,
    timeout_sec=None,
    on_timeout_log=None,
    *,
    backup=True,
    cleanup_success_backup=True,
):
    """Schreibaktion in Worker-Thread mit Timeout; optional Callback bei Timeout (z. B. append_ui_log_entry)."""
    limit = float(timeout_sec if timeout_sec is not None else DIRECT_WRITE_ACTION_TIMEOUT_SEC)

    def _run():
        return execute_write_action(
            resolved,
            proposed_content,
            display_path,
            backup=backup,
            cleanup_success_backup=cleanup_success_backup,
        )

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            fut = executor.submit(_run)
            return fut.result(timeout=max(limit, 1.0))
    except FuturesTimeoutError:
        msg = f"Schreib-Watchdog: Timeout nach {int(limit)}s fuer {display_path}"
        if callable(on_timeout_log):
            try:
                on_timeout_log(msg)
            except Exception:
                pass
        return {
            "ok": False,
            "error": f"Timeout bei Schreibaktion (>{int(limit)}s). Bitte erneut versuchen.",
            "lines": 0,
            "restored": False,
        }
