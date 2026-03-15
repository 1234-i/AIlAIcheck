import pytest

from app.llm.errors import LLMParseError
from app.llm.json_utils import parse_json_object_strict


def test_parse_json_object_strict_accepts_object() -> None:
    parsed = parse_json_object_strict('{"doc_type":"entry_permit"}')
    assert parsed["doc_type"] == "entry_permit"


def test_parse_json_object_strict_rejects_non_object() -> None:
    with pytest.raises(LLMParseError):
        parse_json_object_strict('["entry_permit"]')
