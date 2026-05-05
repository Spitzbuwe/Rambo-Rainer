from __future__ import annotations

from typing import Any

from message_templates import (
    natural_error,
    natural_file_created,
    natural_file_updated,
    natural_no_changes,
    natural_preview_ready,
    natural_success,
)


def success_payload(
    headline: str,
    *,
    technical_message: str | None = None,
    changed_files: list[str] | None = None,
    location: str | None = None,
    detail: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    msg = natural_success(headline, changed_files=changed_files, location=location, detail=detail)
    payload: dict[str, Any] = {
        "message": msg,
        "natural_message": msg,
        "technical_message": technical_message or headline,
        "changed_files": [p for p in (changed_files or []) if str(p).strip()],
        "output_location": location or "",
    }
    payload.update(extra)
    return payload


def preview_payload(
    *,
    path: str | None,
    technical_message: str,
    **extra: Any,
) -> dict[str, Any]:
    msg = natural_preview_ready(path)
    payload: dict[str, Any] = {
        "message": msg,
        "natural_message": msg,
        "technical_message": technical_message,
    }
    payload.update(extra)
    return payload


def file_write_payload(path: str, *, created: bool, location: str | None = None, technical_message: str | None = None, **extra: Any) -> dict[str, Any]:
    msg = natural_file_created(path, location=location) if created else natural_file_updated(path, location=location)
    payload: dict[str, Any] = {
        "message": msg,
        "natural_message": msg,
        "technical_message": technical_message or msg,
        "changed_files": [path],
        "output_location": location or "",
    }
    payload.update(extra)
    return payload


def no_change_payload(path: str | None = None, *, technical_message: str | None = None, **extra: Any) -> dict[str, Any]:
    msg = natural_no_changes(path)
    payload: dict[str, Any] = {
        "message": msg,
        "natural_message": msg,
        "technical_message": technical_message or msg,
        "changed_files": [path] if path else [],
    }
    payload.update(extra)
    return payload


def error_payload(reason: str, *, detail: str | None = None, technical_error: str | None = None, **extra: Any) -> dict[str, Any]:
    msg = natural_error(reason, detail=detail)
    payload: dict[str, Any] = {
        "error": technical_error or reason,
        "message": msg,
        "natural_message": msg,
    }
    payload.update(extra)
    return payload
