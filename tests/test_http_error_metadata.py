"""Tests for HTTP error metadata propagation."""

from fastapi import HTTPException

from src.exceptions import UnsupportedFileTypeError, DocumentExtractionError
from src.interfaces.mcp_server import map_exception_to_http_error


def test_map_exception_includes_exception_metadata():
    exc = UnsupportedFileTypeError("txt", ["pdf", "docx"])

    http_exc = map_exception_to_http_error(exc)

    assert isinstance(http_exc, HTTPException)
    detail = http_exc.detail
    assert detail["error"] == "unsupported_file_type"
    assert detail["metadata"]["supported_types"] == ["pdf", "docx"]


def test_map_exception_prefers_explicit_metadata():
    class CustomExtractionError(DocumentExtractionError):
        pass

    exc = CustomExtractionError("failed", details={"foo": "bar"})
    http_exc = map_exception_to_http_error(exc, metadata={"routing": "vision"})

    assert http_exc.detail["metadata"] == {"routing": "vision"}
