"""Engine creation and a tiny, idempotent SQL migration runner."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .models import Base

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
# Arbitrary constant; serialises migrations when several replicas start at once.
_MIGRATION_LOCK_ID = 74_726_917


def build_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


def wait_for_database(engine: Engine, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    delay = 1.0
    while True:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError:
            if time.monotonic() >= deadline:
                raise
            log.warning("database not reachable yet; retrying in %.0fs", delay)
            time.sleep(delay)
            delay = min(delay * 2, 5.0)


def run_migrations(engine: Engine) -> list[str]:
    """Apply pending ``migrations/*.sql`` files in order. Returns applied versions."""
    if engine.dialect.name != "postgresql":
        # Test/dev databases (SQLite) get the schema from the ORM metadata.
        Base.metadata.create_all(engine)
        return []

    applied_now: list[str] = []
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": _MIGRATION_LOCK_ID})
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                " version TEXT PRIMARY KEY,"
                " applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
        )
        done = set(conn.execute(text("SELECT version FROM schema_migrations")).scalars())
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.stem in done:
                continue
            conn.exec_driver_sql(path.read_text(encoding="utf-8"))
            conn.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:v)"), {"v": path.stem}
            )
            applied_now.append(path.stem)
    if applied_now:
        log.info("applied migrations: %s", ", ".join(applied_now))
    return applied_now


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
    finally:
        session.close()
