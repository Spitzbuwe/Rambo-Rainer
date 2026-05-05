"""
Dateiinhalt auslesen und formatieren
"""
from __future__ import annotations

from pathlib import Path


def read_file_content(file_path):
    """Lese Dateiinhalt aus"""
    try:
        path = Path(file_path)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    except Exception:
        return None


def get_latest_analysis_file(output_dir="data/auto"):
    """Finde neueste Analysedatei im data/auto/"""
    try:
        path = Path(output_dir)
        if not path.exists():
            return None
        md_files = list(path.glob("*.md"))
        if not md_files:
            return None
        latest = max(md_files, key=lambda p: p.stat().st_mtime)
        return latest
    except Exception:
        return None
