"""Test that environment variables properly override config.json values."""

import os
from pathlib import Path

import pytest

from src.config.settings import Settings


def test_env_override_azure_document_intelligence_endpoint(tmp_path, monkeypatch):
    """Test that AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT env var overrides config.json."""
    # Create a temporary config.json with a default value
    config_file = tmp_path / "config.json"
    config_file.write_text(
        """{
        "azureDocumentIntelligence": {
            "endpoint": "https://default-endpoint.cognitiveservices.azure.com/"
        },
        "azureAIFoundry": {
            "projectEndpoint": "https://test.cognitiveservices.azure.com/",
            "extractionModel": "gpt-4o"
        }
    }"""
    )

    # Set environment variable with a different value
    env_endpoint = "https://env-override.cognitiveservices.azure.com/"
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", env_endpoint)

    # Configure settings to use the temp config file
    Settings.configure(config_file)
    settings = Settings()

    # Verify that the environment variable value is used, not the config.json value
    assert settings.azure_document_intelligence is not None
    assert settings.azure_document_intelligence.endpoint == env_endpoint.rstrip("/")


def test_env_override_azure_ai_foundry_endpoint(tmp_path, monkeypatch):
    """Test that AZURE_AI_FOUNDRY_ENDPOINT env var overrides config.json."""
    config_file = tmp_path / "config.json"
    config_file.write_text(
        """{
        "azureAIFoundry": {
            "projectEndpoint": "https://default-foundry.cognitiveservices.azure.com/",
            "extractionModel": "gpt-4o"
        }
    }"""
    )

    env_endpoint = "https://env-foundry.cognitiveservices.azure.com/"
    monkeypatch.setenv("AZURE_AI_FOUNDRY_ENDPOINT", env_endpoint)

    Settings.configure(config_file)
    settings = Settings()

    assert settings.azure_ai_foundry.project_endpoint == env_endpoint.rstrip("/")


def test_env_override_multiple_values(tmp_path, monkeypatch):
    """Test that multiple environment variables can override config.json values."""
    config_file = tmp_path / "config.json"
    config_file.write_text(
        """{
        "minConfidenceThreshold": 0.5,
        "maxBufferSizeMB": 5,
        "azureAIFoundry": {
            "projectEndpoint": "https://default.cognitiveservices.azure.com/",
            "extractionModel": "gpt-3.5-turbo",
            "validationModel": "gpt-3.5-turbo"
        },
        "serverPorts": {
            "mcp": 9000,
            "a2a": 9001
        }
    }"""
    )

    # Override multiple values via environment variables
    monkeypatch.setenv("MIN_CONFIDENCE_THRESHOLD", "0.9")
    monkeypatch.setenv("MAX_BUFFER_SIZE_MB", "20")
    monkeypatch.setenv("AZURE_EXTRACTION_MODEL", "gpt-4o")
    monkeypatch.setenv("AZURE_VALIDATION_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("MCP_SERVER_PORT", "8000")

    Settings.configure(config_file)
    settings = Settings()

    assert settings.min_confidence_threshold == 0.9
    assert settings.max_buffer_size_mb == 20
    assert settings.azure_ai_foundry.extraction_model == "gpt-4o"
    assert settings.azure_ai_foundry.validation_model == "gpt-4o-mini"
    assert settings.server_ports.mcp == 8000
    assert settings.server_ports.a2a == 9001  # Not overridden, should use config.json


def test_config_json_used_when_no_env_vars(tmp_path, monkeypatch):
    """Test that config.json values are used when environment variables are not set."""
    config_file = tmp_path / "config.json"
    config_file.write_text(
        """{
        "minConfidenceThreshold": 0.75,
        "azureDocumentIntelligence": {
            "endpoint": "https://config-endpoint.cognitiveservices.azure.com/"
        },
        "azureAIFoundry": {
            "projectEndpoint": "https://config-foundry.cognitiveservices.azure.com/",
            "extractionModel": "gpt-4o"
        }
    }"""
    )

    # Ensure no environment variables are set
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", raising=False)
    monkeypatch.delenv("MIN_CONFIDENCE_THRESHOLD", raising=False)

    Settings.configure(config_file)
    settings = Settings()

    # Config.json values should be used
    assert settings.min_confidence_threshold == 0.75
    assert settings.azure_document_intelligence.endpoint == "https://config-endpoint.cognitiveservices.azure.com"
