"""Configuration management for agent-extractor.

Provides type-safe configuration using Pydantic models with validation,
environment variable overrides, and Azure credential management.
"""

import json
import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential

# Load environment variables from .env file
load_dotenv()


class AzureAIFoundryConfig(BaseModel):
    """Azure AI Foundry configuration."""
    
    project_endpoint: str = Field(
        ...,
        description="Azure AI Foundry project endpoint URL",
        json_schema_extra={"env": "AZURE_AI_FOUNDRY_ENDPOINT"}
    )
    extraction_model: str = Field(
        ...,
        description="Model deployment name for extraction (e.g., gpt-4o)",
        json_schema_extra={"env": "AZURE_EXTRACTION_MODEL"}
    )
    validation_model: Optional[str] = Field(
        default=None,
        description="Model deployment name for validation (e.g., gpt-4o-mini)",
        json_schema_extra={"env": "AZURE_VALIDATION_MODEL"}
    )
    use_managed_identity: bool = Field(
        default=False,
        description="Use managed identity for authentication (production)",
        json_schema_extra={"env": "AZURE_USE_MANAGED_IDENTITY"}
    )
    
    @field_validator('project_endpoint')
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        """Validate endpoint URL format."""
        if not v:
            raise ValueError("Azure AI Foundry project endpoint is required")
        if not v.startswith(('http://', 'https://')):
            raise ValueError(f"Invalid endpoint URL format: {v}")
        return v.rstrip('/')
    
    @field_validator('extraction_model')
    @classmethod
    def validate_extraction_model(cls, v: str) -> str:
        """Validate extraction model name."""
        if not v:
            raise ValueError("Extraction model name is required")
        return v


class AzureDocumentIntelligenceConfig(BaseModel):
    """Azure Document Intelligence configuration."""
    
    endpoint: Optional[str] = Field(
        default=None,
        description="Azure Document Intelligence endpoint URL",
        json_schema_extra={"env": "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"}
    )
    key: Optional[str] = Field(
        default=None,
        description="Azure Document Intelligence API key (use managed identity instead for production)",
        json_schema_extra={"env": "AZURE_DOCUMENT_INTELLIGENCE_KEY"}
    )
    use_managed_identity: bool = Field(
        default=False,
        description="Use managed identity for authentication",
        json_schema_extra={"env": "AZURE_DOCUMENT_INTELLIGENCE_USE_MANAGED_IDENTITY"}
    )
    
    @field_validator('endpoint')
    @classmethod
    def validate_endpoint(cls, v: Optional[str]) -> Optional[str]:
        """Validate endpoint URL format if provided."""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError(f"Invalid endpoint URL format: {v}")
        return v.rstrip('/') if v else None


class ServerPortsConfig(BaseModel):
    """Server port configuration."""
    
    mcp: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        description="MCP server port number",
        json_schema_extra={"env": "MCP_SERVER_PORT"}
    )
    a2a: int = Field(
        default=8001,
        ge=1024,
        le=65535,
        description="A2A agent server port number",
        json_schema_extra={"env": "A2A_SERVER_PORT"}
    )
    
    @model_validator(mode='after')
    def validate_unique_ports(self) -> 'ServerPortsConfig':
        """Ensure MCP and A2A ports are different."""
        if self.mcp == self.a2a:
            raise ValueError("MCP and A2A server ports must be different")
        return self


class PromptsConfig(BaseModel):
    """Prompt templates configuration."""
    
    extraction: str = Field(
        default="""You are a data extraction assistant. Extract the requested data elements from the provided document text.

Data elements to extract:
{elements}

Return the extracted data as a JSON object with field names as keys.
If a field cannot be found, use null as the value.
Return ONLY the JSON object, no additional text or explanation.

Example format:
{{"fieldName1": "value1", "fieldName2": 123, "fieldName3": null}}""",
        description="System prompt template for data extraction",
        json_schema_extra={"env": "EXTRACTION_PROMPT"}
    )
    validation: Optional[str] = Field(
        default=None,
        description="System prompt template for validation",
        json_schema_extra={"env": "VALIDATION_PROMPT"}
    )


