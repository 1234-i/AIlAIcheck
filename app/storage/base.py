from __future__ import annotations

from typing import Protocol


class StorageBackend(Protocol):
    def save_bytes(self, key: str, data: bytes, content_type: str = "application/pdf") -> str:
        ...

    def read_bytes(self, key: str) -> bytes:
        ...

    def exists(self, key: str) -> bool:
        ...
