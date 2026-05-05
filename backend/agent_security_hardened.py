"""Hardened Security Core: Injection, Traversal, Secrets, Prompt-Overwrite, Audit-Chain."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SECRET_PATTERNS: list[tuple[str, re.Pattern[str], int]] = [
    ("github_token", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"), 50),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), 50),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), 45),
    ("api_key_assignment", re.compile(r"(?i)\bapi[_-]?key\s*[:=]\s*['\"]?[^\s'\";]{4,}"), 30),
    ("password_assignment", re.compile(r"(?i)\bpassword\s*[:=]\s*['\"]?[^\s'\";]{4,}"), 35),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}"), 35),
    ("dotenv_like", re.compile(r"(?im)^\s*[A-Z][A-Z0-9_]{1,40}\s*=\s*[^\n#]{4,}$"), 20),
]

_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str], int]] = [
    ("semicolon_chain", re.compile(r";"), 30),
    ("and_chain", re.compile(r"&&"), 30),
    ("or_chain", re.compile(r"\|\|"), 30),
    ("pipe_chain", re.compile(r"\|"), 20),
    ("backticks", re.compile(r"`[^`]*`"), 35),
    ("dollar_subshell", re.compile(r"\$\([^)]*\)"), 35),
    ("powershell_encodedcommand", re.compile(r"(?i)(?:^|\s)-EncodedCommand(?:\s|$)"), 90),
    ("invoke_expression", re.compile(r"(?i)\b(?:Invoke-Expression|iex)\b"), 60),
    ("rm_rf", re.compile(r"(?i)\brm\s+-rf\b"), 90),
    ("del_recursive", re.compile(r"(?i)\bdel\s+/s\s+/q\b"), 80),
    ("format_command", re.compile(r"(?i)\bformat\b"), 70),
    ("registry_mod", re.compile(r"(?i)\breg\s+(?:add|delete)\b"), 65),
]

_PROMPT_OVERWRITE_MARKERS = (
    "Du arbeitest im Projekt:",
    "Aktueller Stand:",
    "Ausgabeformat:",
    "ZIELORDNER:",
    "ENDE_ZIELORDNER",
    "Pflichttests:",
    "Nicht ändern:",
    "Commit:",
    "Geänderte Dateien",
)

_CRITICAL_FILES = {
    "backend/main.py",
    "frontend/app.js",
    "frontend/index.html",
    "frontend/style.css",
}


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _level_from_score(score: int) -> str:
    if score >= 85:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


class SecurityHardened:
    def __init__(self) -> None:
        self._audit_chain: list[dict[str, Any]] = []
        self._event_counter: int = 0

    def detect_command_injection(self, command: str) -> dict[str, Any]:
        cmd = command or ""
        hits: list[str] = []
        score = 0
        reasons: list[str] = []

        for name, pattern, weight in _INJECTION_PATTERNS:
            if pattern.search(cmd):
                hits.append(name)
                score += weight
                reasons.append(name)

        for m in re.finditer(r"(?i)\b(?:curl|wget)\b[^\n]*?(https?://[^\s'\"`|;]+)", cmd):
            url = m.group(1)
            low = url.lower()
            if not any(host in low for host in ("localhost", "127.0.0.1")):
                hits.append("external_fetch")
                reasons.append(f"external_fetch:{url}")
                score += 35

        for m in re.finditer(r"(?i)\bStart-Process\b[^\n]*?(https?://[^\s'\"`|;]+)", cmd):
            url = m.group(1)
            if "localhost" not in url.lower() and "127.0.0.1" not in url.lower():
                hits.append("suspicious_start_process_url")
                reasons.append(f"suspicious_start_process_url:{url}")
                score += 45

        final_score = max(0, min(100, score))
        return {
            "detected": bool(hits),
            "patterns": sorted(set(hits)),
            "score": final_score,
            "level": _level_from_score(final_score),
            "reasons": reasons,
        }

    def detect_path_traversal(self, path_or_command: str) -> dict[str, Any]:
        text = path_or_command or ""
        issues: list[str] = []
        score = 0

        if "../" in text:
            issues.append("dotdot_slash")
            score += 40
        if "..\\" in text:
            issues.append("dotdot_backslash")
            score += 40
        if re.search(r"(?i)[a-z]:\\[^\\\n]+\\\.\.\\", text):
            issues.append("windows_mixed_traversal")
            score += 50
        if text.startswith("\\\\"):
            issues.append("unc_path")
            score += 35

        final_score = max(0, min(100, score))
        return {
            "detected": bool(issues),
            "issues": sorted(set(issues)),
            "score": final_score,
            "level": _level_from_score(final_score),
        }

    def detect_secrets(self, text: str) -> dict[str, Any]:
        src = text or ""
        findings: list[dict[str, Any]] = []
        score = 0
        reasons: list[str] = []
        for name, pattern, weight in _SECRET_PATTERNS:
            for m in pattern.finditer(src):
                findings.append({"type": name, "match": m.group(0), "start": m.start(), "end": m.end()})
                score += weight
                reasons.append(name)

        final_score = max(0, min(100, score))
        return {
            "detected": bool(findings),
            "findings": findings,
            "score": final_score,
            "level": _level_from_score(final_score),
            "reasons": reasons,
        }

    def scan_secrets(self, text: str) -> list[str]:
        return sorted(set(f["type"] for f in self.detect_secrets(text).get("findings", [])))

    def redact_secrets(self, text: str) -> str:
        out = text or ""

        def _replace_assignment(key_pattern: str, src: str) -> str:
            pat = re.compile(rf"(?i)\b({key_pattern})\s*([:=])\s*([^\s,;]+)")
            return pat.sub(lambda m: f"{m.group(1)}{m.group(2)}***REDACTED***", src)

        out = re.sub(r"\bghp_[A-Za-z0-9]{20,}\b", "***REDACTED***", out)
        out = re.sub(r"\bsk-[A-Za-z0-9]{20,}\b", "***REDACTED***", out)
        out = re.sub(r"\bAKIA[0-9A-Z]{16}\b", "***REDACTED***", out)
        out = re.sub(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}", "bearer ***REDACTED***", out)
        out = _replace_assignment(r"api[_-]?key", out)
        out = _replace_assignment(r"password", out)
        return out

    def validate_project_path(self, path: str, project_root: str | Path) -> dict[str, Any]:
        p_raw = path or ""
        root = Path(project_root).resolve()

        if p_raw.startswith("\\\\"):
            return {"allowed": False, "reason": "unc_path_not_allowed", "normalized_path": p_raw}

        p = Path(p_raw)
        p_abs = p if p.is_absolute() else (root / p)
        p_abs = p_abs.resolve(strict=False)

        try:
            p_abs.relative_to(root)
            return {"allowed": True, "reason": "inside_project_root", "normalized_path": str(p_abs)}
        except ValueError:
            return {"allowed": False, "reason": "outside_project_root", "normalized_path": str(p_abs)}

    def detect_prompt_overwrite(self, file_path: str, new_content: str, old_content: str | None = None) -> dict[str, Any]:
        rel = (file_path or "").replace("\\", "/").lstrip("./")
        new_text = new_content or ""
        old_text = old_content or ""
        hits = [m for m in _PROMPT_OVERWRITE_MARKERS if m in new_text]
        prompt_like = len(hits) >= 2 or ("Du arbeitest im Projekt:" in new_text)
        old_long = len(old_text) >= 400
        new_short = len(new_text) < max(200, int(len(old_text) * 0.35)) if old_text else False
        critical = rel in _CRITICAL_FILES

        block = False
        reason = "ok"
        if critical and prompt_like:
            block = True
            reason = "Prompt-Overwrite erkannt"
        elif prompt_like and old_long and new_short:
            block = True
            reason = "Prompt-Overwrite erkannt"

        return {
            "block": block,
            "reason": reason,
            "matched_patterns": hits,
            "critical_file": critical,
        }

    def risk_score(self, command_or_text: str) -> dict[str, Any]:
        inj = self.detect_command_injection(command_or_text)
        pth = self.detect_path_traversal(command_or_text)
        sec = self.detect_secrets(command_or_text)
        score = min(100, int(inj["score"] * 0.5 + pth["score"] * 0.25 + sec["score"] * 0.35))
        reasons = list(dict.fromkeys(inj["reasons"] + pth["issues"] + sec["reasons"]))
        return {"score": score, "level": _level_from_score(score), "reasons": reasons}

    def sanitize_command(self, command: str) -> dict[str, Any]:
        cmd = command or ""
        inj = self.detect_command_injection(cmd)
        pth = self.detect_path_traversal(cmd)
        sec = self.detect_secrets(cmd)
        risk = self.risk_score(cmd)
        blocked = bool(inj["detected"] or pth["detected"] or sec["detected"] or risk["score"] >= 60)
        reasons = list(dict.fromkeys(inj["reasons"] + pth["issues"] + sec["reasons"] + risk["reasons"]))
        return {
            "allowed": not blocked,
            "blocked": blocked,
            "command": cmd,
            "redacted_command": self.redact_secrets(cmd),
            "injection": inj,
            "path_traversal": pth,
            "secrets": sec,
            "risk": risk,
            "reasons": reasons,
        }

    def _compute_event_hash(self, event: dict[str, Any]) -> str:
        payload = {
            "event_id": event["event_id"],
            "timestamp": event["timestamp"],
            "level": event["level"],
            "event_type": event["event_type"],
            "data": event["data"],
            "previous_hash": event["previous_hash"],
        }
        return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()

    def audit_event(self, event_type: str, data: dict | None = None, level: str = "info") -> dict[str, Any]:
        self._event_counter += 1
        previous_hash = self._audit_chain[-1]["hash"] if self._audit_chain else "genesis"
        event = {
            "event_id": f"evt-{self._event_counter:06d}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "event_type": event_type,
            "data": dict(data or {}),
            "previous_hash": previous_hash,
        }
        event["hash"] = self._compute_event_hash(event)
        self._audit_chain.append(event)
        if len(self._audit_chain) > 1000:
            del self._audit_chain[:-1000]
        return dict(event)

    def verify_audit_chain(self) -> dict[str, Any]:
        if not self._audit_chain:
            return {"ok": True, "checked": 0, "reason": "empty_chain"}
        prev = "genesis"
        for idx, event in enumerate(self._audit_chain):
            if event.get("previous_hash") != prev:
                return {"ok": False, "checked": idx + 1, "index": idx, "reason": "previous_hash_mismatch"}
            expected = self._compute_event_hash(event)
            if event.get("hash") != expected:
                return {"ok": False, "checked": idx + 1, "index": idx, "reason": "hash_mismatch"}
            prev = event["hash"]
        return {"ok": True, "checked": len(self._audit_chain), "reason": "chain_valid"}

    def audit_append(self, event: str, **data: Any) -> dict[str, Any]:
        return self.audit_event(event_type=event, data=data, level="info")

    def verify_chain_tail(self, max_entries: int = 50) -> bool:
        if max_entries <= 0:
            return True
        chain = self._audit_chain[-max_entries:]
        prev = "genesis" if len(chain) == len(self._audit_chain) else self._audit_chain[-max_entries - 1]["hash"]
        for item in chain:
            if item.get("previous_hash") != prev:
                return False
            if item.get("hash") != self._compute_event_hash(item):
                return False
            prev = item["hash"]
        return True

    def verify_signature(self, message: str, signature: str, secret: str) -> bool:
        expected = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "status": "ready",
            "module": "agent_security_hardened",
            "audit_events": len(self._audit_chain),
        }


_INSTANCE: SecurityHardened | None = None


def get_instance() -> SecurityHardened:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = SecurityHardened()
    return _INSTANCE


security_hardened = get_instance()


def detect_command_credential_patterns(cmd: str) -> list[str]:
    return security_hardened.scan_secrets(cmd)


def security_preflight_command_string(cmd: str) -> dict[str, Any] | None:
    checked = security_hardened.sanitize_command(cmd)
    if checked["blocked"]:
        if checked["secrets"]["detected"]:
            code = "SECURITY_SECRET_PATTERN"
            hints = ["Secrets aus Umgebungsvariablen laden", "Keine API-Keys in der Befehlszeile"]
        else:
            code = "SECURITY_SANITIZE"
            hints = ["Befehl ohne Injection-/Traversal-Muster formulieren"]
        security_hardened.audit_event("security_preflight_block", {"reasons": checked["reasons"], "cmd": checked["redacted_command"]}, level="warning")
        return {
            "success": False,
            "error": "Security preflight block: " + ", ".join(checked["reasons"][:4]),
            "error_code": code,
            "hints": hints,
            "recovery": {"retry_suggested": False},
            "cmd": checked["redacted_command"],
        }
    return None


__all__ = [
    "SecurityHardened",
    "get_instance",
    "security_hardened",
    "detect_command_credential_patterns",
    "security_preflight_command_string",
]
