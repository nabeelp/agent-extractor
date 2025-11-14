"""Configuration management for agent-extractor.

Provides type-safe configuration using Pydantic models with validation,
environment variable overrides, and Azure credential management.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, ClassVar, Dict, Optional

from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from dotenv import load_dotenv
from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..exceptions import ConfigurationError


log = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


class AzureAIFoundryConfig(BaseModel):
    """Azure AI Foundry configuration."""

    model_config = SettingsConfigDict(populate_by_name=True)

    project_endpoint: str = Field(
        ...,
        alias="projectEndpoint",
        validation_alias=AliasChoices("projectEndpoint", "project_endpoint"),
        description="Azure AI Foundry project endpoint URL",
        json_schema_extra={"env": "AZURE_AI_FOUNDRY_ENDPOINT"},
    )
    extraction_model: str = Field(
        ...,
        alias="extractionModel",
        validation_alias=AliasChoices("extractionModel", "extraction_model"),
        description="Model deployment name for extraction (e.g., gpt-4o)",
        json_schema_extra={"env": "AZURE_EXTRACTION_MODEL"},
    )
    validation_model: Optional[str] = Field(
        default=None,
        alias="validationModel",
        validation_alias=AliasChoices("validationModel", "validation_model"),
        description="Model deployment name for validation (e.g., gpt-4o-mini)",
        json_schema_extra={"env": "AZURE_VALIDATION_MODEL"},
    )
    use_managed_identity: bool = Field(
        default=False,
        alias="useManagedIdentity",
        validation_alias=AliasChoices("useManagedIdentity", "use_managed_identity"),
        description="Use managed identity for authentication (production)",
        json_schema_extra={"env": "AZURE_USE_MANAGED_IDENTITY"},
    )

    @field_validator("project_endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        if not value:
            raise ConfigurationError("Azure AI Foundry project endpoint is required")
        if not value.startswith(("http://", "https://")):
            raise ConfigurationError(f"Invalid endpoint URL format: {value}")
        return value.rstrip("/")

    @field_validator("extraction_model")
    @classmethod
    def validate_extraction_model(cls, value: str) -> str:
        if not value:
            raise ConfigurationError("Extraction model name is required")
        return value


class AzureDocumentIntelligenceConfig(BaseModel):
    """Azure Document Intelligence configuration."""

    model_config = SettingsConfigDict(populate_by_name=True)

    endpoint: Optional[str] = Field(
        default=None,
        alias="endpoint",
        validation_alias=AliasChoices("endpoint", "endpoint"),
        description="Azure Document Intelligence endpoint URL",
        json_schema_extra={"env": "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"},
    )
    key: Optional[str] = Field(
        default=None,
        alias="key",
        validation_alias=AliasChoices("key", "key"),
        description="Azure Document Intelligence API key (use managed identity instead for production)",
        json_schema_extra={"env": "AZURE_DOCUMENT_INTELLIGENCE_KEY"},
    )
    use_managed_identity: bool = Field(
        default=False,
        alias="useManagedIdentity",
        validation_alias=AliasChoices("useManagedIdentity", "use_managed_identity"),
        description="Use managed identity for authentication",
        json_schema_extra={"env": "AZURE_DOCUMENT_INTELLIGENCE_USE_MANAGED_IDENTITY"},
    )

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: Optional[str]) -> Optional[str]:
        if value and not value.startswith(("http://", "https://")):
            raise ConfigurationError(f"Invalid endpoint URL format: {value}")
        return value.rstrip("/") if value else None


class ServerPortsConfig(BaseModel):
    """Server port configuration."""

    model_config = SettingsConfigDict(populate_by_name=True)

    mcp: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        alias="mcp",
        description="MCP server port number",
        json_schema_extra={"env": "MCP_SERVER_PORT"},
    )
    a2a: int = Field(
        default=8001,
        ge=1024,
        le=65535,
        alias="a2a",
        description="A2A agent server port number",
        json_schema_extra={"env": "A2A_SERVER_PORT"},
    )

    @model_validator(mode="after")
    def validate_unique_ports(self) -> "ServerPortsConfig":
        if self.mcp == self.a2a:
            raise ConfigurationError("MCP and A2A server ports must be different")
        return self


class UseDocumentIntelligenceConfig(BaseModel):
    """Configuration for when to use Document Intelligence."""

    model_config = SettingsConfigDict(populate_by_name=True)

    scanned_document: bool = Field(
        default=True,
        alias="scannedDocument",
        validation_alias=AliasChoices("scannedDocument", "scanned_document"),
        description="Use Document Intelligence for scanned documents",
    )
    low_text_density: bool = Field(
        default=True,
        alias="lowTextDensity",
        validation_alias=AliasChoices("lowTextDensity", "low_text_density"),
        description="Use Document Intelligence for documents with low text density",
    )
    poor_image_quality: bool = Field(
        default=True,
        alias="poorImageQuality",
        validation_alias=AliasChoices("poorImageQuality", "poor_image_quality"),
        description="Use Document Intelligence for poor quality images",
    )


class RoutingThresholdsConfig(BaseModel):
    """Routing thresholds configuration."""

    model_config = SettingsConfigDict(populate_by_name=True)

    use_document_intelligence: UseDocumentIntelligenceConfig = Field(
        default_factory=UseDocumentIntelligenceConfig,
        alias="useDocumentIntelligence",
        validation_alias=AliasChoices("useDocumentIntelligence", "use_document_intelligence"),
        description="Criteria for using Document Intelligence",
    )
    text_density_threshold: int = Field(
        default=100,
        ge=0,
        alias="textDensityThreshold",
        validation_alias=AliasChoices("textDensityThreshold", "text_density_threshold"),
        description="Minimum text density (chars per page) for text-based extraction",
    )
    low_resolution_threshold: int = Field(
        default=500000,
        ge=0,
        alias="lowResolutionThreshold",
        validation_alias=AliasChoices("lowResolutionThreshold", "low_resolution_threshold"),
        description="Pixel count threshold for low resolution images",
    )


class PromptsConfig(BaseModel):
    """Prompt templates configuration."""

    model_config = SettingsConfigDict(populate_by_name=True)

    extraction: str = Field(
        default="""You are a data extraction assistant. Extract the requested data elements from the provided document text.

