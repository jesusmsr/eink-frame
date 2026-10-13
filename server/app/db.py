from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    """UTC 'naive' (SQLite no guarda zona horaria). Se serializa con sufijo Z."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


_engine: Engine | None = None
SessionLocal = sessionmaker(autoflush=False, expire_on_commit=False)


def init_engine(db_path: Path) -> Engine:
    global _engine
    _engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(_engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):  # pragma: no cover - trivial
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

    SessionLocal.configure(bind=_engine)
    return _engine


def get_engine() -> Engine:
    assert _engine is not None, "init_engine() no se ha llamado"
    return _engine


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
