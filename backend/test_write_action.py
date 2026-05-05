"""Mini-Phase 2: write_action.py Smoke (ohne Flask)."""
import shutil
import tempfile
from pathlib import Path

from write_action import execute_write_action, run_write_action_with_watchdog

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_write_action_simple_success_dict():
    """Realstatus Mini-Phase 2: Erfolg = ok, Datei existiert, Inhalt stimmt."""
    p = _DATA_DIR / ".rambo_write_simple_test.txt"
    try:
        r = execute_write_action(p, "Hello World", "data/.rambo_write_simple_test.txt", backup=True)
        assert r.get("ok") is True
        assert p.is_file()
        assert p.read_text(encoding="utf-8") == "Hello World"
    finally:
        try:
            p.unlink()
        except OSError:
            pass
        for bak in _DATA_DIR.glob(".rambo_write_simple_test.txt.rambo-bak-*"):
            try:
                bak.unlink()
            except OSError:
                pass


def test_line_ending_normalization():
    """Arbeitsauftrag: \\r\\n wird als \\n auf die Platte geschrieben."""
    p = _DATA_DIR / ".rambo_write_nl_test.txt"
    try:
        r = execute_write_action(
            p,
            "line1\r\nline2\r\nline3",
            "data/.rambo_write_nl_test.txt",
            backup=True,
        )
        assert r.get("ok") is True, r
        raw = p.read_text(encoding="utf-8")
        assert "\r\n" not in raw
        assert raw == "line1\nline2\nline3"
    finally:
        try:
            p.unlink()
        except OSError:
            pass


def test_backup_creation_kept():
    """Arbeitsauftrag: Backup enthaelt alten Inhalt (cleanup_success_backup=False fuer Test)."""
    p = _DATA_DIR / ".rambo_write_backup_test.txt"
    bak_path = None
    try:
        p.write_text("old content", encoding="utf-8")
        r = execute_write_action(
            p,
            "new content",
            "data/.rambo_write_backup_test.txt",
            backup=True,
            cleanup_success_backup=False,
        )
        assert r.get("ok") is True, r
        bak_path = r.get("backup_path")
        assert bak_path, r
        bp = Path(bak_path)
        assert bp.is_file()
        assert bp.read_text(encoding="utf-8") == "old content"
        assert p.read_text(encoding="utf-8") == "new content"
    finally:
        try:
            p.unlink()
        except OSError:
            pass
        if bak_path:
            try:
                Path(bak_path).unlink()
            except OSError:
                pass


def test_mkdir_creates_directory():
    """Arbeitsauftrag: Parent-Verzeichnis wird angelegt."""
    tmp = tempfile.mkdtemp()
    try:
        nested = Path(tmp) / "subdir" / "nested.txt"
        r = execute_write_action(nested, "content", str(nested), backup=True)
        assert r.get("ok") is True, r
        assert nested.is_file()
        assert nested.read_text(encoding="utf-8") == "content"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_routes_persist_text_file_change():
    """Mini-Phase 2: routes.persist_text_file_change = Watchdog-Pfad fuer main."""
    from routes import persist_text_file_change

    p = _DATA_DIR / ".rambo_route_persist.txt"
    try:
        r = persist_text_file_change(p, "via_routes", "data/.rambo_route_persist.txt", timeout_sec=15)
        assert r.get("ok") is True, r
        assert p.read_text(encoding="utf-8") == "via_routes"
    finally:
        try:
            p.unlink()
        except OSError:
            pass


def test_write_roundtrip_and_watchdog():
    p = _DATA_DIR / ".rambo_write_smoke_unit.txt"
    try:
        r = execute_write_action(p, "alpha\nbeta\n", "data/.rambo_write_smoke_unit.txt", backup=True)
        assert r.get("ok") is True, r
        raw = p.read_text(encoding="utf-8")
        assert raw.replace("\r\n", "\n") == "alpha\nbeta\n"
        r2 = run_write_action_with_watchdog(
            p,
            "next",
            "data/.rambo_write_smoke_unit.txt",
            timeout_sec=15,
            on_timeout_log=lambda _m: None,
        )
        assert r2.get("ok") is True, r2
        assert p.read_text(encoding="utf-8").replace("\r\n", "\n") == "next"
    finally:
        try:
            p.unlink()
        except OSError:
            pass
        for bak in _DATA_DIR.glob(".rambo_write_smoke_unit.txt.rambo-bak-*"):
            try:
                bak.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    test_write_roundtrip_and_watchdog()
    print("write_action_ok")
