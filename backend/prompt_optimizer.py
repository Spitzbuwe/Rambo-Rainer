"""
PromptOptimizer: erkennt Typ, Komponenten, Anforderungen und Constraints.
"""
from __future__ import annotations

import re
from typing import Any


class PromptOptimizer:
    def analyze_prompt(self, prompt: str) -> dict[str, Any]:
        return {
            "prompt": prompt,
            "type": self.detect_type(prompt),
            "components": self.extract_components(prompt),
            "requirements": self.extract_requirements(prompt),
            "constraints": self.extract_constraints(prompt),
            "output_format": self.detect_output_format(prompt),
        }

    def detect_type(self, prompt: str) -> str:
        p = (prompt or "").lower()
        if any(k in p for k in ["icon", "ico", "png", "hintergrund entfernen"]):
            return "icon"
        if any(k in p for k in ["build", "npm", "electron-builder", "installer"]):
            return "build"
        if any(k in p for k in ["electron", "desktop app", "preload", "main.js"]):
            return "electron_app"
        if any(k in p for k in ["react", "component", "useeffect", "usestate", "jsx"]):
            return "react_app"
        return "general"

    def extract_components(self, prompt: str) -> list[str]:
        p = prompt or ""
        found = re.findall(r"\b[\w\-/]+\.(?:py|js|jsx|ts|tsx|json|md|css|html|ico|png)\b", p, flags=re.I)
        folders = re.findall(r"\b(?:src|backend|frontend|electron|assets|installer|components|templates)\b", p, flags=re.I)
        out = []
        for item in found + folders:
            if item not in out:
                out.append(item)
        return out

    def extract_requirements(self, prompt: str) -> list[str]:
        p = (prompt or "").lower()
        req = []
        pairs = [
            ("API Calls", ["api", "fetch", "axios"]),
            ("Forms", ["form", "input", "validation"]),
            ("State Management", ["state", "usestate", "store"]),
            ("IPC", ["ipc", "preload", "contextbridge"]),
            ("Build/Installer", ["installer", "build", "nsis", "electron-builder"]),
        ]
        for label, keys in pairs:
            if any(k in p for k in keys):
                req.append(label)
        return req

    def extract_constraints(self, prompt: str) -> dict[str, Any]:
        p = (prompt or "").lower()
        return {
            "language": "python" if "python" in p else ("javascript" if "javascript" in p or "js" in p else "mixed"),
            "framework": "react" if "react" in p else ("electron" if "electron" in p else "generic"),
            "platform": "windows" if "windows" in p or "win" in p else "cross-platform",
        }

    def detect_output_format(self, prompt: str) -> str:
        p = (prompt or "").lower()
        if "json" in p:
            return "json"
        if "markdown" in p or ".md" in p:
            return "markdown"
        if "code" in p or "script" in p:
            return "code"
        return "text"
