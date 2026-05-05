"""DomainTrainer — lokale Keyword-/JSON-Wissensbasis, deterministisch, ohne externe Modelle."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)

_KB_VERSION = 1

_DEFAULT_DOMAINS: dict[str, dict[str, Any]] = {
    "python_backend": {
        "keywords": ("flask", "fastapi", "django", "uvicorn", "gunicorn", "wsgi", "asyncio", "sqlalchemy"),
        "rules": ("rule:validate_input", "rule:check_db_pool"),
    },
    "javascript_frontend": {
        "keywords": ("react", "vue", "vite", "webpack", "typescript", "eslint", "npm", "dom", "css"),
        "rules": ("rule:lint_bundle",),
    },
    "electron_desktop": {
        "keywords": (
            "electron",
            "vite",
            "dist",
            "index.html",
            "preload",
            "asar",
            "main.js",
            "renderer",
            "white screen",
            "blank window",
        ),
        "rules": ("rule:check_loadfile", "rule:verify_dist_paths"),
    },
    "testing": {
        "keywords": ("pytest", "py_compile", "unittest", "coverage", "mock", "fixture", "test failed", "assert"),
        "rules": ("rule:run_smoke_subset",),
    },
    "git_workflow": {
        "keywords": ("git commit", "git status", "git diff", "merge conflict", "rebase", "branch", "stash"),
        "rules": ("rule:inspect_diff",),
    },
    "local_ai_ollama": {
        "keywords": ("ollama", "llama", "mistral", "model pull", "provider", "generate", "embedding", "11434"),
        "rules": ("rule:check_model_tags",),
    },
    "windows_powershell": {
        "keywords": ("powershell", "cmdlet", "winerror", "executionpolicy", "set-location", "get-childitem"),
        "rules": ("rule:normalize_paths",),
    },
}

_STRATEGY: dict[str, dict[str, list[str]]] = {
    "python_backend": {
        "recommended_steps": ("step_audit_routes", "step_check_env", "step_profile_sql"),
        "risks": ("risk_unhandled_exception", "risk_secret_leak"),
        "required_tests": ("test_py_compile", "test_api_smoke"),
    },
    "javascript_frontend": {
        "recommended_steps": ("step_build_prod", "step_check_console_errors"),
        "risks": ("risk_bundle_size", "risk_cors"),
        "required_tests": ("test_lint", "test_e2e_smoke"),
    },
    "electron_desktop": {
        "recommended_steps": ("step_audit_dist", "step_check_preload", "step_verify_main_entry"),
        "risks": ("risk_missing_asset", "risk_wrong_baseurl"),
        "required_tests": ("test_window_opens", "test_packaged_binary"),
    },
    "testing": {
        "recommended_steps": ("step_reproduce_failure", "step_minimize_case"),
        "risks": ("risk_flaky_timing",),
        "required_tests": ("test_pytest_targeted", "test_regression_subset"),
    },
    "git_workflow": {
        "recommended_steps": ("step_status", "step_diff", "step_branch_check"),
        "risks": ("risk_lost_changes", "risk_merge_conflict"),
        "required_tests": ("test_clean_worktree",),
    },
    "local_ai_ollama": {
        "recommended_steps": ("step_list_models", "step_verify_endpoint", "step_retry_generate"),
        "risks": ("risk_model_missing", "risk_timeout"),
        "required_tests": ("test_ollama_tags",),
    },
    "windows_powershell": {
        "recommended_steps": ("step_print_path", "step_verify_policy", "step_quote_args"),
        "risks": ("risk_path_escaping", "risk_wrong_cwd"),
        "required_tests": ("test_script_syntax",),
    },
    "general": {
        "recommended_steps": ("step_read_logs", "step_reproduce"),
        "risks": ("risk_unknown_domain",),
        "required_tests": ("test_smoke",),
    },
}

_HINTS: dict[str, tuple[str, ...]] = {
    "python_backend": ("hint:entrypoint", "hint:dependency_versions"),
    "javascript_frontend": ("hint:sourcemaps", "hint:network_tab"),
    "electron_desktop": ("hint:asar_unpack", "hint:preload_path"),
    "testing": ("hint:isolate_test", "hint:fixtures"),
    "git_workflow": ("hint:stash_safe", "hint:diff_stat"),
    "local_ai_ollama": ("hint:model_tag", "hint:ctx_size"),
    "windows_powershell": ("hint:literalpath", "hint:errorrecord"),
    "general": ("hint:minimal_repro",),
}


class DomainTrainer:
    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root or ".").resolve()
        self._registry: dict[str, dict[str, Any]] = {
            k: {"keywords": tuple(v["keywords"]), "rules": tuple(v.get("rules", ()))}
            for k, v in _DEFAULT_DOMAINS.items()
        }
        self._examples: dict[str, list[dict[str, Any]]] = {k: [] for k in self._registry}
        self._examples.setdefault("general", [])

    def add_domain(self, name: str, keywords: list[str] | tuple[str, ...] | None = None, rules: list[str] | tuple[str, ...] | None = None) -> None:
        kws = tuple(keywords or ())
        rls = tuple(rules or ())
        self._registry[name] = {"keywords": kws, "rules": rls}
        self._examples.setdefault(name, [])

    def scan_project_text(self, max_files: int = 80) -> str:
        buf: list[str] = []
        n = 0
        for pat in ("**/*.py", "**/*.md", "**/*.js", "**/*.ts"):
            for p in self.project_root.glob(pat):
                if not p.is_file() or ".git" in p.parts:
                    continue
                if n >= max_files:
                    return "\n".join(buf)
                try:
                    buf.append(p.read_text(encoding="utf-8", errors="replace")[:4000])
                except OSError:
                    continue
                n += 1
        return "\n".join(buf)

    def _score_blob(self, blob: str) -> tuple[str, float, dict[str, float], dict[str, list[str]]]:
        low = blob.lower()
        scores: dict[str, float] = {}
        matched: dict[str, list[str]] = {}
        for dom, spec in sorted(self._registry.items()):
            kws = spec["keywords"]
            hits = [k for k in kws if k in low]
            scores[dom] = float(len(hits))
            matched[dom] = hits
        ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        best = ranked[0][0] if ranked else "general"
        top = ranked[0][1] if ranked else 0.0
        second = ranked[1][1] if len(ranked) > 1 else 0.0
        if top <= 0.0:
            return "general", 0.0, scores, matched
        conf = min(1.0, top / (top + second + 1e-6))
        return best, conf, scores, matched

    def detect_domain(self, task_or_error: str | None = None) -> dict[str, Any]:
        blob = (task_or_error or "").strip()
        if not blob:
            blob = self.scan_project_text()
        best, conf, scores, matched = self._score_blob(blob)
        low = blob.lower()
        primary = best
        if best == "python_backend" and any(k in low for k in ("flask", "fastapi", "django")):
            primary = "web"
        mk = sorted(set(matched.get(best, [])))
        return {
            "domain": best,
            "primary": primary,
            "confidence": round(float(conf), 6),
            "scores": scores,
            "matched_keywords": mk,
        }

    def add_example(
        self,
        domain: str,
        task: str,
        solution: str,
        success: bool = True,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self._examples.setdefault(domain, []).append(
            {
                "task": task[:2000],
                "solution": solution[:4000],
                "success": bool(success),
                "metadata": dict(metadata or {}),
            }
        )

    def recommend_strategy(self, task_or_error: str) -> dict[str, Any]:
        det = self.detect_domain(task_or_error)
        dom = det["domain"]
        pack = _STRATEGY.get(dom, _STRATEGY["general"])
        return {
            "domain": dom,
            "recommended_steps": list(pack["recommended_steps"]),
            "risks": list(pack["risks"]),
            "required_tests": list(pack["required_tests"]),
        }

    def domain_stats(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for dom in sorted(set(self._registry) | set(self._examples)):
            ex = self._examples.get(dom, [])
            rules = self._registry.get(dom, {}).get("rules", ())
            out[dom] = {
                "examples": len(ex),
                "custom_rules": len(tuple(rules)),
                "keywords_registered": len(self._registry.get(dom, {}).get("keywords", ())),
            }
        return {"by_domain": out}

    def export_knowledge(self) -> dict[str, Any]:
        return {
            "version": _KB_VERSION,
            "domains": {
                k: {"keywords": list(v["keywords"]), "rules": list(v.get("rules", ()))}
                for k, v in sorted(self._registry.items())
            },
            "examples": {k: list(v) for k, v in sorted(self._examples.items())},
        }

    def import_knowledge(self, data: dict[str, Any]) -> None:
        if int(data.get("version", 0)) < 1:
            logger.warning("import_knowledge: unknown version")
        for name, spec in sorted(data.get("domains", {}).items()):
            self.add_domain(
                name,
                keywords=spec.get("keywords") or (),
                rules=spec.get("rules") or (),
            )
        for dom, rows in data.get("examples", {}).items():
            for row in rows:
                if isinstance(row, dict):
                    self.add_example(
                        dom,
                        str(row.get("task", "")),
                        str(row.get("solution", "")),
                        bool(row.get("success", True)),
                        row.get("metadata"),
                    )

    def adaptation_hints(self) -> list[str]:
        dom = self.detect_domain(None)["domain"]
        return list(_HINTS.get(dom, _HINTS["general"]))

    def build_domain_profile(self) -> dict[str, Any]:
        det = self.detect_domain(None)
        return {
            "project_root": str(self.project_root),
            "detection": det,
            "adaptation_hints": self.adaptation_hints(),
        }

    def export_profile_json(self) -> dict[str, Any]:
        return self.build_domain_profile()

    def health(self) -> dict[str, Any]:
        return {
            "module": "agent_domain_trainer",
            "class": "DomainTrainer",
            "ok": True,
            "status": "ready",
            "domain_count": len(self._registry),
        }

    def describe(self) -> str:
        return "DomainTrainer"


def get_instance(project_root: Path | str | None = None) -> DomainTrainer:
    return DomainTrainer(project_root)


__all__ = ["DomainTrainer", "get_instance"]
