# Document Extraction Agent with MCP and Azure Document Intelligence

## Task List

Track implementation progress for the agent-extractor solution. Update status as tasks are completed.

---

## MVP: Minimal Viable Product (Core Functionality)

### Phase 1: Project Setup ✓
- [x] Initialize Python project structure (venv, requirements.txt, pyproject.toml)
- [x] Install agent-framework-azure-ai --pre and core dependencies
- [x] Create directory structure (src/, src/config/, src/extraction/, src/agents/, src/interfaces/)
- [x] Set up .gitignore for Python (.venv, __pycache__, *.pyc, .env)
- [x] Create README.md with setup instructions

### Phase 2: MVP Configuration (Basic)
- [x] Create minimal config.json with essential values (Azure endpoints, single model deployment)
- [x] Implement basic src/config/settings.py configuration loader
- [x] Add Entra ID (Azure AD) authentication with DefaultAzureCredential
- [x] Simple configuration validation

### Phase 3: MVP Extraction (Single Format - PDF Only)
- [x] Implement src/extraction/document_parser.py (base64 decoding, PDF text extraction only)
- [x] Implement src/extraction/extractor.py (gpt-4o text extraction, no vision, no Document Intelligence)
- [x] Basic error handling (try/catch, simple error messages)
- [x] Single-page PDF support only

### Phase 4: MVP Agent (Single Agent)
- [x] Implement src/agents/extractor_agent.py (basic Microsoft Agent Framework agent)
- [x] Simple extraction workflow (parser → extractor)
- [x] Return extracted data as JSON (no validation, no confidence scoring)
- [x] Basic logging with print statements

### Phase 5: MVP MCP Interface (HTTP Only)
- [x] Implement src/interfaces/mcp_server.py (FastAPI HTTP endpoint only, no WebSocket)
- [x] Define extract_document_data tool schema (simplified input/output)
- [x] Integrate MCP server with extractor agent
- [x] Basic health check endpoint (return 200 OK)
- [x] Test MCP tool with simple HTTP client (curl/Postman)

### Phase 6: MVP Testing & Documentation
- [x] Manual testing with sample PDF documents
- [x] Document MVP limitations in README.md
- [x] Create simple usage example (HTTP POST with sample PDF)
- [x] Basic troubleshooting section

---

## Production Enhancement: Phase 1 (Robustness)

### Phase 7: Enhanced Configuration ✓
- [x] Add Pydantic models for type-safe configuration
- [x] Enhance Entra ID authentication with managed identity for production
- [x] Add configuration validation on startup with detailed error messages
- [x] Support environment variable overrides for all config values

### Phase 8: Multi-Format Support ✓
- [x] Add DOCX support to document_parser.py (python-docx)
- [x] Add image support (PNG, JPG) to document_parser.py (Pillow)
- [x] Implement src/extraction/router.py (document type detection)
- [x] Add Azure Document Intelligence integration for scanned/complex documents
- [x] Add multi-page document aggregation

### Phase 9: Validation & Confidence Scoring
- [ ] Implement src/extraction/validator.py (gpt-4o-mini for validation)
- [ ] Implement src/agents/validator_agent.py (validation agent)
- [ ] Implement src/agents/orchestrator.py (sequential workflow coordinator)
- [ ] Add per-field confidence scores
- [ ] Add required field validation against configurable threshold
- [ ] Test sequential workflow: Router → Extractor → Validator

### Phase 10: Enhanced Error Handling & Resilience
- [ ] Add buffer size validation
- [ ] Add retry logic with exponential backoff
- [ ] Add timeout handling for long-running extractions
- [ ] Add detailed error messages with error codes
- [ ] Add request validation middleware

### Phase 11: Testing & Quality
- [ ] Add unit tests for each extraction module (pytest)
- [ ] Add integration tests for agent workflows
- [ ] Add sample documents for testing (PDF, DOCX, PNG, JPG)
- [ ] Add code coverage reporting (>80% target)
- [ ] Add type checking (mypy)

---

## Production Enhancement: Phase 2 (Scalability & Deployment)

### Phase 12: WebSocket & A2A Support
- [ ] Add WebSocket support to MCP server
- [ ] Implement src/interfaces/agent_server.py (A2A distributed runtime)
- [ ] Define agent events (document.extraction.requested/completed/failed)
- [ ] Add state persistence for async operations
- [ ] Test A2A communication patterns
- [ ] Add A2A agent documentation

