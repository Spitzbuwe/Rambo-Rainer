"""
BuildSystem: orchestriert npm/electron Build-Schritte.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


class BuildSystem:
    def _run(self, cmd: list[str], project_path: str | Path):
        fixed_cmd = list(cmd or [])
        if fixed_cmd and str(fixed_cmd[0]).lower() == "npm":
            fixed_cmd[0] = "npm.cmd"
        cp = subprocess.run(
            fixed_cmd,
            cwd=Path(project_path),
            capture_output=True,
            text=True,
            check=False,
        )
        return {
            "ok": cp.returncode == 0,
            "returncode": cp.returncode,
            "stdout": cp.stdout or "",
            "stderr": cp.stderr or "",
            "command": " ".join(fixed_cmd),
        }

    def run_npm_install(self, project_path: str | Path):
        return self._run(["npm", "install"], project_path)

    def run_npm_build(self, project_path: str | Path):
        return self._run(["npm", "run", "build"], project_path)

    def run_electron_builder(self, project_path: str | Path):
        return self._run(["npm", "run", "build:win"], project_path)

    def build_electron_app(self, spec: dict):
        root = Path(spec.get("project_path") or ".")
        electron_path = Path(spec.get("electron_path") or (root / "electron"))
        ui_path = Path(spec.get("ui_path") or (root / "rambo_ui"))
        steps = []

        steps.append({"step": "ui_npm_install", **self.run_npm_install(ui_path)})
        if not steps[-1]["ok"]:
            return {"ok": False, "steps": steps}

        steps.append({"step": "ui_build", **self.run_npm_build(ui_path)})
        if not steps[-1]["ok"]:
            return {"ok": False, "steps": steps}

        steps.append({"step": "electron_npm_install", **self.run_npm_install(electron_path)})
        if not steps[-1]["ok"]:
            return {"ok": False, "steps": steps}

        steps.append({"step": "electron_build", **self.run_electron_builder(electron_path)})
        return {"ok": steps[-1]["ok"], "steps": steps}
