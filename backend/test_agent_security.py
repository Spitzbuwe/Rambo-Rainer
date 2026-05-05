"""Tests fuer agent_security_hardened."""

from __future__ import annotations

import pytest

from agent_security_hardened import (
    SecurityHardened,
    detect_command_credential_patterns,
    security_preflight_command_string,
)


def test_sanitize_blocks_backtick() -> None:
    s = SecurityHardened()
    ok, msg = s.sanitize_command("python -c `whoami`")
    assert ok is False


def test_sanitize_blocks_traversal_substring() -> None:
    s = SecurityHardened()
    ok, _ = s.sanitize_command("cat ../../etc/passwd")
    assert ok is False


def test_scan_aws_key_pattern() -> None:
    cmd = "echo AKIA0123456789ABCDEF"
    hits = detect_command_credential_patterns(cmd)
    assert "AWS_ACCESS_KEY_PATTERN" in hits


def test_scan_github_pat() -> None:
    token_body = "abcdefghijklmnopqrstuvwxyz0123456789ABCD"  # 36 Zeichen
    cmd = "curl -H token ghp_" + token_body
    hits = detect_command_credential_patterns(cmd)
    assert "GITHUB_PAT_PATTERN" in hits


def test_preflight_blocks_secret() -> None:
    out = security_preflight_command_string("export AWS=AKIA0123456789ABCDEF")
    assert out is not None
    assert out.get("error_code") == "SECURITY_SECRET_PATTERN"


def test_preflight_blocks_sanitize() -> None:
    out = security_preflight_command_string("echo `id`")
    assert out is not None
    assert out.get("error_code") == "SECURITY_SANITIZE"


def test_hmac_verify() -> None:
    s = SecurityHardened()
    msg = "hello"
    secret = "s3cr3t"
    sig = __import__("hmac").new(secret.encode(), msg.encode(), __import__("hashlib").sha256).hexdigest()
    assert s.verify_signature(msg, sig, secret) is True
    assert s.verify_signature(msg, sig + "x", secret) is False


def test_audit_chain_links() -> None:
    s = SecurityHardened()
    s.audit_append("a", x=1)
    s.audit_append("b", x=2)
    assert s.verify_chain_tail(10) is True
