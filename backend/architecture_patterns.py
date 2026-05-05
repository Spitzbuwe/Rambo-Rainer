from __future__ import annotations


class ArchitectureDecider:
    PATTERNS = {
        "monolith": {
            "description": "Alles in einer Anwendung",
            "best_for": ["kleine apps", "mvp", "single-team"],
            "pros": ["Einfach", "Schnell", "Debugging leichter"],
            "cons": ["Skalierung schwerer", "Gekoppeltes Deployment"],
        },
        "microservices": {
            "description": "Viele entkoppelte Services",
            "best_for": ["große apps", "multi-team", "skalierung"],
            "pros": ["Skalierbar", "Unabhängige Deployments", "Technologie-Flexibilität"],
            "cons": ["Höhere Komplexität", "Observability-Aufwand"],
        },
        "mvc": {
            "description": "Model-View-Controller",
            "best_for": ["web apps", "ui-fokus"],
            "pros": ["Separation of Concerns", "Gute Testbarkeit"],
            "cons": ["Etwas Overhead bei kleinen Projekten"],
        },
        "event_driven": {
            "description": "Event-basierte Verarbeitung",
            "best_for": ["real-time apps", "workflows", "asynchrone prozesse"],
            "pros": ["Reaktiv", "Entkoppelt", "Skaliert gut in Pipelines"],
            "cons": ["Debugging komplexer", "Eventual Consistency beachten"],
        },
    }

    def recommend_architecture(self, project_info):
        info = project_info or {}
        best = None
        best_score = -1
        for pattern_name in self.PATTERNS:
            score = self.calculate_fit(pattern_name, info)
            if score > best_score:
                best = pattern_name
                best_score = score
        return {
            "recommended": best,
            "pattern": self.PATTERNS.get(best, {}),
            "score": best_score,
            "reasoning": self.explain_architecture(best, info),
        }

    def pattern_library(self):
        return dict(self.PATTERNS)

    def calculate_fit(self, pattern, project_info):
        info = project_info or {}
        size = str(info.get("size") or "medium").lower()
        team_size = int(info.get("team_size") or 1)
        real_time = bool(info.get("real_time"))
        ui_focus = bool(info.get("ui_focus"))

        score = 0
        if pattern == "monolith" and size in {"small", "medium"}:
            score += 8
        if pattern == "microservices" and size in {"large", "enterprise"}:
            score += 9
        if pattern == "microservices" and team_size >= 6:
            score += 4
        if pattern == "mvc" and ui_focus:
            score += 7
        if pattern == "event_driven" and real_time:
            score += 9
        return score

    def explain_architecture(self, pattern, project_info):
        info = project_info or {}
        if pattern == "monolith":
            return "Projektgröße spricht für schnellen Start mit einfacher Betriebsführung."
        if pattern == "microservices":
            return "Skalierung und Teamgröße profitieren von serviceorientierter Trennung."
        if pattern == "mvc":
            return "UI-Fokus passt gut zu klarer Trennung von Model, View und Controller."
        if pattern == "event_driven":
            return "Asynchrone/Realtime-Abläufe profitieren von Event-getriebenem Design."
        return f"Standardwahl für gegebene Projektdaten: {info}"
