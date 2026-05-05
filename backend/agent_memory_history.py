from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


class MemoryHistoryAgent:
    __test__ = False

    def __init__(self, app_root: Path, store_file: Path | None = None):
        self.app_root = Path(app_root).resolve()
        self.store_file = Path(store_file or (self.app_root / "data" / "agent_memory_history.json")).resolve()
        self.project_knowledge_file = (self.app_root / "data" / "project_knowledge_base.json").resolve()
        self.feature_memory_file = (self.app_root / "data" / "feature_memory.json").resolve()
        self.error_kb_file = (self.app_root / "data" / "error_knowledge_base.json").resolve()
        self.check_intelligence_file = (self.app_root / "data" / "check_intelligence.json").resolve()
        self.max_entries = 200
        self.default_project_id = "rambo_builder_local"

    def _norm_project_id(self, project_id: str | None) -> str:
        pid = str(project_id or "").strip()
        return pid or self.default_project_id

    def _sanitize_text(self, value: str) -> str:
        txt = str(value or "")
        for marker in ("sk-", "api_key", "authorization:", "bearer "):
            if marker in txt.lower():
                return "[redacted]"
        return txt

    def _load(self) -> dict[str, object]:
        if not self.store_file.exists():
            return {"ok": True, "entries": []}
        try:
            raw = json.loads(self.store_file.read_text(encoding="utf-8"))
            entries = raw.get("entries") if isinstance(raw, dict) else []
            return {"ok": True, "entries": entries if isinstance(entries, list) else []}
        except Exception:
            return {"ok": True, "entries": []}

    def _save(self, entries: list[dict[str, object]]) -> None:
        self.store_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {"entries": entries[: self.max_entries]}
        self.store_file.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def _read_json_file(self, path: Path, default: dict[str, object] | None = None) -> dict[str, object]:
        if not path.exists():
            return dict(default or {})
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else dict(default or {})
        except Exception:
            return dict(default or {})

    def _write_json_file(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def _error_fingerprint(self, error_summary: str, failed_tests: list[str] | None = None) -> str:
        base = str(error_summary or "").strip().lower()
        tests = "|".join(sorted([str(t).strip().lower() for t in list(failed_tests or []) if str(t).strip()][:5]))
        joined = f"{base}|{tests}".strip("|")
        return re.sub(r"[^a-z0-9_|:-]+", "_", joined)[:180]

    def record(
        self,
        *,
        feature: str,
        step: str,
        status: str,
        attempted_files: list[str] | None = None,
        notes: str = "",
        run_id: str = "",
        task_id: str = "",
        commit_id: str = "",
        checks: list[dict] | None = None,
        failed_tests: list[str] | None = None,
        error_summary: str = "",
        project_id: str = "",
    ) -> dict[str, object]:
        feat = str(feature or "").strip() or "general"
        stp = str(step or "").strip() or "unknown"
        stat = str(status or "").strip() or "unknown"
        files = [str(p).replace("\\", "/").strip() for p in list(attempted_files or []) if str(p).strip()]
        check_rows = list(checks or [])
        failed = [str(x).replace("\\", "/").strip() for x in list(failed_tests or []) if str(x).strip()]
        err = self._sanitize_text(str(error_summary or "").strip())
        fp = self._error_fingerprint(err, failed)
        entry = {
            "id": f"mem_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "feature": feat,
            "step": stp,
            "status": stat,
            "run_id": str(run_id or "").strip(),
            "task_id": str(task_id or "").strip(),
            "commit_id": str(commit_id or "").strip(),
            "attempted_files": files,
            "checks": check_rows,
            "failed_tests": failed,
            "error_summary": err,
            "error_fingerprint": fp,
            "notes": self._sanitize_text(str(notes or "").strip()),
            "success": stat in {"ok", "success", "done"},
            "project_id": self._norm_project_id(project_id),
        }
        loaded = self._load()
        entries = list(loaded.get("entries") or [])
        entries.insert(0, entry)
        self._save(entries)
        try:
            self._update_feature_memory(
                feature=feat,
                files=files,
                checks=check_rows,
                notes=entry.get("notes") or "",
                project_id=entry.get("project_id") or "",
            )
            self._update_check_intelligence(files=files, checks=check_rows, project_id=entry.get("project_id") or "")
            if err:
                self.record_error_pattern(
                    error_summary=err,
                    failed_tests=failed,
                    failed_files=files,
                    repair_plan="",
                    repair_patch_plan=[],
                    checks_after_fix=[str((c or {}).get("check") or "") for c in check_rows if str((c or {}).get("check") or "").strip()],
                    success=entry.get("success") is True,
                    related_commit=entry.get("commit_id") or "",
                    project_id=entry.get("project_id") or "",
                )
        except Exception:
            pass
        return {"ok": True, "entry": entry, "count": len(entries[: self.max_entries])}

    def build_project_knowledge_base(self) -> dict[str, object]:
        modules = {
            "backend_endpoints": ["backend/main.py"],
            "frontend_areas": ["frontend/app.js", "frontend/index.html", "frontend/style.css"],
            "test_files": [
                "tests/test_agent_run_controller_start.py",
                "tests/test_agent_test_runner.py",
                "tests/test_agent_memory_history.py",
            ],
            "allowed_files": ["backend/**", "frontend/**", "tests/**", "data/**"],
            "blocked_files": ["../*", "Downloads/**", "electron/**", "rambo_ui/**", "src/components/**", "node_modules/**"],
            "runtime_artifacts": ["data/agent_memory_history.json", "data/run_state.json", ".claude/**"],
            "known_warnings": ["requests dependency mismatch", "google.generativeai deprecation warning"],
        }
        important_files = [
            {"path": "backend/main.py", "role": "zentrale API-Datei", "risk_level": "high"},
            {"path": "frontend/app.js", "role": "zentrale UI-Logik", "risk_level": "high"},
            {"path": "tests/test_agent_run_controller_start.py", "role": "Agent-Run Kern-Tests", "risk_level": "high"},
        ]
        payload = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "project_root": str(self.app_root).replace("\\", "/"),
            "project_structure": ["backend", "frontend", "tests", "data"],
            "important_files": important_files,
            "known_modules": modules,
            "typical_checks_by_area": {
                "frontend/app.js": ["node_check_app", "pytest tests/test_agent_run_controller_start.py -q"],
                "backend/main.py": ["py_compile_main", "pytest tests/test_agent_run_controller_start.py -q", "pytest_all"],
                "backend/agent_test_runner.py": ["pytest tests/test_agent_test_runner.py -q", "pytest tests/test_agent_level20_test_runner_api.py -q", "pytest_all"],
            },
        }
        self._write_json_file(self.project_knowledge_file, payload)
        return {"ok": True, "knowledge_base": payload}

    def _update_feature_memory(self, *, feature: str, files: list[str], checks: list[dict], notes: str, project_id: str = "") -> None:
        raw = self._read_json_file(self.feature_memory_file, {"features": []})
        pid = self._norm_project_id(project_id)
        projects = dict(raw.get("projects") or {})
        scoped = dict(projects.get(pid) or {})
        items = list(scoped.get("features") or raw.get("features") or [])
        fmap = {str((x or {}).get("feature_name") or "").strip().lower(): dict(x or {}) for x in items}
        key = str(feature or "general").strip().lower()
        row = fmap.get(key, {
            "feature_name": feature or "general",
            "description": "",
            "related_files": [],
            "related_tests": [],
            "known_checks": [],
            "last_changed_at": "",
            "last_commit": "",
            "risk_level": "medium",
            "notes": "",
        })
        row["related_files"] = sorted(set(list(row.get("related_files") or []) + files))
        row["related_tests"] = sorted(set(list(row.get("related_tests") or []) + [f for f in files if f.startswith("tests/")]))
        row["known_checks"] = sorted(set(list(row.get("known_checks") or []) + [str((c or {}).get("check") or "") for c in checks if str((c or {}).get("check") or "").strip()]))
        row["last_changed_at"] = datetime.now().isoformat(timespec="seconds")
        row["notes"] = str(notes or row.get("notes") or "")
        if any(f.startswith("backend/main.py") or "confirm" in f for f in files):
            row["risk_level"] = "high"
        fmap[key] = row
        scoped["features"] = sorted(fmap.values(), key=lambda x: str(x.get("feature_name") or "").lower())
        scoped["updated_at"] = datetime.now().isoformat(timespec="seconds")
        projects[pid] = scoped
        top_features = scoped["features"] if pid == self.default_project_id else list(raw.get("features") or [])
        out = {"updated_at": datetime.now().isoformat(timespec="seconds"), "features": top_features, "projects": projects}
        self._write_json_file(self.feature_memory_file, out)

    def find_similar_tasks(self, *, task_text: str = "", feature: str = "", files: list[str] | None = None, limit: int = 5, project_id: str = "") -> dict[str, object]:
        text = str(task_text or "").strip().lower()
        feat = str(feature or "").strip().lower()
        fset = {str(x).strip().lower() for x in list(files or []) if str(x).strip()}
        entries = list(self._load().get("entries") or [])
        pid = self._norm_project_id(project_id)
        scored: list[tuple[int, dict[str, object]]] = []
        for e in entries:
            ep = self._norm_project_id(e.get("project_id"))
            if ep != pid:
                continue
            score = 0
            efeat = str(e.get("feature") or "").lower()
            if feat and feat in efeat:
                score += 3
            if text and text in str(e.get("notes") or "").lower():
                score += 2
            efiles = {str(x).strip().lower() for x in list(e.get("attempted_files") or []) if str(x).strip()}
            score += min(3, len(fset.intersection(efiles)))
            if score > 0:
                scored.append((score, e))
        scored.sort(key=lambda x: (-x[0], str((x[1] or {}).get("timestamp") or "")), reverse=False)
        return {"ok": True, "matches": [x[1] for x in scored[: max(1, int(limit or 5))]], "count": len(scored)}

    def record_error_pattern(
        self,
        *,
        error_summary: str,
        failed_tests: list[str] | None = None,
        failed_files: list[str] | None = None,
        root_cause_hint: str = "",
        repair_plan: str = "",
        repair_patch_plan: list[dict] | None = None,
        checks_after_fix: list[str] | None = None,
        success: bool = False,
        related_commit: str = "",
        project_id: str = "",
    ) -> dict[str, object]:
        raw = self._read_json_file(self.error_kb_file, {"errors": []})
        pid = self._norm_project_id(project_id)
        projects = dict(raw.get("projects") or {})
        scoped = dict(projects.get(pid) or {})
        rows = list(scoped.get("errors") or raw.get("errors") or [])
        entry = {
            "id": f"err_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "error_fingerprint": self._error_fingerprint(error_summary, failed_tests),
            "error_summary": str(error_summary or "").strip(),
            "failed_tests": [str(x) for x in list(failed_tests or []) if str(x).strip()],
            "failed_files": [str(x) for x in list(failed_files or []) if str(x).strip()],
            "root_cause_hint": str(root_cause_hint or "").strip(),
            "repair_plan": str(repair_plan or "").strip(),
            "repair_patch_plan": list(repair_patch_plan or []),
            "checks_after_fix": [str(x) for x in list(checks_after_fix or []) if str(x).strip()],
            "success": bool(success),
            "related_commit": str(related_commit or "").strip(),
            "project_id": pid,
        }
        rows.insert(0, entry)
        scoped["errors"] = rows[: self.max_entries]
        scoped["updated_at"] = datetime.now().isoformat(timespec="seconds")
        projects[pid] = scoped
        self._write_json_file(self.error_kb_file, {"updated_at": datetime.now().isoformat(timespec="seconds"), "errors": list(raw.get("errors") or []), "projects": projects})
        return {"ok": True, "entry": entry}

    def _update_check_intelligence(self, *, files: list[str], checks: list[dict], project_id: str = "") -> None:
        raw = self._read_json_file(self.check_intelligence_file, {"files": {}})
        pid = self._norm_project_id(project_id)
        projects = dict(raw.get("projects") or {})
        scoped = dict(projects.get(pid) or {})
        rows = dict(scoped.get("files") or raw.get("files") or {})
        for f in files:
            key = str(f)
            cur = dict(rows.get(key) or {"successful_checks": {}, "failed_checks": {}})
            ok_map = dict(cur.get("successful_checks") or {})
            fail_map = dict(cur.get("failed_checks") or {})
            for c in checks:
                name = str((c or {}).get("check") or "").strip()
                if not name:
                    continue
                if bool((c or {}).get("ok")):
                    ok_map[name] = int(ok_map.get(name) or 0) + 1
                else:
                    fail_map[name] = int(fail_map.get(name) or 0) + 1
            cur["successful_checks"] = ok_map
            cur["failed_checks"] = fail_map
            rows[key] = cur
        scoped["files"] = rows
        scoped["updated_at"] = datetime.now().isoformat(timespec="seconds")
        projects[pid] = scoped
        top_files = rows if pid == self.default_project_id else dict(raw.get("files") or {})
        self._write_json_file(self.check_intelligence_file, {"updated_at": datetime.now().isoformat(timespec="seconds"), "files": top_files, "projects": projects})

    def recommend_checks_for_files(self, *, files: list[str], project_id: str = "") -> dict[str, object]:
        raw = self._read_json_file(self.check_intelligence_file, {"files": {}})
        pid = self._norm_project_id(project_id)
        projects = dict(raw.get("projects") or {})
        scoped = dict(projects.get(pid) or {})
        known = dict(scoped.get("files") or raw.get("files") or {})
        ordered: list[str] = []
        for f in files:
            fkey = str(f)
            row = dict(known.get(fkey) or {})
            ok_map = dict(row.get("successful_checks") or {})
            fail_map = dict(row.get("failed_checks") or {})
            for name, _ in sorted(ok_map.items(), key=lambda x: -int(x[1])):
                if name not in ordered:
                    ordered.append(name)
            for name, _ in sorted(fail_map.items(), key=lambda x: -int(x[1])):
                if name not in ordered:
                    ordered.append(name)
            if "frontend/app.js" in fkey and "node_check_app" not in ordered:
                ordered.append("node_check_app")
            if "backend/main.py" in fkey and "py_compile_main" not in ordered:
                ordered.append("py_compile_main")
        if any("backend/main.py" in str(f) for f in files) and "pytest_all" not in ordered:
            ordered.append("pytest_all")
        return {"ok": True, "recommended_checks": ordered[:8]}

    def list_history(self, *, limit: int = 30, project_id: str = "") -> dict[str, object]:
        loaded = self._load()
        pid = self._norm_project_id(project_id)
        entries = [e for e in list(loaded.get("entries") or []) if self._norm_project_id(e.get("project_id")) == pid]
        lim = max(1, min(int(limit or 30), self.max_entries))
        return {"ok": True, "entries": entries[:lim], "count": len(entries)}

    def summarize(self, *, limit: int = 100, project_id: str = "") -> dict[str, object]:
        loaded = self._load()
        pid = self._norm_project_id(project_id)
        base = [e for e in list(loaded.get("entries") or []) if self._norm_project_id(e.get("project_id")) == pid]
        entries = base[: max(1, min(int(limit or 100), self.max_entries))]
        feature_map: dict[str, dict[str, object]] = {}
        error_map: dict[str, dict[str, object]] = {}
        for e in entries:
            feat = str(e.get("feature") or "general")
            current = feature_map.setdefault(
                feat,
                {"feature": feat, "attempts": 0, "successes": 0, "files": set(), "successful_checks": set(), "failed_checks": set()},
            )
            current["attempts"] = int(current["attempts"]) + 1
            if bool(e.get("success")):
                current["successes"] = int(current["successes"]) + 1
            for f in list(e.get("attempted_files") or []):
                current["files"].add(str(f))
            for c in list(e.get("checks") or []):
                name = str((c or {}).get("check") or (c or {}).get("name") or "").strip()
                if not name:
                    continue
                if bool((c or {}).get("ok")):
                    current["successful_checks"].add(name)
                else:
                    current["failed_checks"].add(name)
            fp = str(e.get("error_fingerprint") or "").strip()
            if fp:
                er = error_map.setdefault(fp, {"fingerprint": fp, "count": 0, "examples": []})
                er["count"] = int(er["count"]) + 1
                if len(er["examples"]) < 3:
                    er["examples"].append(
                        {
                            "feature": feat,
                            "error_summary": str(e.get("error_summary") or ""),
                            "failed_tests": list(e.get("failed_tests") or [])[:3],
                        }
                    )
        features = []
        for v in feature_map.values():
            features.append(
                {
                    "feature": v["feature"],
                    "attempts": v["attempts"],
                    "successes": v["successes"],
                    "files": sorted(list(v["files"])),
                    "successful_checks": sorted(list(v["successful_checks"])),
                    "failed_checks": sorted(list(v["failed_checks"])),
                }
            )
        features.sort(key=lambda x: (-int(x["attempts"]), str(x["feature"]).lower()))
        similar_errors = sorted(list(error_map.values()), key=lambda x: -int(x["count"]))
        return {"ok": True, "feature_summary": features, "similar_errors": similar_errors, "entry_count": len(entries)}

    def find_similar_errors(self, *, error_summary: str = "", failed_tests: list[str] | None = None, limit: int = 5, project_id: str = "") -> dict[str, object]:
        fp = self._error_fingerprint(error_summary, failed_tests or [])
        loaded = self._load()
        pid = self._norm_project_id(project_id)
        entries = [e for e in list(loaded.get("entries") or []) if self._norm_project_id(e.get("project_id")) == pid]
        hits = [e for e in entries if str(e.get("error_fingerprint") or "") == fp]
        return {"ok": True, "fingerprint": fp, "matches": hits[: max(1, int(limit or 5))], "count": len(hits)}


_INSTANCE: MemoryHistoryAgent | None = None


def get_instance(app_root: Path | None = None, store_file: Path | None = None) -> MemoryHistoryAgent:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = MemoryHistoryAgent(app_root or Path("."), store_file=store_file)
    return _INSTANCE
