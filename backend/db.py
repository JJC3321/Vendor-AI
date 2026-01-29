from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from config import get_settings


settings = get_settings()

# For SQLite, `check_same_thread=False` allows usage across threads in FastAPI.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def init_db() -> None:
    """Create database tables if they do not exist.

    This is intended to be called once at application startup.
    """
    import models  # Import models so SQLModel is aware of them.

    _ = models  # Avoid unused import warnings.
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a SQLModel session."""
    with Session(engine) as session:
        yield session

