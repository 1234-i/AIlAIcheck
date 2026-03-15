from app.core.config import get_settings
from app.core.enums import LLMMode
from app.llm.adapters.base import LLMProvider
from app.llm.adapters.gemini_provider import GeminiProvider
from app.llm.adapters.mock_provider import MockProvider


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    mode = settings.llm_mode

    if mode == LLMMode.MOCK.value:
        return MockProvider()
    if mode == LLMMode.GEMINI.value:
        return GeminiProvider()

    # auto mode
    if settings.relay_gemini_api_key or settings.gemini_api_key or settings.official_gemini_api_key:
        return GeminiProvider()
    return MockProvider()
