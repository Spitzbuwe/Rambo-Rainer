"""
Etappe 1: pytest fuer task_parser + routing (DIRECT vs SAFE).
Ausfuehren: python -m pytest rambo_builder_local/backend/test_routing.py -v
oder: cd rambo_builder_local/backend && python -m pytest test_routing.py -v
"""
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from routing import is_direct_safe
from task_parser import parse_user_prompt_to_task_spec


def test_direct_safe_single_line_change():
    spec = parse_user_prompt_to_task_spec("Ändere app.js Zeile 5 von 'a' zu 'b'")
    assert is_direct_safe(spec) is True
    assert spec.operation == "change_file"
    assert spec.file_count == 1


def test_safe_file_deletion():
    spec = parse_user_prompt_to_task_spec("Loesche debug.log")
    assert is_direct_safe(spec) is False
    assert spec.operation == "delete_file"


def test_safe_multiple_files():
    spec = parse_user_prompt_to_task_spec("Ändere app.js, config.json und utils.js")
    assert is_direct_safe(spec) is False
    assert spec.file_count >= 2


def test_safe_large_code():
    spec = parse_user_prompt_to_task_spec("Schreib eine ganze neue Funktion [200 Zeilen]")
    assert is_direct_safe(spec) is False
    assert spec.line_count >= 200


def test_safe_shell_command():
    spec = parse_user_prompt_to_task_spec("Führe npm test aus")
    assert is_direct_safe(spec) is False
    assert spec.has_shell_commands is True


def test_handle_user_prompt_routing_tuple():
    from routes import handle_user_prompt_routing

    path, spec = handle_user_prompt_routing("nur ein kleiner Kommentar in readme.md")
    assert path in ("DIRECT_EXECUTE_PATH", "SAFE_REVIEW_PATH")
    assert spec.operation in ("change_file", "unknown", "create_file")


def test_realstatus_doc_string_api():
    """Realstatus Mini-Phase 1: Doku-API is_direct_safe(str)."""
    assert is_direct_safe("Ändere file.txt eine Zeile") is True
    assert is_direct_safe("Loesche file.txt") is False
    assert is_direct_safe("Schreib 200 Zeilen Code") is False


def test_simple_line_change_is_direct():
    """Arbeitsauftrag: einfache Zeile aendern (Dict-API) = DIRECT."""
    task = {
        "operation": "change_file",
        "file": "app.js",
        "lines": 1,
        "content_size": 45,
    }
    assert is_direct_safe(task) is True, "Simple change should be DIRECT"


def test_file_deletion_is_safe():
    """Arbeitsauftrag: Datei loeschen = SAFE."""
    task = {"operation": "delete_file", "file": "debug.log"}
    assert is_direct_safe(task) is False, "Delete should be SAFE_REVIEW"


def test_large_code_is_safe():
    """Arbeitsauftrag: grosser Code-Block = SAFE."""
    task = {
        "operation": "create_file",
        "file": "new_module.py",
        "lines": 250,
        "content_size": 8500,
    }
    assert is_direct_safe(task) is False, "Large file should be SAFE_REVIEW"


def test_shell_command_is_safe():
    """Arbeitsauftrag: Shell-Befehl = SAFE."""
    task = {"operation": "run_command", "command": "npm test"}
    assert is_direct_safe(task) is False, "Shell command should be SAFE_REVIEW"


def test_multiple_files_is_safe():
    """Arbeitsauftrag: mehrere Dateien = SAFE."""
    task = {
        "operation": "change_files",
        "files": ["app.js", "config.json", "utils.py"],
    }
    assert is_direct_safe(task) is False, "Multiple files should be SAFE_REVIEW"


def test_prompt_debug_toggle_line5_is_direct():
    """Beispiel aus Arbeitsauftrag: konkreter Ein-Zeilen-Edit app.js."""
    prompt = "Ändere app.js Zeile 5 von 'debug: false' zu 'debug: true'"
    assert is_direct_safe(prompt) is True, "Single targeted line edit should be DIRECT"
