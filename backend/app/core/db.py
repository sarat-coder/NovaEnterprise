from __future__ import annotations

import functools
from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.health import register_check


@functools.lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    url = settings.database_url
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        # WAL mode: better concurrent read performance for SQLite
        @event.listens_for(engine, "connect")
        def _set_wal(dbapi_conn, _):  # noqa: ANN001
            dbapi_conn.execute("PRAGMA journal_mode=WAL")

    return engine


def get_session_factory() -> sessionmaker:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables and register the database readiness check."""
    from pathlib import Path  # noqa: PLC0415

    # Import models so metadata is populated
    import app.models.entities  # noqa: F401, PLC0415
    import app.models.research  # noqa: F401, PLC0415
    from app.models.base import Base  # noqa: PLC0415

    settings = get_settings()
    url = settings.database_url
    if url.startswith("sqlite:///"):
        # Ensure the directory exists for file-based SQLite
        db_path = url.replace("sqlite:///", "")
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    engine = get_engine()
    Base.metadata.create_all(engine)

    def _db_check() -> dict:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            dialect = engine.dialect.name
            detail = "sqlite" if dialect == "sqlite" else dialect
            return {"status": "ok", "detail": detail}
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "detail": str(exc)}

    register_check("database", _db_check)


def reset_engine_cache() -> None:
    """Clear the engine lru_cache. Use in tests only."""
    get_engine.cache_clear()
