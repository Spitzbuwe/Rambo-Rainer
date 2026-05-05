from __future__ import annotations


def _line(text: str) -> str:
    return str(text or "").strip()


def natural_success(headline: str, *, changed_files: list[str] | None = None, location: str | None = None, detail: str | None = None) -> str:
    lines: list[str] = [_line(headline)]
    files = [str(p).strip() for p in (changed_files or []) if str(p).strip()]
    if files:
        lines.append("")
        for path in files[:4]:
            lines.append(f"📄 {path}")
    if location:
        lines.append(f"📍 {_line(location)}")
    if detail:
        lines.append("")
        lines.append(_line(detail))
    return "\n".join([ln for ln in lines if ln is not None]).strip()


def natural_preview_ready(path: str | None = None) -> str:
    target = _line(path or "Vorschau")
    return natural_success(
        "Vorschau bereit! ✓",
        changed_files=[target] if target else None,
        detail="Du kannst jetzt direkt prüfen und fortfahren."
    )


def natural_file_created(path: str, *, location: str | None = None) -> str:
    return natural_success(
        "Datei erstellt! ✓",
        changed_files=[path],
        location=location,
        detail="Die Datei ist jetzt bereit."
    )


def natural_file_updated(path: str, *, location: str | None = None) -> str:
    return natural_success(
        "Datei aktualisiert! ✓",
        changed_files=[path],
        location=location,
        detail="Die Änderung ist gespeichert."
    )


def natural_no_changes(path: str | None = None) -> str:
    target = _line(path or "Datei")
    return natural_success(
        "Keine inhaltliche Änderung nötig.",
        changed_files=[target] if target else None,
        detail="Es wurde nichts überschrieben."
    )


def natural_error(reason: str, *, detail: str | None = None) -> str:
    text = _line(reason) or "Ein Fehler ist aufgetreten."
    if detail:
        text = f"{text}\n\n{_line(detail)}"
    return text


class MessageTemplates:
    @staticmethod
    def analysis_result(analysis_content):
        """Analyseergebnis mit Dateiinhalt"""
        return (
            "Ich habe die Analyse durchgeführt.\n\n"
            "Hier sind die Ergebnisse:\n\n"
            "---\n\n"
            f"{str(analysis_content or '').strip()}\n\n"
            "---\n\n"
            "Die Analyse ist komplett. Alle Informationen oben. ✓"
        )

    @staticmethod
    def query_result(query_type, result_content):
        """Generisches Query-Ergebnis"""
        body = str(result_content or "").strip()
        if query_type == "structure":
            return (
                "Ich habe die Struktur analysiert.\n\n"
                "Hier ist was ich gefunden habe:\n\n"
                f"{body}\n\n"
                "Alles klar. ✓"
            )
        if query_type == "search":
            return (
                "Ich habe gesucht und gefunden:\n\n"
                f"{body}\n\n"
                "Fertig. ✓"
            )
        return body
