"""Tests for the document routing logic."""

import pytest

from src.exceptions import DocumentRoutingError
from src.extraction.router import DocumentRouter, DocumentType, ExtractionMethod


def _scanned_pdf_metadata() -> dict:
    return {
        "has_extractable_text": False,
        "is_likely_scanned": True,
        "text_density": 0,
    }


def test_scanned_pdf_routes_to_document_intelligence_when_available():
    router = DocumentRouter(use_document_intelligence=True)

    method, reasoning = router._select_extraction_method(  # noqa: SLF001 (intentional)
        DocumentType.PDF,
        _scanned_pdf_metadata(),
    )

    assert method == ExtractionMethod.DOCUMENT_INTELLIGENCE
    assert "Document Intelligence" in reasoning


def test_scanned_pdf_errors_when_document_intelligence_missing():
    router = DocumentRouter(use_document_intelligence=False)

    with pytest.raises(DocumentRoutingError):
        router._select_extraction_method(  # noqa: SLF001 (intentional)
            DocumentType.PDF,
            _scanned_pdf_metadata(),
        )


def test_image_documents_still_use_vision():
    router = DocumentRouter(use_document_intelligence=True)

    method, reasoning = router._select_extraction_method(  # noqa: SLF001 (intentional)
        DocumentType.PNG,
        {"is_image": True},
    )

    assert method == ExtractionMethod.LLM_VISION
    assert "vision" in reasoning.lower()
