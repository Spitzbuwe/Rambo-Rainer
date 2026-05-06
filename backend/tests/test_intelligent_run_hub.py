# -*- coding: utf-8 -*-
"""Phase 1.1: /api/intelligent-run delegiert an /api/direct-run (ohne implementation: true)."""

from __future__ import annotations

import main


def test_intelligent_run_same_classification_as_direct_run_for_chat():
    with main.app.test_client() as c:
        r_dr = c.post("/api/direct-run", json={"task": "hallo", "scope": "local", "mode": "apply"})
        r_ir = c.post("/api/intelligent-run", json={"task": "hallo"})
    assert r_dr.status_code == 200
    assert r_ir.status_code == 200
    j_dr = r_dr.get_json() or {}
    j_ir = r_ir.get_json() or {}
    assert j_dr.get("classification") == j_ir.get("classification")
    assert j_ir.get("run_mode") == "intelligent"
