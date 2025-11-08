"""MCP (Model Context Protocol) HTTP server for document extraction."""

from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

from ..config.settings import get_settings
from ..agents.extractor_agent import create_extractor_agent


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


# Create FastAPI app
app = FastAPI(
    title="Agent Extractor MCP Server",
    description="Document extraction agent with MCP (Model Context Protocol) interface",
    version="0.1.0"
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
    try:
        print(f"[MCP Server] Received extraction request for {request.fileType} document")
        print(f"[MCP Server] Data elements: {len(request.dataElements)}")
        
        # Get settings and create agent
        settings = get_settings()
        agent = create_extractor_agent(settings)
        
        # Convert Pydantic models to dicts for agent
        data_elements = [element.model_dump() for element in request.dataElements]
        
        # Execute extraction
        result = agent.extract_from_document(
            document_base64=request.documentBase64,
            file_type=request.fileType,
            data_elements=data_elements
        )
        
        # Convert result to response
        response_dict = result.to_dict()
        print(f"[MCP Server] Extraction {'succeeded' if result.success else 'failed'}")
        
        return ExtractDocumentResponse(**response_dict)
        
    except Exception as e:
        print(f"[MCP Server] Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def start_server(host: str = "0.0.0.0", port: Optional[int] = None):
    """Start the MCP HTTP server.
    
    Args:
        host: Host to bind to (default: 0.0.0.0 for all interfaces)
        port: Port to bind to (default: from settings)
    """
    settings = get_settings()
    server_port = port or settings.mcp_server_port
    
    print(f"[MCP Server] Starting on {host}:{server_port}")
    print(f"[MCP Server] Health check: http://{host}:{server_port}/health")
    print(f"[MCP Server] Extract endpoint: http://{host}:{server_port}/extract_document_data")
    
    uvicorn.run(app, host=host, port=server_port)


if __name__ == "__main__":
    start_server()