### Phase 13: Containerization
- [ ] Create Dockerfile with multi-stage build
- [ ] Create .dockerignore for Python projects
- [ ] Test local Docker build and run
- [ ] Optimize image size (use slim Python base, multi-stage build)
- [ ] Add health probes (liveness, readiness)

### Phase 14: Azure Deployment
- [ ] Create azure-container-app.yaml manifest
- [ ] Configure dual ingress (ports 8000, 8001)
- [ ] Configure auto-scaling rules (CPU/memory/HTTP requests)
- [ ] Set up managed identity in Azure
- [ ] Deploy to Azure Container Apps
- [ ] Test deployed endpoints (MCP and A2A)
- [ ] Configure custom domains and SSL certificates

### Phase 15: API Management Integration
- [ ] Create Azure API Management instance (or use existing)
- [ ] Import MCP OpenAPI specification into APIM
- [ ] Configure APIM policies (rate limiting, throttling, caching)
- [ ] Add API key authentication in APIM
- [ ] Configure request/response transformation policies
- [ ] Set up APIM developer portal for API documentation
- [ ] Add monitoring and analytics in APIM
- [ ] Test MCP access through APIM gateway
- [ ] Document APIM endpoint URLs and authentication

---

## Production Enhancement: Phase 3 (Observability & Operations)

### Phase 16: Monitoring & Telemetry
- [ ] Add Application Insights integration
- [ ] Add structured logging (JSON format)
- [ ] Add custom metrics (extraction success rate, processing time, confidence scores)
- [ ] Add distributed tracing for multi-agent workflows
- [ ] Create Azure Monitor dashboards
- [ ] Set up alerts for failures and performance degradation

### Phase 17: Documentation & Operations
- [ ] Add comprehensive API reference documentation
- [ ] Add architecture diagrams (sequence diagrams, component diagrams)
- [ ] Create deployment runbook
- [ ] Create troubleshooting guide with common issues
- [ ] Add performance tuning guide
- [ ] Add security best practices documentation
- [ ] Create usage examples for all supported document types

---

## Future Enhancements (Post-Production)

### Phase 18: Extended Format Support
- [ ] Add support for Excel (XLSX) documents
- [ ] Add support for TXT and HTML documents
- [ ] Add support for email formats (MSG, EML)
- [ ] Add support for compressed archives (ZIP extraction)

### Phase 19: Advanced Features
- [ ] Implement batch processing for multiple documents
- [ ] Add streaming results for large documents
- [ ] Add caching layer for repeated extractions (Redis)
- [ ] Add document fingerprinting for duplicate detection
- [ ] Add support for encrypted/password-protected documents

### Phase 20: AI Enhancements
- [ ] Fine-tune custom extraction models for specific document types
- [ ] Add multi-language document support (automatic language detection)
- [ ] Add table extraction and structure preservation
- [ ] Add handwriting recognition support
- [ ] Add form field detection and auto-mapping
- [ ] Add entity recognition and linking (NER)

## Overview

Build a greenfield document extraction agent using Microsoft Agent Framework (Python) that exposes both MCP tools and A2A agent interfaces for extracting structured data from multi-format documents (PDF, DOCX, images). The agent will intelligently route extraction between LLM-based and Azure Document Intelligence methods, then validate results with confidence scoring, deployed as an Azure Container App.

## Technology Choices

### Why Python?
- Microsoft Agent Framework officially supports Python and .NET (no TypeScript/Node.js support)
- Python SDK (`agent-framework-azure-ai`) provides integrated Azure AI Foundry support
- Rich ecosystem for document processing (PyPDF2, python-docx, Pillow)

### Why Azure AI Foundry?
- Production-ready for multi-agent orchestration systems
- Built-in support for workflows and agent coordination patterns
- Managed identity and enterprise security features
- Better suited for complex agent systems vs. GitHub models (recommended for simple/getting-started scenarios)

### Model Selection
- **gpt-4o**: Primary extraction model with vision capabilities for multimodal document processing (images, scanned PDFs)
- **gpt-4o-mini**: Lightweight validation model for cost-effective confidence scoring and field verification
- Both models deployed via Azure AI Foundry for production reliability

