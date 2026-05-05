from response_builder import (
    error_payload,
    file_write_payload,
    no_change_payload,
    preview_payload,
    success_payload,
)


def test_success_payload_is_human_friendly():
    payload = success_payload(
        "Datei erstellt! ✓",
        technical_message="file created",
        changed_files=["config.json"],
        location="rambo_builder_local/",
        detail="Die Datei ist jetzt bereit.",
    )
    assert "Datei erstellt! ✓" in payload["message"]
    assert "📄 config.json" in payload["message"]
    assert "📍 rambo_builder_local/" in payload["message"]
    assert payload["technical_message"] == "file created"


def test_file_write_payload_created_and_updated():
    created = file_write_payload("file1.txt", created=True, location="rambo_builder_local/")
    updated = file_write_payload("file1.txt", created=False, location="rambo_builder_local/")
    assert "Datei erstellt! ✓" in created["message"]
    assert "Datei aktualisiert! ✓" in updated["message"]


def test_preview_and_no_change_payloads():
    preview = preview_payload(path="config.json", technical_message="preview")
    no_change = no_change_payload("config.json", technical_message="none")
    assert "Vorschau bereit! ✓" in preview["message"]
    assert "Keine inhaltliche Änderung nötig." in no_change["message"]


def test_error_payload_keeps_technical_error_and_natural_message():
    payload = error_payload("Pfad ist nicht erlaubt.", technical_error="guard_blocked")
    assert payload["error"] == "guard_blocked"
    assert "Pfad ist nicht erlaubt." in payload["message"]
