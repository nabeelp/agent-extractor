"""MCP (Model Context Protocol) HTTP server for document extraction."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

from ..agents.orchestrator import create_orchestrator
from ..config.settings import get_settings
from ..exceptions import (
    Base64DecodingError,
    ConfigurationError,
    DocumentExtractionError,
    DocumentIntelligenceError,
    DocumentIntelligenceNotConfiguredError,
    DocumentParsingError,
    DocumentRoutingError,
    ExtractionError,
    InvalidExtractionResultError,
    RequiredFieldMissingError,
    UnsupportedFileTypeError,
)


# Request/Response models for MCP tool
class DataElement(BaseModel):
    """Data element to extract from document."""
    name: str = Field(..., description="Field name for extracted data")
    description: str = Field(..., description="Description of what to extract")
    format: str = Field(default="string", description="Expected data format (string, number, date, etc.)")
    required: bool = Field(default=False, description="Whether this field is required")


class ExtractDocumentRequest(BaseModel):
    """Request for extract_document_data tool."""
    documentBase64: str = Field(..., description="Base64 encoded document buffer")
    fileType: str = Field(..., description="Document type (pdf, docx, png, jpg)")
    dataElements: List[DataElement] = Field(..., description="Array of data elements to extract")


class ExtractDocumentResponse(BaseModel):
    """Response from extract_document_data tool."""
    success: bool = Field(..., description="Whether extraction succeeded")
    extractedData: Dict[str, Any] = Field(default_factory=dict, description="Extracted data with field names as keys")
    confidence: Optional[Dict[str, float]] = Field(default=None, description="Per-field confidence scores (0.0-1.0)")
    overall_confidence: Optional[float] = Field(default=None, description="Overall confidence score")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Routing and extraction context metadata")
    errors: Optional[List[str]] = Field(default=None, description="Error messages if extraction failed")


# Configure module logger
log = logging.getLogger(__name__)


def map_exception_to_http_error(exc: Exception, metadata: Optional[Dict[str, Any]] = None) -> HTTPException:
    """Map domain exceptions to HTTP errors with appropriate status codes.
    
    This centralizes error handling logic and ensures consistent error responses
    across all MCP endpoints.
    
    Args:
        exc: The exception to map
        metadata: Optional metadata to include in the error response
        
    Returns:
        HTTPException with appropriate status code and detail message
    """
    combined_metadata: Optional[Dict[str, Any]] = metadata or getattr(exc, "details", None)

    def _http_exception(status_code: int, detail: Dict[str, Any]) -> HTTPException:
        if combined_metadata:
            detail.setdefault("metadata", combined_metadata)
        return HTTPException(status_code=status_code, detail=detail)

    # Client errors (4xx)
    if isinstance(exc, UnsupportedFileTypeError):
        return _http_exception(
            400,
            {
                "error": "unsupported_file_type",
                "message": str(exc),
                "file_type": exc.file_type,
                "supported_types": exc.supported_types,
            },
        )
    
    if isinstance(exc, Base64DecodingError):
        return _http_exception(
            400,
            {
                "error": "invalid_base64",
                "message": str(exc),
            },
        )
    
    if isinstance(exc, DocumentParsingError):
        return _http_exception(
            400,
            {
                "error": "document_parsing_failed",
                "message": str(exc),
            },
        )
    
    if isinstance(exc, RequiredFieldMissingError):
        return _http_exception(
            422,
            {
                "error": "required_field_missing",
                "message": str(exc),
                "field_name": exc.field_name,
                "field_description": exc.details.get("field_description"),
            },
        )
    
    if isinstance(exc, InvalidExtractionResultError):
        return _http_exception(
            422,
            {
                "error": "invalid_extraction_result",
                "message": str(exc),
            },
        )
    
    if isinstance(exc, DocumentRoutingError):
        return _http_exception(
            400,
            {
                "error": "document_routing_failed",
                "message": str(exc),
            },
        )
    
    # Server errors (5xx)
    if isinstance(exc, ConfigurationError):
        return _http_exception(
            500,
            {
                "error": "configuration_error",
                "message": str(exc),
            },
        )
    
    if isinstance(exc, DocumentIntelligenceNotConfiguredError):
        return _http_exception(
            503,
            {
                "error": "document_intelligence_not_configured",
                "message": str(exc),
            },
        )
    
    if isinstance(exc, DocumentIntelligenceError):
        return _http_exception(
            502,
            {
                "error": "document_intelligence_failed",
                "message": str(exc),
            },
        )
    
    if isinstance(exc, ExtractionError):
        return _http_exception(
            500,
            {
                "error": "extraction_failed",
                "message": str(exc),
            },
        )
    
    # Generic document extraction errors
    if isinstance(exc, DocumentExtractionError):
        return _http_exception(
            500,
            {
                "error": "document_extraction_error",
                "message": str(exc),
            },
        )
    
    # Unknown errors (500)
    log.exception("Unexpected error: %s", exc)
    return _http_exception(
        500,
        {
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
        },
    )


# Create FastAPI app
app = FastAPI(
    title="Agent Extractor MCP Server",
    description="Document extraction agent with MCP (Model Context Protocol) interface",
    version="0.1.0"
)
@app.on_event("startup")
async def startup_event() -> None:
    """Initialise shared settings and orchestrator instance."""
    settings = get_settings()
    app.state.settings = settings
    app.state.orchestrator = create_orchestrator(settings)
    log.info(
        "MCP server initialised with orchestrator | port=%s",
        settings.mcp_server_port,
    )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    orchestrator = getattr(app.state, "orchestrator", None)
    if orchestrator is not None:
        await orchestrator.aclose()


@app.get("/health")
async def health_check():
    """Health check endpoint.
    
    Returns:
        Simple health status
    """
    return {"status": "healthy", "service": "agent-extractor"}


@app.post("/extract_document_data", response_model=ExtractDocumentResponse)
async def extract_document_data(request: ExtractDocumentRequest) -> ExtractDocumentResponse:
    """Extract structured data from a document using orchestrated workflow.
    
    This endpoint uses the orchestrator to coordinate:
    1. Extractor agent: Routes, parses, and extracts data
    2. Validator agent: Validates data and assigns confidence scores
    
    Args:
        request: ExtractDocumentRequest with document and data elements
        
    Returns:
        ExtractDocumentResponse with extracted data, confidence scores, metadata, or errors
        
    Raises:
        HTTPException: If request validation fails or extraction errors occur
    """
    orchestrator = getattr(app.state, "orchestrator", None)
    if orchestrator is None:
        log.error("Orchestrator not initialised")
        raise HTTPException(status_code=500, detail="Orchestrator not initialised")

    try:
        log.info(
            "Received extraction request | type=%s | data_elements=%s",
            request.fileType,
            len(request.dataElements),
        )

        data_elements = [element.model_dump() for element in request.dataElements]

        # Execute orchestrated workflow (extraction → validation)
        result = await orchestrator.orchestrate(
            request.documentBase64,
            request.fileType,
            data_elements,
        )

        # Convert orchestration result to response
        response_dict = result.to_dict()
        log.info(
            "Orchestration completed | success=%s | overall_confidence=%.2f",
            result.success,
            result.overall_confidence,
        )
        return ExtractDocumentResponse(**response_dict)

    except DocumentExtractionError as exc:
        # Use centralized error mapping for all domain exceptions
        raise map_exception_to_http_error(exc)
    except Exception as exc:
        # Catch-all for unexpected errors
        raise map_exception_to_http_error(exc)


def start_server(host: str = "0.0.0.0", port: Optional[int] = None):
    """Start the MCP HTTP server.
    
    Args:
        host: Host to bind to (default: 0.0.0.0 for all interfaces)
        port: Port to bind to (default: from settings)
    """
    settings = get_settings()
    server_port = port or settings.mcp_server_port
    
    log.info("Starting MCP server | host=%s | port=%s", host, server_port)
    log.info("Health check available at http://%s:%s/health", host, server_port)
    log.info(
        "Extraction endpoint available at http://%s:%s/extract_document_data",
        host,
        server_port,
    )

    uvicorn.run(app, host=host, port=server_port)


if __name__ == "__main__":
    start_server()
