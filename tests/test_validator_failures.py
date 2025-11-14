"""Validator behavior for empty inputs and missing confidence scores."""

from types import SimpleNamespace

import pytest

from src.config.settings import load_settings
from src.extraction.validator import Validator


@pytest.fixture(scope="module")
def settings():
    return load_settings("config.json")


@pytest.mark.asyncio
async def test_validator_short_circuits_when_no_elements(settings, monkeypatch):
    validator = Validator(settings)

    async def fail_if_called(*_args, **_kwargs):  # pragma: no cover - defensive
        raise AssertionError("Validation model should not be called when no elements are provided")

    monkeypatch.setattr(validator.client, "get_response", fail_if_called)

    result = await validator.validate(
        document_content="Sample document",
        data_elements=[],
        extracted_data={},
    )

    assert result.success is False
    assert result.errors == ["Validation requires at least one data element"]


@pytest.mark.asyncio
async def test_validator_flags_missing_confidence_scores(settings, monkeypatch):
    validator = Validator(settings)

    async def fake_response(*_args, **_kwargs):
        return SimpleNamespace(text="{}")

    monkeypatch.setattr(validator.client, "get_response", fake_response)
    monkeypatch.setattr(validator.result_parser, "parse", lambda _text, _data: {})

    result = await validator.validate(
        document_content="Invoice 123",
        data_elements=[{"name": "invoiceNumber", "description": "Invoice #", "required": True}],
        extracted_data={"invoiceNumber": "123"},
    )

    assert result.success is False
    assert any("no confidence scores" in error.lower() for error in result.errors)
