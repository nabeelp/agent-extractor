"""Unit tests for the shared structured response parser."""

import pytest

from src.extraction.structured_parser import StructuredResponseParser
from src.exceptions import InvalidExtractionResultError


def test_parser_extracts_json_object_with_padding():
    parser = StructuredResponseParser("test payload")
    response = "LLM output:\n```json\n{\"foo\": \"bar\"}\n```"

    assert parser.parse(response) == {"foo": "bar"}


def test_parser_supports_yaml_like_single_quotes():
    parser = StructuredResponseParser("test payload")
    response = "Answer: {'foo': 'bar', 'count': 2}"

    assert parser.parse(response) == {"foo": "bar", "count": 2}


def test_parser_handles_double_wrapped_braces():
    parser = StructuredResponseParser("test payload")
    response = "Here you go: {{\"foo\": 1, \"bar\": 2}}"

    assert parser.parse(response) == {"foo": 1, "bar": 2}


def test_parser_requires_json_object():
    parser = StructuredResponseParser("test payload")

    with pytest.raises(InvalidExtractionResultError):
        parser.parse("No structured data here")


def test_parser_rejects_non_object_values():
    parser = StructuredResponseParser("test payload")

    with pytest.raises(InvalidExtractionResultError):
        parser.parse("Here is data: [1, 2, 3]")
