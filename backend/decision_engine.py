from __future__ import annotations


class DecisionMaker:
    def make_technology_choice(self, requirements):
        req = requirements or {}
        language = self.choose_language(req)
        framework = self.choose_framework(req)
        return {
            "language": language,
            "framework": framework,
            "recommended": {
                "language": language.get("recommended"),
                "framework": framework.get("recommended"),
            },
            "explanation": self.explain_choice(
                language.get("recommended"),
                req,
                framework.get("recommended"),
            ),
        }

    def choose_language(self, requirements):
        req = requirements or {}
        scores = {"Python": 0, "C#": 0, "JavaScript": 0, "Go": 0, "Rust": 0}

        if req.get("high_performance"):
            scores["C#"] += 8
            scores["Rust"] += 10
            scores["Go"] += 8
        if req.get("fast_development"):
            scores["Python"] += 10
            scores["JavaScript"] += 8
        if req.get("windows_only"):
            scores["C#"] += 10
        if req.get("web_ui"):
            scores["JavaScript"] += 7

        best = max(scores, key=scores.get)
        return {
            "recommended": best,
            "score": scores[best],
            "reason": self.explain_choice(best, req),
            "scores": scores,
        }

    def choose_framework(self, requirements):
        req = requirements or {}
        language = req.get("preferred_language")
        if not language:
            language = self.choose_language(req).get("recommended")

        if language == "C#":
            fw = "WPF" if req.get("windows_only") else ".NET MAUI"
        elif language == "JavaScript":
            fw = "React"
        elif language == "Python":
            fw = "Flask"
        elif language == "Go":
            fw = "Gin"
        else:
            fw = "Actix"
        return {"recommended": fw, "language": language}

    def explain_choice(self, choice, requirements, framework=None):
        req = requirements or {}
        reasons = []
        if choice == "C#" and req.get("windows_only"):
            reasons.append("Windows-spezifisch -> C# ist nativer Fit")
        if choice == "Python" and req.get("fast_development"):
            reasons.append("Schnelle Entwicklung -> Python mit hoher Produktivität")
        if choice == "JavaScript" and req.get("web_ui"):
            reasons.append("UI-Anforderung -> JavaScript/React liefert schnellen Frontend-Stack")
        if framework:
            reasons.append(f"Framework-Entscheidung: {framework}")
        if not reasons:
            reasons.append("Abgewogene Standardentscheidung auf Basis der Anforderungen")
        return " | ".join(reasons)
