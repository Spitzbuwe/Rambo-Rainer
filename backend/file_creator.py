"""Sicheres Anlegen von Dateien und Ordnern nur unter einem festen Wurzelverzeichnis."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path

_log = logging.getLogger(__name__)


class FileCreator:
    """Session-Root typisch: data/implementations/impl_<timestamp>_<id>/."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _assert_under_root(self, path: Path) -> None:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as ex:
            raise ValueError("Pfad liegt ausserhalb des erlaubten Wurzelverzeichnisses") from ex

    def safe_path_check(self, rel: str) -> bool:
        """True, wenn der relative Pfad innerhalb des Session-Roots bleiben wuerde."""
        try:
            self._safe_rel(rel)
            return True
        except ValueError:
            return False

    def _safe_rel(self, rel: str) -> Path:
        raw = str(rel or "").strip().replace("\\", "/").lstrip("/")
        parts = [p for p in raw.split("/") if p]
        if not parts or any(p == ".." for p in parts):
            raise ValueError("Ungueltiger relativer Pfad")
        dst = (self.root / raw).resolve()
        self._assert_under_root(dst)
        return dst

    def create_folder(self, rel: str) -> Path:
        """Legt einen Ordner relativ zum Session-Root an."""
        p = self._safe_rel(rel)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def create_file(self, rel: str, content: str, encoding: str = "utf-8") -> Path:
        """Schreibt eine Textdatei relativ zum Session-Root."""
        p = self._safe_rel(rel)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(str(content), encoding=encoding, newline="\n")
        except OSError as ex:
            _log.exception("create_file fehlgeschlagen: %s", p)
            raise OSError(f"Konnte Datei nicht schreiben: {p}") from ex
        return p

    @staticmethod
    def create_session_root(base: Path) -> Path:
        base = Path(base).resolve()
        base.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sid = uuid.uuid4().hex[:10]
        sess = (base / f"impl_{stamp}_{sid}").resolve()
        sess.mkdir(parents=True, exist_ok=True)
        return sess

    @staticmethod
    def create_sandbox(impl_base: Path) -> Path:
        """Legt impl_<Zeitstempel>_<id>/ unter impl_base an inkl. src/."""
        impl_base = Path(impl_base).resolve()
        impl_base.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sid = uuid.uuid4().hex[:8]
        root = (impl_base / f"impl_{stamp}_{sid}").resolve()
        root.mkdir(parents=True, exist_ok=True)
        (root / "src").mkdir(parents=True, exist_ok=True)
        _log.info("Sandbox erstellt: %s", root)
        return root

    @staticmethod
    def create_project_file(root: Path, rel: str, content: str) -> Path:
        """Schreibt eine Datei relativ zu root (Pfadpruefung wie bei create_file)."""
        root = Path(root).resolve()
        fc = FileCreator(root)
        rel_norm = str(rel or "").strip().replace("\\", "/").lstrip("/")
        if not rel_norm:
            raise ValueError("rel darf nicht leer sein")
        if not fc.safe_path_check(rel_norm):
            raise ValueError(f"unsafe path: {rel!r}")
        try:
            p = fc.create_file(rel_norm, str(content))
        except OSError:
            raise
        except Exception as ex:
            _log.exception("create_project_file: %s unter %s", rel_norm, root)
            raise RuntimeError(f"Datei konnte nicht angelegt werden: {rel_norm}") from ex
        _log.info("Datei erstellt: %s", p)
        return p
