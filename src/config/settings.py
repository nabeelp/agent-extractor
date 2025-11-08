"""Configuration management for agent-extractor."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential


class Settings:
    """Application settings loaded from config.json and .env files."""

    def __init__(self, config_path: str = "config.json"):
        """Initialize settings from config file and environment variables.
        
        Args:
            config_path: Path to configuration JSON file
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If required configuration is missing
        """
        # Load environment variables from .env file
        load_dotenv()
        
        # Load configuration from JSON file
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_file, 'r') as f:
            self._config: Dict[str, Any] = json.load(f)
        
        # Initialize Azure credential for Entra ID authentication
        self._credential = DefaultAzureCredential()
        
        # Validate required configuration
        self._validate()
    
    def _validate(self) -> None:
        """Validate required configuration values are present.
        
        Raises:
            ValueError: If required configuration is missing
        """
        required_fields = [
            "azureAIFoundry.projectEndpoint",
            "azureAIFoundry.extractionModel",
            "serverPorts.mcp"
        ]
        
        for field in required_fields:
            if not self._get_nested(field):
                raise ValueError(f"Required configuration missing: {field}")
    
    def _get_nested(self, path: str) -> Optional[Any]:
        """Get nested configuration value using dot notation.
        
        Args:
            path: Dot-separated path to config value (e.g., 'azureAIFoundry.projectEndpoint')
            
        Returns:
            Configuration value or None if not found
        """
        keys = path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        
        return value
    
    # Azure AI Foundry configuration
    @property
    def azure_ai_foundry_endpoint(self) -> str:
        """Azure AI Foundry project endpoint URL."""
        return self._get_nested("azureAIFoundry.projectEndpoint")
    
    @property
    def azure_credential(self) -> DefaultAzureCredential:
        """Azure credential for Entra ID authentication."""
        return self._credential
    
    @property
    def azure_tenant_id(self) -> Optional[str]:
        """Azure tenant ID from environment variable (optional)."""
        return os.getenv("AZURE_TENANT_ID")
    
    @property
    def extraction_model(self) -> str:
        """Model deployment name for extraction (e.g., gpt-4o)."""
        return self._get_nested("azureAIFoundry.extractionModel")
    
    # Server configuration
    @property
    def mcp_server_port(self) -> int:
        """MCP server port number."""
        return int(self._get_nested("serverPorts.mcp") or 8000)
    
    # Extraction settings
    @property
    def min_confidence_threshold(self) -> float:
        """Minimum confidence score for required fields."""
        return float(self._get_nested("minConfidenceThreshold") or 0.8)
    
    @property
    def max_buffer_size_mb(self) -> int:
        """Maximum document buffer size in MB."""
        return int(self._get_nested("maxBufferSizeMB") or 10)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create global settings instance.
    
    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def load_settings(config_path: str = "config.json") -> Settings:
    """Load settings from specified configuration file.
    
    Args:
        config_path: Path to configuration JSON file
        
    Returns:
        Settings instance
    """
    global _settings
    _settings = Settings(config_path)
    return _settings
