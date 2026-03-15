from __future__ import annotations

from pathlib import Path


class LocalStorage:
    def __init__(self, base_path: str) -> None:
        self.base = Path(base_path)
        self.base.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, key: str, data: bytes, content_type: str = "application/pdf") -> str:
        target = self.base / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(target)

    def read_bytes(self, key: str) -> bytes:
        target = self.base / key
        return target.read_bytes()

    def exists(self, key: str) -> bool:
        return (self.base / key).exists()