class Settings(BaseSettings):
    """Application settings with type-safe Pydantic models.
    
    Configuration is loaded from config.json and can be overridden by environment variables.
    Environment variables take precedence over config.json values.
    """
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )
    
    # Core configuration sections
    min_confidence_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score for required fields",
        json_schema_extra={"env": "MIN_CONFIDENCE_THRESHOLD"}
    )
    max_buffer_size_mb: int = Field(
        default=10,
        gt=0,
        le=100,
        description="Maximum document buffer size in MB",
        json_schema_extra={"env": "MAX_BUFFER_SIZE_MB"}
    )
    azure_ai_foundry: AzureAIFoundryConfig
    azure_document_intelligence: Optional[AzureDocumentIntelligenceConfig] = None
    server_ports: ServerPortsConfig = Field(default_factory=ServerPortsConfig)
    prompts: PromptsConfig = Field(default_factory=PromptsConfig)
    
    # Azure authentication
    azure_tenant_id: Optional[str] = Field(
        default=None,
        description="Azure tenant ID for authentication",
        json_schema_extra={"env": "AZURE_TENANT_ID"}
    )
    
    # Internal state
    _credential: Optional[DefaultAzureCredential] = None
    
    @property
    def azure_credential(self) -> DefaultAzureCredential:
        """Get Azure credential for Entra ID authentication.
        
        Returns appropriate credential based on configuration:
        - ManagedIdentityCredential for production (when use_managed_identity=true)
        - DefaultAzureCredential for local development (tries multiple auth methods)
        """
        if self._credential is None:
            if self.azure_ai_foundry.use_managed_identity:
                # Production: Use managed identity
                print("Using ManagedIdentityCredential for Azure authentication")
                self._credential = ManagedIdentityCredential()
            else:
                # Development: Use DefaultAzureCredential (tries az cli, env vars, etc.)
                print("Using DefaultAzureCredential for Azure authentication")
                credential_kwargs = {}
                if self.azure_tenant_id:
                    credential_kwargs['tenant_id'] = self.azure_tenant_id
                self._credential = DefaultAzureCredential(**credential_kwargs)
        return self._credential
    
    @property
    def azure_ai_foundry_endpoint(self) -> str:
        """Azure AI Foundry project endpoint URL."""
        return self.azure_ai_foundry.project_endpoint
    
    @property
    def extraction_model(self) -> str:
        """Model deployment name for extraction."""
        return self.azure_ai_foundry.extraction_model
    
    @property
    def validation_model(self) -> Optional[str]:
        """Model deployment name for validation."""
        return self.azure_ai_foundry.validation_model
    
    @property
    def mcp_server_port(self) -> int:
        """MCP server port number."""
        return self.server_ports.mcp
    
    @property
    def a2a_server_port(self) -> int:
        """A2A server port number."""
        return self.server_ports.a2a
    
    @property
    def extraction_prompt(self) -> str:
        """System prompt template for data extraction."""
        return self.prompts.extraction
    
    @property
    def validation_prompt(self) -> Optional[str]:
        """System prompt template for validation."""
        return self.prompts.validation
    
    def validate_on_startup(self) -> None:
        """Perform comprehensive validation on startup.
        
        Raises:
            ValueError: If configuration is invalid with detailed error messages
        """
        errors = []
        
        # Validate Azure AI Foundry configuration
        if not self.azure_ai_foundry.project_endpoint:
            errors.append("Azure AI Foundry project endpoint is required")
        if not self.azure_ai_foundry.extraction_model:
            errors.append("Azure AI Foundry extraction model is required")
        
        # Validate buffer size
        if self.max_buffer_size_mb <= 0:
            errors.append(f"Invalid max_buffer_size_mb: {self.max_buffer_size_mb} (must be > 0)")
        
        # Validate confidence threshold
        if not 0.0 <= self.min_confidence_threshold <= 1.0:
            errors.append(f"Invalid min_confidence_threshold: {self.min_confidence_threshold} (must be 0.0-1.0)")
        
        # Validate Document Intelligence config if provided
        if self.azure_document_intelligence:
            if not self.azure_document_intelligence.use_managed_identity:
                if not self.azure_document_intelligence.endpoint:
                    errors.append("Azure Document Intelligence endpoint is required when not using managed identity")
        
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)
        
        print("✓ Configuration validation successful")
        print(f"  - Azure AI Foundry endpoint: {self.azure_ai_foundry_endpoint}")
        print(f"  - Extraction model: {self.extraction_model}")
        print(f"  - Validation model: {self.validation_model or 'Not configured'}")
        print(f"  - MCP server port: {self.mcp_server_port}")
        print(f"  - A2A server port: {self.a2a_server_port}")
        print(f"  - Min confidence threshold: {self.min_confidence_threshold}")
        print(f"  - Max buffer size: {self.max_buffer_size_mb} MB")


