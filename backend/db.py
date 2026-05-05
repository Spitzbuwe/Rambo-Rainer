# -*- coding: utf-8 -*-
"""SQLAlchemy Engine/Session (Phase 17)."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models import Base


def make_engine(db_url: Optional[str] = None):
    if db_url:
        return create_engine(db_url, future=True)
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(backend_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "rambo_rainer.db")
    return create_engine(f"sqlite:///{path.replace(os.sep, '/')}", future=True)


SessionLocal: Optional[sessionmaker] = None
_engine = None


def init_engine(db_url: Optional[str] = None):
    global _engine, SessionLocal
    _engine = make_engine(db_url)
    SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, class_=Session)
    return _engine


def get_engine():
    global _engine
    if _engine is None:
        init_engine()
    return _engine


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    if SessionLocal is None:
        init_engine()
    assert SessionLocal is not None
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def create_all(engine=None):
    eng = engine or get_engine()
    Base.metadata.create_all(eng)
