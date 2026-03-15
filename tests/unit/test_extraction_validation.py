from app.extractors.schema_registry import get_schema_for_doc_type
from app.services.extraction_service import _validate_against_json_schema


def test_validate_against_json_schema_success_for_contract() -> None:
    schema = get_schema_for_doc_type("construction_contract")
    assert schema is not None
    payload = {
        "project_name": "Alpha LNG Upgrade",
        "contractor_name": "ACME EPC Co.",
        "contract_no": "HT-2026-001",
        "effective_date": "2026-01-01",
    }
    errors = _validate_against_json_schema(payload, schema["json_schema"])
    assert errors == []


def test_validate_against_json_schema_rejects_unknown_fields() -> None:
    schema = get_schema_for_doc_type("entry_permit")
    assert schema is not None
    payload = {
        "project_name": "Alpha LNG Upgrade",
        "person_name": "Zhang San",
        "id_no": "A-10001",
        "role": "scaffolder",
        "permit_no": "EP-1",
        "permit_date": "2026-02-10",
        "unknown_field": "should fail",
    }
    errors = _validate_against_json_schema(payload, schema["json_schema"])
    assert "unexpected field by schema: unknown_field" in errors


def test_validate_against_json_schema_rejects_array_type_mismatch() -> None:
    schema = get_schema_for_doc_type("jsa")
    assert schema is not None
    payload = {
        "project_name": "Alpha LNG Upgrade",
        "activity": "Hot Work",
        "hazards": "fire",  # should be array
        "controls": ["fire watch"],
        "prepared_by": "Safety Engineer Lin",
    }
    errors = _validate_against_json_schema(payload, schema["json_schema"])
    assert "field 'hazards' expected array, got str" in errors
