"""MCP (Model Context Protocol) HTTP server for document extraction."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

from ..agents.extractor_agent import create_extractor_agent
from ..config.settings import get_settings


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
    errors: Optional[List[str]] = Field(default=None, description="Error messages if extraction failed")


# Configure module logger
log = logging.getLogger(__name__)


# Create FastAPI app
app = FastAPI(
    title="Agent Extractor MCP Server",
    description="Document extraction agent with MCP (Model Context Protocol) interface",
    version="0.1.0"
)


@app.on_event("startup")
async def startup_event() -> None:
    """Initialise shared settings and agent instances."""
    settings = get_settings()
    app.state.settings = settings
    app.state.agent = create_extractor_agent(settings)
    log.info(
        "MCP server initialised | port=%s",
        settings.mcp_server_port,
    )


@app.get("/health")
async def health_check():
    """Health check endpoint.
    
    Returns:
        Simple health status
    """
    return {"status": "healthy", "service": "agent-extractor"}


@app.post("/extract_document_data", response_model=ExtractDocumentResponse)
async def extract_document_data(request: ExtractDocumentRequest) -> ExtractDocumentResponse:
    """Extract structured data from a document.
    
    This is the main MCP tool endpoint for document extraction.
    
    Args:
        request: ExtractDocumentRequest with document and data elements
        
    Returns:
        ExtractDocumentResponse with extracted data or errors
        
    Raises:
        HTTPException: If request validation fails
    """
    agent = getattr(app.state, "agent", None)
    if agent is None:
        log.error("Extractor agent not initialised")
        raise HTTPException(status_code=500, detail="Agent not initialised")

    try:
        log.info(
            "Received extraction request | type=%s | data_elements=%s",
            request.fileType,
            len(request.dataElements),
        )

        data_elements = [element.model_dump() for element in request.dataElements]

        loop = asyncio.get_running_loop()
        result = await asyncio.to_thread(
            agent.extract_from_document,
            request.documentBase64,
            request.fileType,
            data_elements,
        )

        response_dict = result.to_dict()
        log.info("Extraction completed | success=%s", result.success)
        return ExtractDocumentResponse(**response_dict)

    except Exception as exc:  # pragma: no cover - pass context upstream
        log.exception("Unexpected error during extraction")
        raise HTTPException(status_code=500, detail=str(exc))


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
