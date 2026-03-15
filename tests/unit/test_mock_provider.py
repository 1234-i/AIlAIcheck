import pytest

from app.llm.adapters.mock_provider import MockProvider


@pytest.mark.asyncio
async def test_mock_provider_classify_pdf() -> None:
    provider = MockProvider()
    result = await provider.classify_pdf("construction_contract.pdf", b"%PDF-1.4")

    assert result.doc_type in {
        "construction_contract",
        "personnel_qualification_review_form",
        "entry_permit",
        "jsa",
    }
    assert result.primary_group
    assert 0 <= result.confidence <= 1


@pytest.mark.asyncio
async def test_mock_provider_extract_structured() -> None:
    provider = MockProvider()
    result = await provider.extract_structured(
        file_name="sample.pdf",
        pdf_bytes=b"%PDF-1.4",
        schema_name="construction_contract",
        schema_definition={"required_fields": []},
    )

    assert result.schema_name == "construction_contract"
    assert "project_name" in result.data
