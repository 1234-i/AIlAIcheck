from uuid import UUID

from fastapi import HTTPException


def parse_uuid(value: str, field_name: str) -> UUID:
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid {field_name}: {value}") from exc
