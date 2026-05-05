# -*- coding: utf-8 -*-
"""Smoke-/Integrations-Tests für die HTTP-API (siehe conftest.py für Backend & state)."""

from __future__ import annotations

import pytest
import requests

pytestmark = [pytest.mark.smoke, pytest.mark.integration]


class TestHealthAndBasics:
    def test_health(self, base_url):
        resp = requests.get(f"{base_url}/api/health", timeout=10)
        assert resp.status_code == 200
        assert resp.json().get("status") == "healthy"

    def test_rules_list(self, base_url, admin_headers):
        resp = requests.get(f"{base_url}/api/rules/list", headers=admin_headers, timeout=10)
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("success") is True
        assert isinstance(body.get("rules"), list)

    def test_rules_history(self, base_url, admin_headers):
        resp = requests.get(f"{base_url}/api/rules/history", headers=admin_headers, timeout=10)
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("success") is True
        assert isinstance(body.get("entries"), list)


class TestRuleUpdates:
    def test_update_rule_priority(self, base_url, admin_headers, fresh_state):
        resp = requests.get(f"{base_url}/api/rules/list", headers=admin_headers, timeout=10)
        assert resp.status_code == 200
        rules = resp.json().get("rules") or []
        if not rules:
            pytest.skip("Keine Rules vorhanden")
        rule = rules[0]
        fp = rule.get("fingerprint")
        if not fp:
            pytest.skip("Regel ohne fingerprint")

        resp = requests.post(
            f"{base_url}/api/rules/update",
            headers=admin_headers,
            json={"fingerprint": fp, "priority": 10},
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    def test_toggle_rule_group(self, base_url, admin_headers, fresh_state):
        resp = requests.get(f"{base_url}/api/rules/list", headers=admin_headers, timeout=10)
        assert resp.status_code == 200
        rules = resp.json().get("rules") or []
        if not rules:
            pytest.skip("Keine Rules vorhanden")
        group = rules[0].get("rule_group") or "behavior"

        resp = requests.post(
            f"{base_url}/api/rule-groups/toggle",
            headers=admin_headers,
            json={"rule_group": group, "active": True},
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.json().get("success") is True


class TestExplainAndExport:
    def test_explain_rule(self, base_url, admin_headers, fresh_state):
        resp = requests.get(
            f"{base_url}/api/rules/explain",
            headers=admin_headers,
            params={"q": "test"},
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    def test_export_rules(self, base_url, admin_headers, fresh_state):
        resp = requests.get(f"{base_url}/api/rules/export", headers=admin_headers, timeout=10)
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("success") is True
        assert "learned_user_rules" in body
        assert isinstance(body["learned_user_rules"], list)


class TestPresetsAndBackup:
    def test_get_presets(self, base_url, admin_headers, fresh_state):
        resp = requests.get(f"{base_url}/api/rules/presets", headers=admin_headers, timeout=10)
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("success") is True
        assert isinstance(body.get("presets"), list)

    def test_apply_preset(self, base_url, admin_headers, fresh_state):
        resp = requests.get(f"{base_url}/api/rules/presets", headers=admin_headers, timeout=10)
        presets = resp.json().get("presets") or []
        if not presets:
            pytest.skip("Keine Presets vorhanden")
        preset_id = presets[0].get("id")
        resp = requests.post(
            f"{base_url}/api/rules/presets/apply",
            headers=admin_headers,
            json={"preset": preset_id, "merge": True},
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    def test_backup_rules(self, base_url, admin_headers, fresh_state):
        resp = requests.get(f"{base_url}/api/rules/backup", headers=admin_headers, timeout=10)
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("success") is True
        assert "learned_user_rules" in body

    def test_restore_rules(self, base_url, admin_headers, fresh_state):
        resp = requests.get(f"{base_url}/api/rules/backup", headers=admin_headers, timeout=10)
        if resp.status_code != 200:
            pytest.skip("Backup nicht verfügbar")
        backup = resp.json()
        resp = requests.post(
            f"{base_url}/api/rules/restore",
            headers=admin_headers,
            json={"backup": backup, "merge": False},
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.json().get("success") is True


class TestSummaryAndStatus:
    def test_summary(self, base_url, admin_headers, fresh_state):
        resp = requests.get(f"{base_url}/api/rules/summary", headers=admin_headers, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        assert "count_active" in data or "rules_total" in data

    def test_status(self, base_url, admin_headers, fresh_state):
        resp = requests.get(f"{base_url}/api/rules/status", headers=admin_headers, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        assert isinstance(data.get("apis"), dict)
