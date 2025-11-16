"""Utilities for parsing structured model responses into JSON dictionaries."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import yaml

from ..exceptions import InvalidExtractionResultError


class StructuredResponseParser:
    """Parse LLM responses that *should* be JSON but may use YAML syntax."""

    def __init__(self, expected_root: str):
        self._expected_root = expected_root

    def parse(self, response_text: str) -> Dict[str, Any]:
        """Parse response text into a dictionary.

        Args:
            response_text: Raw response from the LLM

        Returns:
            Parsed dictionary

        Raises:
            InvalidExtractionResultError: When no valid JSON/YAML object exists
        """

        response_text = response_text.strip()
        json_candidate = self._extract_braced_segment(response_text)

        data = self._loads_json(json_candidate)
        if data is None:
            data = self._loads_yaml(json_candidate)

        if not isinstance(data, dict):
            raise InvalidExtractionResultError(
                f"Parsed {self._expected_root} is not an object; got {type(data).__name__}"
            )

        return data

    def _extract_braced_segment(self, response_text: str) -> str:
        start_idx = response_text.find("{")
        end_idx = response_text.rfind("}")

        if start_idx == -1 or end_idx == -1:
            raise InvalidExtractionResultError(
                f"No JSON object found in {self._expected_root} response"
            )

        segment = response_text[start_idx : end_idx + 1]
        return self._strip_redundant_wrappers(segment)

    def _strip_redundant_wrappers(self, text: str) -> str:
        text = text.strip()

        while text.startswith("{{") and text.endswith("}}"):
            inner = text[1:-1].strip()
            if not inner.startswith("{") or not inner.endswith("}"):
                break
            text = inner

        return text

    def _loads_json(self, json_text: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            return None

    def _loads_yaml(self, json_text: str) -> Dict[str, Any]:
        try:
            return yaml.safe_load(json_text)
        except yaml.YAMLError as exc:
            raise InvalidExtractionResultError(
                f"Failed to parse {self._expected_root} as JSON or YAML: {exc}"
            ) from exc