## Architecture

### Dual Interface Pattern
- **MCP Server**: HTTP/WebSocket endpoint for AI assistant integration (Claude Desktop, VS Code, other MCP clients)
- **A2A Agent**: Agent-to-agent communication for orchestrated workflows and automation pipelines

### Multi-Agent Orchestration Pattern
**Sequential Workflow** with handoff pattern:
1. Router Agent → analyzes document and selects extraction strategy
2. Extractor Agent → processes document using selected method
3. Validator Agent → verifies results and assigns confidence scores
4. Results aggregated and returned to caller

### Core Components
1. **Extraction Router**: Analyzes document complexity to select optimal extraction method
2. **Document Parser**: Converts base64 buffers to text/images for processing
3. **Extractor**: Integrates with Azure AI Foundry models (gpt-4o) and Azure Document Intelligence
4. **Validator**: Cross-references extracted data and assigns confidence scores using gpt-4o-mini

## Prerequisites

### Azure AI Foundry Setup
1. **Azure AI Foundry Project**: Create or use existing project in Azure portal
2. **Model Deployments**: Deploy gpt-4o and gpt-4o-mini models in your Azure AI Foundry project
3. **Azure Document Intelligence**: Create Azure Document Intelligence resource
4. **Entra ID Authentication**: Solution uses Entra ID (Azure AD) authentication via DefaultAzureCredential
   - For local development: Run `az login` to authenticate
   - For production: Configure managed identity in Azure Container Apps
5. **VS Code Extension**: Install Azure AI Foundry extension for resource management
   - Open Command Palette and run: `workbench.view.extension.azure-ai-foundry`

### Reference Resources
- **Microsoft Agent Framework GitHub**: https://github.com/microsoft/agent-framework
  - MCP integration examples
  - Multi-agent orchestration patterns (sequential, concurrent, handoff)
  - Multimodal and vision API examples
  - Workflow patterns (fan-out/fan-in, loops, conditionals)

## Implementation Plan

### Step 1: Initialize Python Project
- Create `requirements.txt` with dependencies:
  - **`agent-framework-azure-ai --pre`** (⚠️ **REQUIRED**: `--pre` flag needed during preview)
  - `@modelcontextprotocol/sdk` for MCP server (or Python MCP library)
  - `azure-ai-formrecognizer` (Azure Document Intelligence SDK)
  - `PyPDF2` or `pypdf` (PDF processing)
  - `python-docx` (DOCX processing)
  - `Pillow` (image processing)
  - `python-dotenv` (environment configuration)
- Create `pyproject.toml` for project metadata
- Set up virtual environment and install dependencies using uv:
  ```bash
  # Install uv (if not already installed)
  pip install uv
  
  # Sync dependencies (creates .venv automatically)
  uv sync
  
  # Install Agent Framework with --pre flag
  uv pip install agent-framework-azure-ai --pre
  ```

### Step 2: Create JSON Configuration System
- **config.json**: Default configuration values
  - `minConfidenceThreshold`: Minimum confidence score for required fields (default: 0.8)
  - `maxBufferSizeMB`: Maximum document buffer size in MB (default: 10)
  - `azureDocumentIntelligence`: Endpoint and key (or use managed identity)
  - `azureAIFoundry`: Project endpoint, connection string, and model deployment names (gpt-4o, gpt-4o-mini)
  - `routingThresholds`: Criteria for choosing extraction method
  - `serverPorts`: MCP server (8000), A2A server (8001)

- **src/config/settings.py**: Configuration loader
  - Load and validate config.json
  - Provide typed configuration using Pydantic or dataclasses
  - Environment variable override support for secrets (.env file)
  - Support for managed identity authentication (recommended for production)

### Step 3: Build Core Extraction Modules

#### src/extraction/router.py
- Analyze document type (PDF, DOCX, PNG, JPG)
- Assess document complexity (scanned vs. digital, text density, image quality)
- Route to appropriate extraction method based on configured thresholds
- Return extraction strategy with reasoning
- Reference: Search `microsoft/agent-framework` GitHub for condition/switch-case workflow patterns

