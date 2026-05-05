from __future__ import annotations


class TradeOffAnalyzer:
    def analyze_tradeoffs(self, options):
        result = {}
        for option in options or []:
            result[option] = {
                "pros": self.find_pros(option),
                "cons": self.find_cons(option),
                "effort": self.estimate_effort(option),
                "risk": self.assess_risk(option),
            }
        return result

    def find_pros(self, option):
        pros_map = {
            "Python": ["Schnelle Entwicklung", "Großes Ökosystem", "Gut für Automation"],
            "C#": ["Gute Performance", "Windows-Integration", "Starke Toolchain"],
            "JavaScript": ["Web + Desktop", "Viele Libraries", "Schnelle UI-Iterationen"],
            "Go": ["Schnell", "Einfache Deployments", "Stabil für Services"],
            "Rust": ["Sehr hohe Performance", "Memory Safety", "Langfristig robust"],
        }
        return pros_map.get(option, ["Flexible Einsetzbarkeit"])

    def find_cons(self, option):
        cons_map = {
            "Python": ["CPU-intensive Aufgaben langsamer", "Packaging kann komplex sein"],
            "C#": ["Stärker an .NET gebunden", "Learning Curve für Nicht-.NET-Teams"],
            "JavaScript": ["Tooling-Komplexität", "Desktop-App Overhead (Electron)"],
            "Go": ["Weniger UI-Ökosystem", "Generics-Best-Practices noch im Wandel"],
            "Rust": ["Höhere Lernkurve", "Längere initiale Entwicklungszeit"],
        }
        return cons_map.get(option, ["Trade-offs projektspezifisch"])

    def estimate_effort(self, option):
        effort_map = {"Python": 3, "JavaScript": 4, "Go": 5, "C#": 6, "Rust": 8}
        return effort_map.get(option, 5)

    def assess_risk(self, option):
        risk_map = {"Python": "MEDIUM", "JavaScript": "MEDIUM", "Go": "LOW", "C#": "LOW", "Rust": "MEDIUM"}
        return risk_map.get(option, "MEDIUM")