def load_settings_from_json(config_path: str = "config.json") -> Settings:
    """Load settings from JSON file with environment variable overrides.
    
    Args:
        config_path: Path to configuration JSON file
        
    Returns:
        Settings instance with validated configuration
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If configuration is invalid
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    # Load JSON configuration
    with open(config_file, 'r') as f:
        config_data = json.load(f)
    
    # Convert JSON keys to match Pydantic field names (camelCase -> snake_case)
    normalized_config = {
        'min_confidence_threshold': config_data.get('minConfidenceThreshold', 0.8),
        'max_buffer_size_mb': config_data.get('maxBufferSizeMB', 10),
        'azure_ai_foundry': {
            'project_endpoint': config_data.get('azureAIFoundry', {}).get('projectEndpoint'),
            'extraction_model': config_data.get('azureAIFoundry', {}).get('extractionModel'),
            'validation_model': config_data.get('azureAIFoundry', {}).get('validationModel'),
            'use_managed_identity': config_data.get('azureAIFoundry', {}).get('useManagedIdentity', False),
        },
        'server_ports': {
            'mcp': config_data.get('serverPorts', {}).get('mcp', 8000),
            'a2a': config_data.get('serverPorts', {}).get('a2a', 8001),
        },
        'prompts': {
            'extraction': config_data.get('prompts', {}).get('extraction'),
            'validation': config_data.get('prompts', {}).get('validation'),
        },
    }
    
    # Add Document Intelligence config if present
    if 'azureDocumentIntelligence' in config_data:
        normalized_config['azure_document_intelligence'] = {
            'endpoint': config_data['azureDocumentIntelligence'].get('endpoint'),
            'key': config_data['azureDocumentIntelligence'].get('key'),
            'use_managed_identity': config_data['azureDocumentIntelligence'].get('useManagedIdentity', False),
        }
    
    # Override with environment variables (they take precedence)
    env_overrides = {}
    
    # Azure AI Foundry overrides
    if os.getenv('AZURE_AI_FOUNDRY_ENDPOINT'):
        env_overrides.setdefault('azure_ai_foundry', {})['project_endpoint'] = os.getenv('AZURE_AI_FOUNDRY_ENDPOINT')
    if os.getenv('AZURE_EXTRACTION_MODEL'):
        env_overrides.setdefault('azure_ai_foundry', {})['extraction_model'] = os.getenv('AZURE_EXTRACTION_MODEL')
    if os.getenv('AZURE_VALIDATION_MODEL'):
        env_overrides.setdefault('azure_ai_foundry', {})['validation_model'] = os.getenv('AZURE_VALIDATION_MODEL')
    if os.getenv('AZURE_USE_MANAGED_IDENTITY'):
        env_overrides.setdefault('azure_ai_foundry', {})['use_managed_identity'] = os.getenv('AZURE_USE_MANAGED_IDENTITY').lower() == 'true'
    
    # Azure Document Intelligence overrides
    if os.getenv('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT'):
        env_overrides.setdefault('azure_document_intelligence', {})['endpoint'] = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT')
    if os.getenv('AZURE_DOCUMENT_INTELLIGENCE_KEY'):
        env_overrides.setdefault('azure_document_intelligence', {})['key'] = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_KEY')
    if os.getenv('AZURE_DOCUMENT_INTELLIGENCE_USE_MANAGED_IDENTITY'):
        env_overrides.setdefault('azure_document_intelligence', {})['use_managed_identity'] = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_USE_MANAGED_IDENTITY').lower() == 'true'
    
    # Server port overrides
    if os.getenv('MCP_SERVER_PORT'):
        env_overrides.setdefault('server_ports', {})['mcp'] = int(os.getenv('MCP_SERVER_PORT'))
    if os.getenv('A2A_SERVER_PORT'):
        env_overrides.setdefault('server_ports', {})['a2a'] = int(os.getenv('A2A_SERVER_PORT'))
    
    # Prompt overrides
    if os.getenv('EXTRACTION_PROMPT'):
        env_overrides.setdefault('prompts', {})['extraction'] = os.getenv('EXTRACTION_PROMPT')
    if os.getenv('VALIDATION_PROMPT'):
        env_overrides.setdefault('prompts', {})['validation'] = os.getenv('VALIDATION_PROMPT')
    
    # Core configuration overrides
    if os.getenv('MIN_CONFIDENCE_THRESHOLD'):
        env_overrides['min_confidence_threshold'] = float(os.getenv('MIN_CONFIDENCE_THRESHOLD'))
    if os.getenv('MAX_BUFFER_SIZE_MB'):
        env_overrides['max_buffer_size_mb'] = int(os.getenv('MAX_BUFFER_SIZE_MB'))
    if os.getenv('AZURE_TENANT_ID'):
        env_overrides['azure_tenant_id'] = os.getenv('AZURE_TENANT_ID')
    
    # Merge environment overrides
    for key, value in env_overrides.items():
        if isinstance(value, dict):
            normalized_config[key].update(value)
        else:
            normalized_config[key] = value
    
    # Create Settings instance
    settings = Settings(**normalized_config)
    
    # Validate configuration
    settings.validate_on_startup()
    
    return settings


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create global settings instance.
    
    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = load_settings_from_json()
    return _settings


def load_settings(config_path: str = "config.json") -> Settings:
    """Load settings from specified configuration file.
    
    Args:
        config_path: Path to configuration JSON file
        
    Returns:
        Settings instance with validated configuration
    """
    global _settings
    _settings = load_settings_from_json(config_path)
    return _settings
