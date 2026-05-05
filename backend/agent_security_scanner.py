"""Local security scanner with deterministic risk reporting."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

_DEFAULT_PATTERNS = ("*.py", "*.js", "*.jsx", "*.ts", "*.tsx", "*.html", "*.css", "*.json", "*.yml", "*.yaml", "*.env", "*.txt")
_IGNORED_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build", ".rainer_agent", "Downloads"}
_PROMPT_MARKERS = ("Du arbeitest im Projekt:", "ZIELORDNER:", "ENDE_ZIELORDNER", "Ausgabeformat:")


def _make_id(file_path: str, line: int | None, ftype: str, evidence: str) -> str:
    raw = f"{file_path}|{line}|{ftype}|{evidence}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class SecurityScanner:
    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root or ".").resolve()

    def _add_finding(
        self,
        findings: list[dict[str, Any]],
        *,
        file_path: str,
        line: int | None,
        ftype: str,
        severity: str,
        message: str,
        evidence: str,
        recommendation: str,
    ) -> None:
        findings.append(
            {
                "id": _make_id(file_path, line, ftype, evidence),
                "file": file_path,
                "line": line,
                "type": ftype,
                "severity": severity,
                "message": message,
                "evidence": evidence[:220],
                "recommendation": recommendation,
            }
        )

    def scan_text(self, text: str, file_path: str | None = None) -> dict[str, Any]:
        src = text or ""
        fp = file_path or "<memory>"
        findings: list[dict[str, Any]] = []
        lines = src.splitlines() or [src]
        for i, ln in enumerate(lines, start=1):
            low = ln.lower()

            if re.search(r"\bghp_[A-Za-z0-9]{20,}\b", ln):
                self._add_finding(findings, file_path=fp, line=i, ftype="hardcoded_secret", severity="critical", message="GitHub token detected", evidence=ln, recommendation="Move token to environment variable")
            if re.search(r"\bsk-[A-Za-z0-9]{20,}\b", ln):
                self._add_finding(findings, file_path=fp, line=i, ftype="hardcoded_secret", severity="critical", message="OpenAI key detected", evidence=ln, recommendation="Move key to environment variable")
            if re.search(r"\bAKIA[0-9A-Z]{16}\b", ln):
                self._add_finding(findings, file_path=fp, line=i, ftype="hardcoded_secret", severity="critical", message="AWS access key detected", evidence=ln, recommendation="Use secure credential provider")
            if re.search(r"(?i)\bapi[_-]?key\s*[:=]", ln) or re.search(r"(?i)\bpassword\s*[:=]", ln):
                self._add_finding(findings, file_path=fp, line=i, ftype="hardcoded_secret", severity="high", message="Credential assignment detected", evidence=ln, recommendation="Use secret manager or env vars")
            if re.search(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}", ln):
                self._add_finding(findings, file_path=fp, line=i, ftype="hardcoded_secret", severity="high", message="Bearer token detected", evidence=ln, recommendation="Redact token and inject at runtime")

            if "shell=true" in low and "subprocess" in low:
                self._add_finding(findings, file_path=fp, line=i, ftype="dangerous_shell", severity="critical", message="subprocess with shell=True", evidence=ln, recommendation="Use argv list with shell=False")
            if "os.system(" in low:
                self._add_finding(findings, file_path=fp, line=i, ftype="dangerous_shell", severity="high", message="os.system usage detected", evidence=ln, recommendation="Use subprocess.run with explicit argv")
            if re.search(r"\beval\s*\(", low) or re.search(r"\bexec\s*\(", low):
                self._add_finding(findings, file_path=fp, line=i, ftype="code_execution", severity="critical", message="Dynamic code execution detected", evidence=ln, recommendation="Avoid eval/exec on runtime input")
            if "pickle.loads" in low:
                self._add_finding(findings, file_path=fp, line=i, ftype="unsafe_deserialization", severity="high", message="pickle.loads detected", evidence=ln, recommendation="Use safe serialization formats")
            if "yaml.load(" in low and "safeloader" not in low:
                self._add_finding(findings, file_path=fp, line=i, ftype="unsafe_deserialization", severity="high", message="yaml.load without SafeLoader", evidence=ln, recommendation="Use yaml.safe_load or SafeLoader")

            if "debug=true" in low:
                self._add_finding(findings, file_path=fp, line=i, ftype="unsafe_web_config", severity="high", message="Debug mode enabled", evidence=ln, recommendation="Disable debug in non-local environments")
            if "access-control-allow-origin" in low and "*" in low:
                self._add_finding(findings, file_path=fp, line=i, ftype="unsafe_web_config", severity="high", message="CORS allow-all detected", evidence=ln, recommendation="Restrict allowed origins")
            if "localhost" in low:
                self._add_finding(findings, file_path=fp, line=i, ftype="informational_network", severity="low", message="Hardcoded localhost detected", evidence=ln, recommendation="Ensure not used in production builds")

            if re.search(r"(?i)f[\"']\s*(select|insert|update|delete)\b", ln):
                self._add_finding(findings, file_path=fp, line=i, ftype="sql_injection_risk", severity="high", message="SQL f-string detected", evidence=ln, recommendation="Use parameterized queries")

            if "../" in ln or "..\\" in ln:
                self._add_finding(findings, file_path=fp, line=i, ftype="path_traversal", severity="high", message="Path traversal marker detected", evidence=ln, recommendation="Normalize and validate paths")
            if "remove-item -recurse -force" in low or "rm -rf" in low or "del /s /q" in low:
                self._add_finding(findings, file_path=fp, line=i, ftype="dangerous_delete", severity="critical", message="Destructive delete command found", evidence=ln, recommendation="Use sandboxed/allowlisted deletion logic")

            if any(marker in ln for marker in _PROMPT_MARKERS) and fp.endswith((".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css")):
                self._add_finding(findings, file_path=fp, line=i, ftype="prompt_overwrite_marker", severity="high", message="Prompt-overwrite marker in code file", evidence=ln, recommendation="Remove prompt text from source files")

        severities = self.summarize_findings(findings).get("by_severity", {})
        return {
            "ok": True,
            "file": fp,
            "findings": findings,
            "total_findings": len(findings),
            "by_severity": severities,
        }

    def scan_file(self, path: str | Path) -> dict[str, Any]:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return {"ok": False, "file": str(p), "error": "file_not_found", "findings": []}
        try:
            raw = p.read_bytes()
        except OSError as e:
            return {"ok": False, "file": str(p), "error": str(e), "findings": []}
        if b"\x00" in raw:
            return {"ok": True, "file": str(p), "skipped_binary": True, "findings": []}
        text = raw.decode("utf-8", errors="replace")
        out = self.scan_text(text, file_path=str(p).replace("\\", "/"))
        return out

    def scan_project(self, root: str | Path, patterns: list[str] | None = None, max_files: int = 500) -> dict[str, Any]:
        base = Path(root).resolve()
        pats = tuple(patterns or _DEFAULT_PATTERNS)
        findings: list[dict[str, Any]] = []
        scanned = 0
        skipped_files: list[str] = []
        seen: set[Path] = set()
        for pat in pats:
            for p in base.rglob(pat):
                if scanned >= max_files:
                    break
                if p in seen:
                    continue
                seen.add(p)
                if not p.is_file():
                    continue
                rel = p.relative_to(base)
                if any(part in _IGNORED_DIRS for part in rel.parts):
                    continue
                if p.stat().st_size > 2_000_000:
                    skipped_files.append(rel.as_posix())
                    continue
                raw = p.read_bytes()
                if b"\x00" in raw:
                    skipped_files.append(rel.as_posix())
                    continue
                text = raw.decode("utf-8", errors="replace")
                res = self.scan_text(text, file_path=rel.as_posix())
                findings.extend(res["findings"])
                scanned += 1
            if scanned >= max_files:
                break
        result = {
            "ok": True,
            "root": str(base),
            "scanned_files": scanned,
            "skipped_files": skipped_files,
            "total_findings": len(findings),
            "findings": findings,
        }
        result["summary"] = self.summarize_findings(findings)
        return result

    def classify_finding(self, finding: dict[str, Any]) -> dict[str, Any]:
        f = dict(finding)
        sev = str(f.get("severity", "low")).lower()
        if sev not in {"low", "medium", "high", "critical"}:
            sev = "low"
        f["severity"] = sev
        if "recommendation" not in f or not f["recommendation"]:
            f["recommendation"] = "Review and remediate finding"
        return f

    def summarize_findings(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        by_severity = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        by_type: dict[str, int] = {}
        for item in findings:
            c = self.classify_finding(item)
            by_severity[c["severity"]] += 1
            t = str(c.get("type", "unknown"))
            by_type[t] = by_type.get(t, 0) + 1
        return {"by_severity": by_severity, "by_type": by_type}

    def risk_report(self, scan_result: dict[str, Any]) -> dict[str, Any]:
        findings = [self.classify_finding(f) for f in scan_result.get("findings", [])]
        summary = self.summarize_findings(findings)
        by_severity = summary["by_severity"]
        by_type = summary["by_type"]
        if by_severity["critical"] > 0:
            level = "critical"
        elif by_severity["high"] > 0:
            level = "high"
        elif by_severity["medium"] > 0:
            level = "medium"
        else:
            level = "low"
        critical_files = sorted({f["file"] for f in findings if f["severity"] in {"critical", "high"}})
        recs = []
        if by_severity["critical"] > 0:
            recs.append("Block release until critical findings are fixed")
        if by_type.get("hardcoded_secret", 0) > 0:
            recs.append("Rotate and remove hardcoded credentials")
        if by_type.get("dangerous_shell", 0) > 0:
            recs.append("Replace shell execution with safe argv invocation")
        if not recs:
            recs.append("Continue periodic security scanning")
        return {
            "ok": True,
            "risk_level": level,
            "total_findings": len(findings),
            "by_severity": by_severity,
            "by_type": by_type,
            "critical_files": critical_files,
            "recommendations": recs,
            "findings": findings,
        }

    def export_report(self, report: dict[str, Any], format: str = "json") -> str:
        fmt = (format or "json").lower()
        if fmt == "json":
            return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
        raise ValueError(f"Unsupported report format: {format}")

    def health(self) -> dict[str, Any]:
        return {"ok": True, "status": "ready", "module": "agent_security_scanner", "class": "SecurityScanner"}

    def describe(self) -> str:
        return "SecurityScanner"


_INSTANCE: SecurityScanner | None = None


def get_instance(project_root: Path | str | None = None) -> SecurityScanner:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = SecurityScanner(project_root)
    return _INSTANCE


AgentSecurityScanner = SecurityScanner

__all__ = ["SecurityScanner", "AgentSecurityScanner", "get_instance"]