Data elements to extract:
{elements}

Return the extracted data as a JSON object with field names as keys.
If a field cannot be found, use null as the value.
Return ONLY the JSON object, no additional text or explanation.

Example format:
{{"fieldName1": "value1", "fieldName2": 123, "fieldName3": null}}""",
        alias="extraction",
        validation_alias=AliasChoices("extraction", "extraction"),
        description="System prompt template for data extraction",
        json_schema_extra={"env": "EXTRACTION_PROMPT"},
    )
    validation: Optional[str] = Field(
        default=None,
        alias="validation",
        validation_alias=AliasChoices("validation", "validation"),
        description="System prompt template for validation",
        json_schema_extra={"env": "VALIDATION_PROMPT"},
    )


class Settings(BaseSettings):
    """Application settings with type-safe Pydantic models."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    _config_file_path: ClassVar[Path] = Path("config.json")

    min_confidence_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        alias="minConfidenceThreshold",
        validation_alias=AliasChoices("minConfidenceThreshold", "min_confidence_threshold"),
        description="Minimum confidence score for required fields",
        json_schema_extra={"env": "MIN_CONFIDENCE_THRESHOLD"},
    )
    max_buffer_size_mb: int = Field(
        default=10,
        gt=0,
        le=100,
        alias="maxBufferSizeMB",
        validation_alias=AliasChoices("maxBufferSizeMB", "max_buffer_size_mb"),
        description="Maximum document buffer size in MB",
        json_schema_extra={"env": "MAX_BUFFER_SIZE_MB"},
    )
    azure_ai_foundry: AzureAIFoundryConfig = Field(alias="azureAIFoundry")
    azure_document_intelligence: Optional[AzureDocumentIntelligenceConfig] = Field(
        default=None,
        alias="azureDocumentIntelligence",
    )
    routing_thresholds: RoutingThresholdsConfig = Field(
        default_factory=RoutingThresholdsConfig,
        alias="routingThresholds",
    )
    server_ports: ServerPortsConfig = Field(
        default_factory=ServerPortsConfig,
        alias="serverPorts",
    )
    prompts: PromptsConfig = Field(
        default_factory=PromptsConfig,
        alias="prompts",
    )

    azure_tenant_id: Optional[str] = Field(
        default=None,
        alias="azureTenantId",
        validation_alias=AliasChoices("azureTenantId", "azure_tenant_id"),
        description="Azure tenant ID for authentication",
        json_schema_extra={"env": "AZURE_TENANT_ID"},
    )

    _credential: Optional[DefaultAzureCredential] = None

    @classmethod
    def configure(cls, config_path: Path | str) -> None:
        cls._config_file_path = Path(config_path)

    @classmethod
    def _json_config_settings_source(
        cls,
        _: Optional[BaseSettings] = None,
    ) -> Dict[str, Any]:
        if not cls._config_file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {cls._config_file_path}")
        with cls._config_file_path.open("r", encoding="utf-8") as config_file:
            return json.load(config_file)

    @classmethod
    def _env_override_settings_source(
        cls,
        _: Optional[BaseSettings] = None,
    ) -> Dict[str, Any]:
        """Custom environment variable source that handles nested config overrides."""
        env_config = {}
        
        # Azure Document Intelligence overrides
        di_endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        di_key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
        di_use_mi = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_USE_MANAGED_IDENTITY")
        
        if any([di_endpoint, di_key, di_use_mi]):
            env_config["azureDocumentIntelligence"] = {}
            if di_endpoint:
                env_config["azureDocumentIntelligence"]["endpoint"] = di_endpoint
            if di_key:
                env_config["azureDocumentIntelligence"]["key"] = di_key
            if di_use_mi:
                env_config["azureDocumentIntelligence"]["useManagedIdentity"] = di_use_mi.lower() in ("true", "1", "yes")
        
        # Azure AI Foundry overrides
        foundry_endpoint = os.getenv("AZURE_AI_FOUNDRY_ENDPOINT")
        extraction_model = os.getenv("AZURE_EXTRACTION_MODEL")
        validation_model = os.getenv("AZURE_VALIDATION_MODEL")
        use_mi = os.getenv("AZURE_USE_MANAGED_IDENTITY")
        
        if any([foundry_endpoint, extraction_model, validation_model, use_mi]):
            env_config["azureAIFoundry"] = {}
            if foundry_endpoint:
                env_config["azureAIFoundry"]["projectEndpoint"] = foundry_endpoint
            if extraction_model:
                env_config["azureAIFoundry"]["extractionModel"] = extraction_model
            if validation_model:
                env_config["azureAIFoundry"]["validationModel"] = validation_model
            if use_mi:
                env_config["azureAIFoundry"]["useManagedIdentity"] = use_mi.lower() in ("true", "1", "yes")
        
        # Server ports overrides
        mcp_port = os.getenv("MCP_SERVER_PORT")
        a2a_port = os.getenv("A2A_SERVER_PORT")
        
        if any([mcp_port, a2a_port]):
            env_config["serverPorts"] = {}
            if mcp_port:
                env_config["serverPorts"]["mcp"] = int(mcp_port)
            if a2a_port:
                env_config["serverPorts"]["a2a"] = int(a2a_port)
        
        # Top-level overrides
        min_confidence = os.getenv("MIN_CONFIDENCE_THRESHOLD")
        if min_confidence:
            env_config["minConfidenceThreshold"] = float(min_confidence)
        
        max_buffer = os.getenv("MAX_BUFFER_SIZE_MB")
        if max_buffer:
            env_config["maxBufferSizeMB"] = int(max_buffer)
        
        tenant_id = os.getenv("AZURE_TENANT_ID")
        if tenant_id:
            env_config["azureTenantId"] = tenant_id
        
        # Prompts overrides
        extraction_prompt = os.getenv("EXTRACTION_PROMPT")
        validation_prompt = os.getenv("VALIDATION_PROMPT")
        
        if any([extraction_prompt, validation_prompt]):
            env_config["prompts"] = {}
            if extraction_prompt:
                env_config["prompts"]["extraction"] = extraction_prompt
            if validation_prompt:
                env_config["prompts"]["validation"] = validation_prompt
        
        return env_config

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # Priority order (highest to lowest):
        # 1. Environment variables (custom env override source)
        # 2. Constructor arguments (init_settings)
        # 3. config.json file (JSON config)
        # 4. File secrets (file_secret_settings)
        return (
            cls._env_override_settings_source,
            init_settings,
            cls._json_config_settings_source,
            file_secret_settings,
        )

    @property
    def azure_credential(self) -> DefaultAzureCredential:
        if self._credential is None:
            if self.azure_ai_foundry.use_managed_identity:
                log.info("Using ManagedIdentityCredential for Azure authentication")
                self._credential = ManagedIdentityCredential()
            else:
                credential_kwargs: Dict[str, Any] = {}
                if self.azure_tenant_id:
                    credential_kwargs["tenant_id"] = self.azure_tenant_id
                log.info("Using DefaultAzureCredential for Azure authentication")
                self._credential = DefaultAzureCredential(**credential_kwargs)
        return self._credential

    @property
    def azure_ai_foundry_endpoint(self) -> str:
        return self.azure_ai_foundry.project_endpoint

    @property
    def extraction_model(self) -> str:
        return self.azure_ai_foundry.extraction_model

    @property
    def validation_model(self) -> Optional[str]:
        return self.azure_ai_foundry.validation_model

    @property
    def mcp_server_port(self) -> int:
        return self.server_ports.mcp

    @property
    def a2a_server_port(self) -> int:
        return self.server_ports.a2a

    @property
    def extraction_prompt(self) -> str:
        return self.prompts.extraction

    @property
    def validation_prompt(self) -> Optional[str]:
        return self.prompts.validation

    def validate_on_startup(self) -> None:
        errors = []

        if not self.azure_ai_foundry.project_endpoint:
            errors.append("Azure AI Foundry project endpoint is required")
        if not self.azure_ai_foundry.extraction_model:
            errors.append("Azure AI Foundry extraction model is required")

        if self.max_buffer_size_mb <= 0:
            errors.append(f"Invalid max_buffer_size_mb: {self.max_buffer_size_mb} (must be > 0)")
        if not 0.0 <= self.min_confidence_threshold <= 1.0:
            errors.append(
                f"Invalid min_confidence_threshold: {self.min_confidence_threshold} (must be 0.0-1.0)",
            )

        if self.azure_document_intelligence and not self.azure_document_intelligence.use_managed_identity:
            if not self.azure_document_intelligence.endpoint:
                errors.append(
                    "Azure Document Intelligence endpoint is required when not using managed identity",
                )

        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
            raise ConfigurationError(error_msg)

        log.info("Configuration validation successful")
        log.info("Azure AI Foundry endpoint: %s", self.azure_ai_foundry_endpoint)
        log.info("Extraction model: %s", self.extraction_model)
        log.info("Validation model: %s", self.validation_model or "Not configured")
        log.info("MCP server port: %s", self.mcp_server_port)
        log.info("A2A server port: %s", self.a2a_server_port)
        log.info("Min confidence threshold: %s", self.min_confidence_threshold)
        log.info("Max buffer size (MB): %s", self.max_buffer_size_mb)


# Configure default config path once module is imported
Settings.configure(Path("config.json"))


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.validate_on_startup()
    return _settings


def load_settings(config_path: str = "config.json") -> Settings:
    Settings.configure(config_path)
    global _settings
    _settings = Settings()
    _settings.validate_on_startup()
    return _settings