#### src/extraction/document_parser.py
- Decode base64 buffer
- Extract text from digital PDFs using PyPDF2 or pypdf
- Extract text from DOCX using python-docx
- Convert images to appropriate format for vision APIs using Pillow
- Handle multi-page documents and aggregate content
- Validate buffer size against configured limits

#### src/extraction/extractor.py
- **LLM-based extraction**: Use Azure AI Foundry gpt-4o with vision capabilities for multimodal processing
- **Azure Document Intelligence**: OCR preprocessing for complex/scanned documents
- Parse extraction results into structured JSON matching data element schemas
- Handle pagination and content aggregation across all pages
- Error handling and retry logic with exponential backoff
- Reference: Search `microsoft/agent-framework` GitHub for multimodal and vision API examples

#### src/extraction/validator.py
- Cross-reference extracted data against original document content
- Use Azure AI Foundry gpt-4o-mini to validate each field
- Assign confidence scores (0-1) per extracted field
- Check required fields against configured minimum threshold
- Return validation result with per-field confidence and overall status

### Step 4: Implement Microsoft Agent Framework Agents

#### src/agents/extractor_agent.py
- Microsoft Agent Framework agent for document extraction
- State management for multi-page document processing
- Coordinate router → parser → extractor pipeline using sequential workflow pattern
- Aggregate results from all pages
- Format output as JSON matching input schema
- Handle errors and validation failures
- Reference: Search `microsoft/agent-framework` GitHub for sequential workflow and fan-out/fan-in patterns

#### src/agents/validator_agent.py
- Microsoft Agent Framework agent for result validation
- Receive extracted data and original document via handoff from extractor agent
- Execute validation logic using validator module
- Track validation state and confidence scores
- Return final validated result or error with details
- Reference: Search `microsoft/agent-framework` GitHub for agent handoff patterns

#### src/agents/orchestrator.py
- Orchestrate multi-agent workflow: Router → Extractor → Validator
- Implement sequential execution with state passing between agents
- Handle workflow errors and retry logic
- Aggregate final results from validator agent
- Reference: Search `microsoft/agent-framework` GitHub for workflow orchestration examples

### Step 5: Create MCP HTTP/WebSocket Server

#### src/interfaces/mcp_server.py
- Implement HTTP/WebSocket server using Python MCP SDK
- Integrate with Microsoft Agent Framework agents
- Expose `extract_document_data` tool with schema:
- Reference: Search `microsoft/agent-framework` GitHub for MCP integration examples
  - **Input**:
    - `documentBase64`: Base64 encoded document buffer
    - `fileType`: Document type (pdf | docx | png | jpg)
    - `dataElements`: Array of extraction schemas
      - `name`: Field name
      - `description`: What to extract
      - `format`: Expected data format (string, number, date, etc.)
      - `required`: Boolean flag
  - **Output**:
    - `success`: Boolean
    - `extractedData`: Object with field names as keys
    - `confidence`: Per-field confidence scores
    - `errors`: Array of error messages if extraction failed

- Wrap extractor and validator agents
- Handle synchronous request/response flow
- Implement timeout and error handling
- Health check endpoint

### Step 6: Create A2A Agent Interface

#### src/interfaces/agent_server.py
- Implement Microsoft Agent Framework distributed runtime server
- Expose asynchronous extraction capabilities
- Agent events/messages:
  - `document.extraction.requested`: Trigger extraction workflow
  - `document.extraction.completed`: Return results
  - `document.extraction.failed`: Report errors
- Enable agent-to-agent communication patterns
- State persistence for long-running operations
- Event-driven orchestration support
- Reference: Search `microsoft/agent-framework` GitHub for distributed agent execution examples

### Step 7: Add Azure Container App Deployment

#### Dockerfile
- Multi-stage build:
  - Stage 1: Install Python dependencies
  - Stage 2: Production runtime with minimal dependencies
- Python 3.11+ base image (official python:3.11-slim)
- Copy requirements.txt and install with `pip install agent-framework-azure-ai --pre`
- Copy application code
- Expose ports 8000 (MCP) and 8001 (A2A)
- Health check configuration
- Non-root user for security

#### .dockerignore
- Exclude .venv, __pycache__, .git, test files, documentation, *.pyc
- Include only necessary files for container build

