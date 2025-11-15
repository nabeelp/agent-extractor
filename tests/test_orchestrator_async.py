"""Async integration tests for the extraction orchestrator."""

from __future__ import annotations

import pytest

from src.config.settings import load_settings
from src.agents.orchestrator import ExtractionOrchestrator
from src.agents.extractor_agent import ExtractionResult
from src.agents.validator_agent import ValidatorAgentOutput


class _FakeExtractorAgent:
    def __init__(self, result: ExtractionResult):
        self._result = result
        self.calls = []

    async def extract_from_document(self, **kwargs):  # noqa: ANN003 (test helper)
        self.calls.append(kwargs)
        return self._result

    async def aclose(self) -> None:  # pragma: no cover - not used in test
        return None


class _FakeValidatorAgent:
    def __init__(self, output: ValidatorAgentOutput):
        self._output = output
        self.calls = []

    async def validate(self, validator_input):
        self.calls.append(validator_input)
        return self._output

    async def aclose(self) -> None:  # pragma: no cover - not used in test
        return None


@pytest.fixture(scope="module")
def settings():
    return load_settings()


@pytest.mark.asyncio
async def test_orchestrator_success(monkeypatch, settings):
    extractor_result = ExtractionResult(
        success=True,
        data={"invoiceNumber": "INV-1"},
        error=None,
        metadata={"extraction_method": "llm_text"},
        document_content="Invoice INV-1",
    )
    validator_output = ValidatorAgentOutput(
        success=True,
        validated_data={"invoiceNumber": "INV-1"},
        confidence_scores={"invoiceNumber": 0.95},
        overall_confidence=0.95,
        errors=[],
        metadata={"validation": True},
    )

    fake_extractor = _FakeExtractorAgent(extractor_result)
    fake_validator = _FakeValidatorAgent(validator_output)

    monkeypatch.setattr(
        "src.agents.orchestrator.create_extractor_agent",
        lambda _settings: fake_extractor,
    )
    monkeypatch.setattr(
        "src.agents.orchestrator.create_validator_agent",
        lambda _settings: fake_validator,
    )

    orchestrator = ExtractionOrchestrator(settings)

    result = await orchestrator.orchestrate(
        document_base64="ZHVtbXk=",
        file_type="pdf",
        data_elements=[{"name": "invoiceNumber", "description": "Invoice #", "required": True}],
    )

    assert result.success is True
    assert result.extracted_data == {"invoiceNumber": "INV-1"}
    assert result.confidence_scores == {"invoiceNumber": 0.95}
    assert result.metadata["validation"]["overall_confidence"] == 0.95


@pytest.mark.asyncio
async def test_orchestrator_validation_failure(monkeypatch, settings):
    extractor_result = ExtractionResult(
        success=True,
        data={"invoiceNumber": "INV-2"},
        error=None,
        metadata={},
        document_content="Invoice INV-2",
    )
    validator_output = ValidatorAgentOutput(
        success=False,
        validated_data={"invoiceNumber": "INV-2"},
        confidence_scores={"invoiceNumber": 0.4},
        overall_confidence=0.4,
        errors=["below threshold"],
        metadata={},
    )

    fake_extractor = _FakeExtractorAgent(extractor_result)
    fake_validator = _FakeValidatorAgent(validator_output)

    monkeypatch.setattr(
        "src.agents.orchestrator.create_extractor_agent",
        lambda _settings: fake_extractor,
    )
    monkeypatch.setattr(
        "src.agents.orchestrator.create_validator_agent",
        lambda _settings: fake_validator,
    )

    orchestrator = ExtractionOrchestrator(settings)

    result = await orchestrator.orchestrate(
        document_base64="ZHVtbXk=",
        file_type="pdf",
        data_elements=[{"name": "invoiceNumber", "description": "Invoice #", "required": True}],
    )

    assert result.success is False
    assert result.errors == ["below threshold"]
    assert result.overall_confidence == 0.4