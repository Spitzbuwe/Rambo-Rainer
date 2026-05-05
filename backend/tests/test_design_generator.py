# -*- coding: utf-8 -*-
"""Tests für Design-/SVG-Generierung (HTTP + DesignGenerator)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import requests

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.design_generator import DesignGenerator  # noqa: E402


@pytest.fixture
def design_gen(tmp_path):
    tpl = BACKEND_DIR / "design_templates.json"
    out = tmp_path / "designs"
    return DesignGenerator(templates_path=str(tpl), output_dir=str(out))


def test_design_generator_svg_disk(design_gen):
    r = design_gen.generate_svg_design(
        "business_card",
        variables={"name": "Max", "title": "Dev", "email": "a@b.c"},
    )
    assert r.get("status") == "success"
    assert r["file"].endswith(".svg")
    assert r.get("format") == "SVG"
    assert os.path.isfile(r["path"])


def test_generate_svg_http(base_url, admin_headers):
    r = requests.post(
        f"{base_url}/api/generate/svg-design",
        json={
            "template_type": "business_card",
            "variables": {"name": "Max Mustermann", "title": "Designer"},
        },
        headers={**admin_headers, "Content-Type": "application/json"},
        timeout=60,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["file"].endswith(".svg")
    assert data["format"] == "SVG"
    assert os.path.isfile(data["path"])


def test_generate_design_template_http(base_url, admin_headers):
    r = requests.post(
        f"{base_url}/api/generate/design-template",
        json={
            "design_type": "flyer",
            "brand_style": "modern",
            "variables": {"title": "Mein Flyer", "content": "Text"},
        },
        headers={**admin_headers, "Content-Type": "application/json"},
        timeout=60,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["file"].endswith(".svg")


def test_get_design_templates(base_url):
    r = requests.get(f"{base_url}/api/generate/design-templates", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "svg_templates" in data
    assert "brand_colors" in data
    assert "template_details" in data


def test_svg_design_with_variables_http(base_url, admin_headers):
    r = requests.post(
        f"{base_url}/api/generate/svg-design",
        json={
            "template_type": "logo_background",
            "variables": {"logo": "MY BRAND"},
        },
        headers={**admin_headers, "Content-Type": "application/json"},
        timeout=60,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"


def test_invalid_template_http(base_url, admin_headers):
    r = requests.post(
        f"{base_url}/api/generate/svg-design",
        json={"template_type": "nonexistent"},
        headers={**admin_headers, "Content-Type": "application/json"},
        timeout=30,
    )
    assert r.status_code == 400
    data = r.json()
    assert "error" in data


def test_design_admin_required(base_url):
    r = requests.post(
        f"{base_url}/api/generate/svg-design",
        json={"template_type": "business_card"},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    assert r.status_code == 403

