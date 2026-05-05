# -*- coding: utf-8 -*-
"""Erstellt DB-Tabellen (Phase 17)."""

from __future__ import annotations

from db import create_all, init_engine
from models import Base


def run_migrate(db_url: str | None = None):
    init_engine(db_url)
    create_all()
    return {
        "status": "migrated",
        "tables": sorted(Base.metadata.tables.keys()),
    }


if __name__ == "__main__":
    print(run_migrate())
