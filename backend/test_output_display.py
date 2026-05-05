"""
Test dass Analyseergebnisse angezeigt werden
"""
from pathlib import Path

from file_reader import read_file_content, get_latest_analysis_file
from message_templates import MessageTemplates as MT


def test_read_file_content():
    """Kann Datei lesen?"""
    auto_dir = Path(__file__).resolve().parent.parent / "data" / "auto"
    auto_dir.mkdir(parents=True, exist_ok=True)
    test_file = auto_dir / "test_analysis.md"
    test_file.write_text("Test Content", encoding="utf-8")

    content = read_file_content(test_file)
    assert content == "Test Content"

    test_file.unlink(missing_ok=True)


def test_analysis_message():
    """Wird Message richtig gebaut?"""
    content = "Rambo Rainer: ...\nRainer Build: ..."
    message = MT.analysis_result(content)

    assert "Ich habe die Analyse durchgeführt" in message
    assert content in message
    assert "✓" in message


def test_query_result():
    """Query-Result Messages?"""
    content = "Ergebnis 1\nErgebnis 2"
    message = MT.query_result("structure", content)

    assert "Ich habe die Struktur analysiert" in message
    assert content in message


def test_get_latest_analysis_file():
    auto_dir = Path(__file__).resolve().parent.parent / "data" / "auto"
    auto_dir.mkdir(parents=True, exist_ok=True)
    older = auto_dir / "test_old_analysis.md"
    newer = auto_dir / "test_new_analysis.md"
    older.write_text("old", encoding="utf-8")
    newer.write_text("new", encoding="utf-8")
    latest = get_latest_analysis_file(auto_dir)
    assert latest is not None
    assert latest.name in {older.name, newer.name}
    older.unlink(missing_ok=True)
    newer.unlink(missing_ok=True)
