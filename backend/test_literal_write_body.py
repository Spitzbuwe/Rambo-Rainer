"""Tests: expliziter Schreib-Inhalt aus Prompt (DEBUG_Plan_Write_Action)."""
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import main as m


def test_extract_inhalt_colon():
    assert m.extract_literal_write_body("Schreibe file1.txt\nInhalt: content1") == "content1"


def test_extract_content_colon_quoted():
    s = m.extract_literal_write_body('Aufgabe\nContent: "content1"')
    assert s == "content1"


def test_extract_fence():
    assert m.extract_literal_write_body("Hi\n```\ncontent1\n```") == "content1"


def test_extract_mit_inhalt_quoted():
    assert m.extract_literal_write_body('Lege an mit dem Inhalt "content1" fuer file1') == "content1"


def test_extract_mit_inhalt_unquoted_token():
    s = "Erstelle nur die Datei x.txt mit dem Inhalt content2."
    assert m.extract_literal_write_body(s) == "content2"


def test_extract_replace_pair_plain():
    old, new = m._extract_explicit_replace_pair(
        "Aendere nur in file2.txt den Inhalt von content2 zu modified."
    )
    assert old == "content2"
    assert new == "modified"


def test_resolve_replace_pair_prefers_existing_content():
    out = m.resolve_proposed_content_for_local_task(
        "Aendere nur in file2.txt den Inhalt von content2 zu modified.",
        "file2.txt",
        "content2",
        True,
        "file2.txt",
    )
    assert out == "modified"


def test_resolve_prefers_literal_over_stub():
    body = m.resolve_proposed_content_for_local_task(
        "Schreibe data/x.txt\nInhalt: ONLYTHIS",
        "data/x.txt",
        "old",
        True,
        "data/x.txt",
    )
    assert body == "ONLYTHIS"
    assert "Aufgabe:" not in body
