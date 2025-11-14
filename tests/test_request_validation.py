"""Tests for upfront request validation helpers in the extractor agent."""

import pytest

from src.agents.extractor_agent import ExtractorAgent
from src.exceptions import Base64DecodingError, UnsupportedFileTypeError


def test_normalize_file_type_accepts_mixed_case():
    assert ExtractorAgent.normalize_file_type(" PDF\n") == "pdf"


def test_normalize_file_type_rejects_unknown_type():
    with pytest.raises(UnsupportedFileTypeError):
        ExtractorAgent.normalize_file_type("txt")


def test_decode_document_payload_rejects_invalid_base64():
    with pytest.raises(Base64DecodingError):
        ExtractorAgent.decode_document_payload("!!not-base64!!")


def test_decode_document_payload_rejects_empty_string():
    with pytest.raises(Base64DecodingError):
        ExtractorAgent.decode_document_payload("")
