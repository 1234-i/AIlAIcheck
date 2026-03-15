from __future__ import annotations


class LLMProviderError(RuntimeError):
    def __init__(self, message: str, code: str = "llm_error") -> None:
        super().__init__(message)
        self.code = code


class LLMTimeoutError(LLMProviderError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="llm_timeout")


class LLMTransportError(LLMProviderError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="llm_transport_error")


class LLMParseError(LLMProviderError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="llm_parse_error")


class LLMValidationError(LLMProviderError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="llm_validation_error")
