from __future__ import annotations

import re


class ImprovementSuggester:
    def analyze_code(self, code, language):
        text = str(code or "")
        lang = str(language or "").lower()
        issues = []
        issues.extend(self.check_performance(text, lang))
        issues.extend(self.check_code_quality(text, lang))
        issues.extend(self.check_error_handling(text, lang))
        issues.extend(self.check_testing(text, lang))
        suggestions = [self.fix_suggestion(issue) for issue in issues]
        return {
            "issues_found": len(issues),
            "issues": issues,
            "suggestions": suggestions,
            "priority": self.prioritize_suggestions(suggestions),
        }

    def check_performance(self, code, language):
        issues = []
        if code.count("for ") > 2:
            issues.append({
                "type": "Performance",
                "severity": "Medium",
                "description": "Mehrere Loop-Strukturen erkannt",
                "fix": "Algorithmus vereinfachen oder Zwischenergebnisse cachen",
            })
        return issues

    def check_code_quality(self, code, language):
        issues = []
        function_defs = re.findall(r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", code)
        if len(function_defs) == 0:
            issues.append({
                "type": "Code Quality",
                "severity": "Low",
                "description": "Keine klaren Funktionsgrenzen erkannt",
                "fix": "Logik in testbare Funktionen aufteilen",
            })
        if len(code.splitlines()) > 120:
            issues.append({
                "type": "Code Quality",
                "severity": "Medium",
                "description": "Codeblock ist relativ lang",
                "fix": "In kleinere Module/Funktionen schneiden",
            })
        return issues

    def check_error_handling(self, code, language):
        issues = []
        if language == "python" and "open(" in code and "try:" not in code:
            issues.append({
                "type": "Error Handling",
                "severity": "High",
                "description": "Dateioperation ohne Fehlerbehandlung",
                "fix": "try/except um I/O-Aufrufe ergänzen",
            })
        if "fetch(" in code and ".catch(" not in code and "try" not in code:
            issues.append({
                "type": "Error Handling",
                "severity": "Medium",
                "description": "Netzwerkaufruf ohne Fehlerpfad",
                "fix": "Fehlerbehandlung ergänzen (try/catch oder .catch)",
            })
        return issues

    def check_testing(self, code, language):
        issues = []
        text = code.lower()
        if "test_" not in text and "assert " not in text and "pytest" not in text:
            issues.append({
                "type": "Testing",
                "severity": "Medium",
                "description": "Keine Test-Hinweise im Code gefunden",
                "fix": "Unit-Tests für Kernlogik hinzufügen",
            })
        return issues

    def fix_suggestion(self, issue):
        return {
            "issue": issue.get("description"),
            "severity": issue.get("severity", "Medium"),
            "fix": issue.get("fix", "Konkreten Fix definieren"),
            "effort": "low" if issue.get("severity") == "Low" else ("high" if issue.get("severity") == "High" else "medium"),
        }

    def prioritize_suggestions(self, suggestions):
        rank = {"High": 1, "Medium": 2, "Low": 3}
        return sorted(suggestions, key=lambda s: rank.get(s.get("severity"), 999))
