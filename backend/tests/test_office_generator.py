# -*- coding: utf-8 -*-
"""Tests für Office-Generierung (HTTP + OfficeGenerator direkt)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import requests

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.office_generator import OfficeGenerator  # noqa: E402


@pytest.fixture
def office_gen(tmp_path):
    tpl = BACKEND_DIR / "document_templates.json"
    out = tmp_path / "out"
    return OfficeGenerator(templates_path=str(tpl), output_dir=str(out))


def test_office_generator_word_disk(office_gen):
    r = office_gen.generate_word_document(
        "letter", "Test-Brief", "Inhalt.", author="Test"
    )
    assert r.get("status") == "success"
    assert r["file"].endswith(".docx")
    assert os.path.isfile(r["path"])


def test_office_generator_excel_disk(office_gen):
    r = office_gen.generate_excel_sheet(
        "budget",
        data={"Einnahmen": [[100, 200], [50, 75]]},
    )
    assert r.get("status") == "success"
    assert r["file"].endswith(".xlsx")
    assert os.path.isfile(r["path"])


def test_office_generator_powerpoint_disk(office_gen):
    r = office_gen.generate_powerpoint("presentation")
    assert r.get("status") == "success"
    assert r["file"].endswith(".pptx")
    assert os.path.isfile(r["path"])


def test_office_generator_unknown_template(office_gen):
    r = office_gen.generate_word_document("nope", "x", "y")
    assert "error" in r


def test_generate_word_http(base_url, admin_headers):
    r = requests.post(
        f"{base_url}/api/generate/word-document",
        json={
            "template_type": "letter",
            "title": "Test-Brief",
            "content": "Das ist ein Test-Brief.",
            "author": "pytest",
        },
        headers={**admin_headers, "Content-Type": "application/json"},
        timeout=60,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["file"].endswith(".docx")
    assert os.path.isfile(data["path"])


def test_generate_excel_http(base_url, admin_headers):
    r = requests.post(
        f"{base_url}/api/generate/excel-sheet",
        json={"template_type": "budget"},
        headers={**admin_headers, "Content-Type": "application/json"},
        timeout=60,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["file"].endswith(".xlsx")


def test_generate_powerpoint_http(base_url, admin_headers):
    r = requests.post(
        f"{base_url}/api/generate/powerpoint",
        json={"template_type": "presentation"},
        headers={**admin_headers, "Content-Type": "application/json"},
        timeout=60,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["file"].endswith(".pptx")


def test_get_office_templates(base_url):
    r = requests.get(f"{base_url}/api/generate/office-templates", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "word_templates" in data
    assert "excel_templates" in data
    assert "powerpoint_templates" in data
    assert "letter" in data["word_templates"]


def test_word_forbidden_without_admin(base_url):
    r = requests.post(
        f"{base_url}/api/generate/word-document",
        json={"template_type": "letter", "title": "x", "content": "y"},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    assert r.status_code == 403
