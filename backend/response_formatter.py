from __future__ import annotations


def format_response_like_claude(analysis):
    """
    Formatiere wie Claude - friendly und energisch.
    """
    if isinstance(analysis, dict):
        problem = analysis.get("analysis", {}) or {}
        tech = analysis.get("recommended_approach", "") or ""
        arch = analysis.get("architecture", "") or ""
        improvements = analysis.get("improvements", []) or []
        if isinstance(improvements, dict):
            improvements = improvements.get("priority", []) or []

        if isinstance(problem, dict):
            p_type = problem.get("actual_problem") or problem.get("problem_type") or "Problem erkannt"
            scope = ", ".join(problem.get("user_goals") or []) or problem.get("scope") or "Umfang definiert"
        else:
            p_type = "Problem erkannt"
            scope = "Umfang definiert"

        response = (
            "🎯 OKAY, ICH HAB DAS VERSTANDEN!\n\n"
            "PROBLEMANALYSE:\n"
            f"  - {p_type}\n"
            f"  - {scope}\n\n"
            "🏆 MEINE EMPFEHLUNG:\n"
            f"  Technologie: {tech}\n"
            "  Warum: Best performance, native integration\n\n"
            f"🏗️ ARCHITEKTUR: {arch}\n"
            "  Warum: Responsive, skalierbar, wartbar\n\n"
            "✅ TRADE-OFFS:\n"
            "  Pro: Performance, Integration, Modern\n"
            "  Con: Komplexitaet, Learning Curve\n\n"
            "💡 VERBESSERUNGSVORSCHLAEGE:"
        )
        if improvements:
            for i, imp in enumerate(improvements[:5], 1):
                if isinstance(imp, dict):
                    response += f"\n  {i}. {imp.get('suggestion') or imp.get('issue') or 'Improvement'}"
                else:
                    response += f"\n  {i}. {imp}"
        response += "\n\n✓ FERTIG! 🚀"
        return response
    return str(analysis or "")


class ResponseFormatter:
    """Formatiert technische Ergebnisse in einen klaren, freundlichen Stil."""

    def detect_style(self, prompt_text, preferred_style=None):
        if preferred_style in {"business", "developer", "friendly"}:
            return preferred_style
        text = str(prompt_text or "").lower()
        if any(k in text for k in ("vorstand", "management", "kunde", "business")):
            return "business"
        if any(k in text for k in ("api", "backend", "code", "architektur", "debug")):
            return "developer"
        return "friendly"

    def format_response(self, raw_analysis, style="friendly"):
        data = raw_analysis or {}
        analysis = data.get("analysis") or {}
        recommended = data.get("recommended_approach_detail") or data.get("recommended_approach") or {}
        arch = data.get("architecture_detail") or data.get("architecture") or {}
        improvements_raw = data.get("improvements") or []
        if isinstance(improvements_raw, dict):
            improvements = improvements_raw.get("priority") or []
        elif isinstance(improvements_raw, list):
            improvements = improvements_raw
        else:
            improvements = []
        perf = (data.get("performance_optimizations") or {}).get("optimizations") or []

        if isinstance(recommended, dict):
            lang = str((recommended.get("language") or "Unklar")).strip()
            framework = str((recommended.get("framework") or "Unklar")).strip()
        else:
            parts = str(recommended).split()
            lang = str(parts[0] if parts else "Unklar").strip()
            framework = str(" ".join(parts[1:]) if len(parts) > 1 else "Unklar").strip()
        arch_name = str((arch.get("recommended") if isinstance(arch, dict) else arch) or "Unklar").strip()
        actual_problem = str(analysis.get("actual_problem") or "Allgemeine Anfrage").strip()
        goals = analysis.get("user_goals") or []

        if style == "business":
            lines = [
                "✅ Analyse abgeschlossen. Hier ist die priorisierte Empfehlung.",
                "",
                f"🎯 **Empfehlung:** `{lang}` + `{framework}`",
                f"🏗️ **Architektur:** `{arch_name}`",
                f"⚠️ **Hauptproblem:** {actual_problem}",
                f"📌 **Ziele:** {', '.join(goals) if goals else 'General Functionality'}",
                "",
                "```text",
                "Kurzbegründung",
                f"- Technologie-Fit: {lang}",
                f"- Framework-Fit: {framework}",
                f"- Architektur-Fit: {arch_name}",
                "```",
            ]
        elif style == "developer":
            lines = [
                "🚀 Tech-Plan steht. Hier ist der Stack mit Begründung.",
                "",
                f"✅ **Stack:** `{lang}` + `{framework}`",
                f"🧩 **Architektur-Pattern:** `{arch_name}`",
                f"⚠️ **Problemklasse:** {actual_problem}",
                "",
                "```text",
                "Engineer Notes",
                f"- Language fit: {lang}",
                f"- Framework fit: {framework}",
                f"- Architecture fit: {arch_name}",
                "```",
            ]
        else:
            lines = [
                "🎯 Stark! Ich habe dein Problem analysiert und eine klare Empfehlung gebaut.",
                "",
                f"✅ **BESTE WAHL:** `{lang}` + `{framework}`",
                f"🚀 **Architektur:** `{arch_name}`",
                f"⚠️ **Kernproblem:** {actual_problem}",
                f"🎯 **Ziele:** {', '.join(goals) if goals else 'General Functionality'}",
                "",
                "```text",
                "Warum diese Wahl?",
                f"- Tech-Fit: {lang} passt zu den Anforderungen.",
                f"- Framework-Fit: {framework} bringt schnellen Start und klare Struktur.",
                f"- Architektur-Fit: {arch_name} balanciert Tempo und Wartbarkeit.",
                "```",
            ]

        if improvements:
            lines.extend([
                "",
                "🛠️ **Top Verbesserungen:**",
            ])
            for item in improvements[:3]:
                lines.append(f"- {item.get('severity', 'Medium')}: {item.get('issue', 'Verbesserung erkannt')}")

        if perf:
            lines.extend([
                "",
                "⚡ **Performance-Boost Ideen:**",
            ])
            for item in perf[:3]:
                lines.append(f"- {item.get('type', 'Optimierung')}: {item.get('suggestion', 'Optimierung prüfen')}")

        if style == "business":
            lines.extend(["", "➡️ Bei Freigabe setze ich die Umsetzung im nächsten Schritt direkt auf."])
        elif style == "developer":
            lines.extend(["", "➡️ Gib kurz den Go, dann erstelle ich sofort den Implementierungs-PR-Plan."])
        else:
            lines.extend([
                "",
                "💬 Wenn du willst, setze ich als Nächstes direkt die Umsetzung um.",
                "→ **GIB MIR BESCHEID!** 😎",
            ])

        return "\n".join(lines)
