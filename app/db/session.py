from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings


@lru_cache(maxsize=8)
def _build_engine(database_url: str, echo: bool) -> Engine:
    return create_engine(database_url, echo=echo)


def get_runtime_engine() -> Engine:
    settings = get_settings()
    return _build_engine(settings.database_url, settings.app_debug)


def init_db() -> None:
    # Ensure model metadata is registered before table creation.
    import app.models.entities  # noqa: F401

    SQLModel.metadata.create_all(get_runtime_engine())


def get_session() -> Generator[Session, None, None]:
    with Session(get_runtime_engine()) as session:
        yield session