#### azure-container-app.yaml
- Container App manifest configuration:
  - Container image reference
  - Environment variables for Azure AI Foundry connection string, endpoints
  - Dual HTTP ingress configuration (ports 8000, 8001)
  - Health probes (liveness, readiness)
  - Resource limits (CPU, memory)
  - Auto-scaling rules based on HTTP request rate
  - Managed identity for Azure service authentication (recommended over API keys)

## Data Flow

### MCP Tool Flow (Synchronous)
1. MCP client sends `extract_document_data` request with base64 document and schemas
2. MCP server validates input and buffer size
3. Extractor agent processes document (router → parser → extractor)
4. Validator agent verifies extracted data and assigns confidence scores
5. MCP server returns JSON response with extracted data and confidence scores

### A2A Agent Flow (Asynchronous)
1. Calling agent sends `document.extraction.requested` event
2. Extractor agent receives event and begins processing
3. Multi-page documents processed in parallel where possible
4. Validator agent verifies results asynchronously
5. Extractor agent emits `document.extraction.completed` event with results
6. Calling agent receives event and continues workflow

## Configuration Example

```json
{
  "minConfidenceThreshold": 0.8,
  "maxBufferSizeMB": 10,
  "azureDocumentIntelligence": {
    "endpoint": "https://YOUR_ENDPOINT.cognitiveservices.azure.com/",
    "key": "YOUR_KEY"
  },
  "azureAIFoundry": {
    "projectEndpoint": "https://YOUR_PROJECT.api.azureml.ms",
    "connectionString": "YOUR_CONNECTION_STRING",
    "deployments": {
      "extraction": "gpt-4o",
      "validation": "gpt-4o-mini"
    },
    "useManagedIdentity": true
  },
  "routingThresholds": {
    "useDocumentIntelligence": {
      "scannedDocument": true,
      "lowTextDensity": true,
      "poorImageQuality": true
    }
  },
  "serverPorts": {
    "mcp": 8000,
    "a2a": 8001
  }
}
```

## Usage Examples

### MCP Tool Usage
```json
// From Claude Desktop or MCP client
{
  "tool": "extract_document_data",
  "arguments": {
    "documentBase64": "JVBERi0xLjQK...",
    "fileType": "pdf",
    "dataElements": [
      {
        "name": "invoiceNumber",
        "description": "The invoice number from the document",
        "format": "string",
        "required": true
      },
      {
        "name": "totalAmount",
        "description": "The total amount due",
        "format": "number",
        "required": true
      },
      {
        "name": "dueDate",
        "description": "Payment due date",
        "format": "date",
        "required": false
      }
    ]
  }
}
```

### A2A Agent Usage
```python
# From orchestrating agent using Microsoft Agent Framework
from agent_framework import Agent

# Send extraction request to agent
await agent.send_message(
    'document.extraction.requested',
    {
        'documentBase64': base64_buffer,
        'fileType': 'pdf',
        'dataElements': schemas
    }
)

# Receive results
result = await agent.receive_message('document.extraction.completed')
print(f"Extracted: {result['extractedData']}")
print(f"Confidence: {result['confidence']}")
```

## Deployment

### Local Development
```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies (--pre flag required for Agent Framework preview)
pip install agent-framework-azure-ai --pre
pip install -r requirements.txt

# Run development server
python src/main.py
```

⚠️ **Important**: The `--pre` flag is **required** while Microsoft Agent Framework is in preview.

### Azure Container App Deployment
```bash
# Build container
docker build -t agent-extractor:latest .

# Push to Azure Container Registry
az acr build --registry YOUR_ACR --image agent-extractor:latest .

# Deploy to Container App with managed identity
az containerapp create \
  --name agent-extractor \
  --resource-group YOUR_RG \
  --environment YOUR_ENV \
  --image YOUR_ACR.azurecr.io/agent-extractor:latest \
  --ingress external \
  --target-port 8000 \
  --user-assigned YOUR_MANAGED_IDENTITY_ID \
  --env-vars \
    AZURE_AI_FOUNDRY_ENDPOINT=YOUR_ENDPOINT \
    USE_MANAGED_IDENTITY=true
```

## Future Enhancements
- Support for additional document formats (Excel, TXT, HTML)
- Batch processing for multiple documents
- Streaming results for large documents
- Custom extraction models fine-tuned for specific document types
- Caching layer for repeated extractions
- Audit logging and telemetry
- Multi-language document support
