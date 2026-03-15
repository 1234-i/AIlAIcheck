from __future__ import annotations

import hashlib


def checksum_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
