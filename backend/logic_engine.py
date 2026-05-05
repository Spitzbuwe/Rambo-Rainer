from __future__ import annotations


class ProblemAnalyzer:
    def analyze_problem(self, user_request):
        request = str(user_request or "")
        return {
            "stated_problem": request,
            "actual_problem": self.infer_actual_problem(request),
            "user_goals": self.extract_goals(request),
            "constraints": self.find_constraints(request),
            "solution_approaches": self.brainstorm_solutions(request),
            "recommended_approach": self.rank_solutions(request),
        }

    def infer_actual_problem(self, request):
        text = str(request or "").lower()
        keywords = {
            "slow": "Performance-Problem",
            "performance": "Performance-Problem",
            "error": "Fehlerbehandlung nötig",
            "fehler": "Fehlerbehandlung nötig",
            "windows": "Platform-spezifisches Problem",
            "data": "Datenmanagement-Problem",
            "daten": "Datenmanagement-Problem",
        }
        for keyword, problem in keywords.items():
            if keyword in text:
                return problem
        return "General Feature Request"

    def extract_goals(self, request):
        text = str(request or "").lower()
        goal_keywords = {
            "fast": "Performance",
            "schnell": "Performance",
            "easy": "Usability",
            "einfach": "Usability",
            "cheap": "Cost",
            "guenstig": "Cost",
            "secure": "Security",
            "sicher": "Security",
            "scalable": "Scalability",
            "skalier": "Scalability",
        }
        goals = [goal for key, goal in goal_keywords.items() if key in text]
        return goals or ["General Functionality"]

    def find_constraints(self, request):
        text = str(request or "").lower()
        constraints = {
            "budget": "low" if "budget" in text else None,
            "timeframe": "short" if ("schnell" in text or "asap" in text) else None,
            "platforms": [],
            "dependencies": [],
            "skills": [],
        }
        if "windows" in text:
            constraints["platforms"].append("Windows")
        if "linux" in text:
            constraints["platforms"].append("Linux")
        if "python" in text:
            constraints["dependencies"].append("Python")
        if "javascript" in text or "js" in text:
            constraints["dependencies"].append("JavaScript")
        return constraints

    def brainstorm_solutions(self, request):
        problem_type = self.infer_actual_problem(request)
        if "Performance" in problem_type:
            return [
                "Algorithmus-Optimierung",
                "Caching-System",
                "Parallelisierung",
                "Datenbank-Indexing",
            ]
        if "Datenmanagement" in problem_type:
            return [
                "Schema-Optimierung",
                "ETL-Pipeline",
                "Batch-Verarbeitung",
                "Data Validation Layer",
            ]
        return [
            "Minimum Viable Product (MVP)",
            "Phased Rollout",
            "Modulare Architektur",
            "Service-orientierter Ansatz",
        ]

    def rank_solutions(self, request):
        approaches = self.brainstorm_solutions(request)
        goals = self.extract_goals(request)
        if not approaches:
            return {"recommended": "MVP", "reason": "Kein Ansatz erkannt", "alternatives": []}

        scored = {}
        for approach in approaches:
            score = 1
            if "Performance" in goals and ("Optimierung" in approach or "Caching" in approach):
                score += 3
            if "Scalability" in goals and ("Service" in approach or "Modulare" in approach):
                score += 2
            if "Usability" in goals and "MVP" in approach:
                score += 1
            scored[approach] = score

        best = max(scored, key=scored.get)
        return {
            "recommended": best,
            "reason": f"Passt am besten zu den Zielen: {goals}",
            "alternatives": [item for item in approaches if item != best],
        }
