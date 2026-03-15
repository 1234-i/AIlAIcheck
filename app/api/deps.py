from collections.abc import Generator

from sqlmodel import Session

from app.db.session import get_session
from app.llm.adapters.base import LLMProvider
from app.llm.provider_factory import get_llm_provider
from app.storage.base import StorageBackend
from app.storage.factory import get_storage_backend


def get_db_session() -> Generator[Session, None, None]:
    yield from get_session()


def get_storage() -> StorageBackend:
    return get_storage_backend()


def get_provider() -> LLMProvider:
    return get_llm_provider()
