# -*- coding: utf-8 -*-
"""Bereinigung bekannter Mojibake-Bytefolgen in frontend/src/App.jsx."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "frontend" / "src" / "App.jsx"

# Längere zuerst, falls Überschneidungen
RAW_REPLACEMENTS: list[tuple[bytes, bytes]] = [
    (b"\xc3\xa2\xc5\x93\xe2\x80\x94", "\u2717".encode()),
    (b"\xc3\xa2\xc5\x93\xe2\x80\x9c", "\u2713".encode()),
    (b"\xc3\xa2\xe2\x82\xac\xe2\x80\x9d", "\u2014".encode()),
    (b"\xc3\xa2\xe2\x82\xac\xc2\xa6", "\u2026".encode()),
    (b"\xc3\xa2\xe2\x80\xa0\xe2\x80\x99", "\u2192".encode()),
    (b"\xc3\x82\xc2\xb7", "\u00b7".encode()),
    (b"\xc3\x83\xc2\xbc", "\u00fc".encode()),
    (b"\xc3\x83\xc2\xb6", "\u00f6".encode()),
    (b"\xc3\x83\xc2\xa4", "\u00e4".encode()),
    (b"\xc3\xa2\xc5\xa1\xc2\xa0\xc3\xaf\xc2\xb8\xc2\x8f", "\u26a0\ufe0f".encode()),
    (b"\xc3\xa2\xc2\x9d\xc2\x8c", "\u274c".encode()),
    (b"\xc3\xa2\xc2\x8f\xc2\xb1\xc3\xaf\xc2\xb8\xc2\x8f", "\u23f1\ufe0f".encode()),
    (b"\xc3\xa2\xc2\x9c\xc2\xa8", "\u2728".encode()),
    (b"\xc3\xb0\xc5\xb8\xe2\x80\x9c\xc2\xa5", "\U0001f4e5".encode()),
    (b"\xc3\xb0\xc5\xb8\xe2\x80\x9c\xc2\x81", "\U0001f4c1".encode()),
]


def main() -> None:
    data = APP.read_bytes()
    for bad, good in RAW_REPLACEMENTS:
        data = data.replace(bad, good)
    APP.write_bytes(data)


if __name__ == "__main__":
    main()
