# Agent Extractor

Document extraction agent using Microsoft Agent Framework with MCP and A2A interfaces for extracting structured data from multi-format documents (PDF, DOCX, images).

## Features

- **Multi-Format Support**: Extract data from PDF, DOCX, PNG, and JPG documents
- **Intelligent Routing**: Automatically routes digital documents to LLMs, reserves vision models for image inputs, and requires Azure Document Intelligence for scanned PDFs
- **Dual Interfaces**: 
  - **MCP Server**: HTTP/WebSocket endpoint for AI assistant integration (Claude Desktop, VS Code)
  - **A2A Agent**: Agent-to-agent communication for orchestrated workflows
- **Multi-Agent Orchestration**: Sequential workflow with Router → Extractor → Validator pattern
- **Confidence Scoring**: Per-field confidence validation with configurable thresholds
- **Production Ready**: Azure Container App deployment with managed identity support

## MVP Limitations (Current Version)

This is the **Minimum Viable Product (MVP)** release with the following limitations:

⚠️ **Document Format**: PDF files only (DOCX, PNG, JPG support coming in production phase)
⚠️ **Page Support**: Single-page PDFs only (multi-page aggregation coming later)
⚠️ **Extraction Method**: Text-only extraction with gpt-4o (no vision or Document Intelligence yet)
⚠️ **Validation**: No confidence scoring or validation agent (coming in Phase 9)
⚠️ **Interface**: HTTP-only MCP server (WebSocket and A2A agent coming in Phase 12)
⚠️ **Error Handling**: Basic error messages (enhanced retry logic and detailed errors coming in Phase 10)

See [AGENTS.md](AGENTS.md) for the full roadmap to production.

## Technology Stack

- **Python 3.11+** with Microsoft Agent Framework
- **Azure AI Foundry**: Production models (gpt-4o, gpt-4o-mini)
- **Azure Document Intelligence**: OCR for complex/scanned documents
- **FastAPI**: HTTP/WebSocket server for MCP
- **Pydantic**: Type-safe configuration and validation

## Prerequisites

### Azure Resources
1. **Azure AI Foundry Project** with deployed models:
   - `gpt-4o` (extraction with vision capabilities)
   - `gpt-4o-mini` (validation and confidence scoring)
2. **Azure Document Intelligence** resource
3. **Entra ID Authentication**:
   - Local development: `az login` for user authentication
   - Production: Managed identity for secure service-to-service authentication

### Development Tools
- Python 3.11 or higher
- Azure CLI (for deployment)
- VS Code with Azure AI Foundry extension (optional)

## Installation

### 1. Clone Repository
```bash
git clone https://github.com/nabeelp/agent-extractor.git
cd agent-extractor
```

### 2. Install Dependencies with uv

⚠️ **IMPORTANT**: The `--pre` flag is **required** while Microsoft Agent Framework is in preview.

```bash
# Install uv if not already installed
pip install uv

# Sync dependencies (creates venv automatically)
uv sync

# Install server extras (FastAPI/uvicorn) if you plan to run the MCP server
uv pip install -e ".[server]"

# Install pre-commit hooks for lint/type/test gates
uv pip install pre-commit
pre-commit install

# Install Agent Framework with --pre flag
uv pip install agent-framework-azure-ai --pre
```

**Note**: `uv` automatically creates and manages the virtual environment in `.venv/`

### 3. Authenticate with Azure

```bash
# Login to Azure with Entra ID (Azure AD)
az login

# Optional: Set specific tenant if you have multiple
az login --tenant YOUR_TENANT_ID
```

### 4. Configure Environment

Create a `.env` file in the project root (optional - most settings in `config.json`):

```env
# Authentication: Uses Entra ID (Azure AD) via DefaultAzureCredential
# Local: Ensure you've run 'az login'
# Production: Managed identity configured in Azure Container Apps

# Optional: Specify tenant ID if using multiple tenants
# AZURE_TENANT_ID=your_tenant_id

# Optional: Override config.json values
# MCP_SERVER_PORT=8000
# MIN_CONFIDENCE_THRESHOLD=0.8
# MAX_BUFFER_SIZE_MB=10
```

Edit `config.json` to set your Azure AI Foundry endpoint and model deployment names.

**Note**: This solution uses **Entra ID authentication** (no API keys required). Ensure you have appropriate Azure RBAC permissions on the AI Foundry project.

## Usage

### Running the Server

```bash
# Start MCP HTTP server
uv run python src/main.py

# Server starts on http://localhost:8000
# Health check: http://localhost:8000/health
# API docs: http://localhost:8000/docs
```

### Quick Test with REST Client

1. Install REST Client extension in VS Code: `humao.rest-client`
2. Open `test.http` file
3. Click "Send Request" above any request
4. View response in split pane

See [test.http](test.http) for examples.

### Testing with curl

```bash
# Health check
curl http://localhost:8000/health

# Extract data (replace with your base64-encoded PDF)
curl -X POST http://localhost:8000/extract_document_data \
  -H "Content-Type: application/json" \
  -d '{
    "documentBase64": "JVBERi0xLjQK...",
    "fileType": "pdf",
    "dataElements": [
      {
        "name": "invoiceNumber",
        "description": "The invoice number",
        "format": "string",
        "required": true
      }
    ]
  }'
```

### Testing with PowerShell

```powershell
# Convert PDF to base64
$base64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("invoice.pdf"))

# Extract data
$body = @{
    documentBase64 = $base64
    fileType = "pdf"
    dataElements = @(
        @{
            name = "invoiceNumber"
            description = "The invoice number"
            format = "string"
            required = $true
        }
    )
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Uri http://localhost:8000/extract_document_data `
    -Method Post -Body $body -ContentType "application/json"
```

### Response Format

**Success:**
```json
{
  "success": true,
  "extractedData": {
    "invoiceNumber": "INV-12345",
    "totalAmount": 1500.00
  },
  "errors": null
}
```

**Failure:**
```json
{
  "success": false,
  "extractedData": {},
  "errors": ["Required field 'invoiceNumber' not found in document"],
  "metadata": {
    "extraction_method": "llm_text",
    "routing_reasoning": "Digital PDF with extractable text",
    "document_type": "pdf"
  }
}
```

### Error Responses

When the server returns an HTTP error (4xx/5xx), the response body now includes a
`metadata` object containing routing and extraction context whenever it is
available. This matches the metadata provided in successful responses and helps
diagnose failures without digging through server logs.

## Configuration

Edit `config.json` to customize:

- `azureAIFoundry.projectEndpoint`: Your Azure AI Foundry project endpoint
- `azureAIFoundry.extractionModel`: Model deployment name (default: gpt-4o)
- `serverPorts.mcp`: MCP server port (default: 8000)
- `minConfidenceThreshold`: Minimum confidence for required fields (default: 0.8)
- `maxBufferSizeMB`: Maximum document size in MB (default: 10)
- `prompts.extraction`: System prompt for data extraction (customizable)

See [config.json](config.json) and [AGENTS.md](AGENTS.md) for details.

## Troubleshooting

### Server won't start

**Problem**: `ValueError: Required environment variable missing` or `FileNotFoundError: Configuration file not found`

**Solution**:
1. Ensure `config.json` exists in the project root
2. Run `az login` to authenticate with Azure
3. Verify your Azure AI Foundry endpoint in `config.json`

### "Required field not found" error

**Problem**: Extraction succeeds but returns error for required field

**Solution**:
1. Check that the PDF contains the data you're looking for
2. Make the field `required: false` for testing
3. Improve the field `description` to be more specific
4. Verify the PDF has extractable text; scanned PDFs now require Azure Document Intelligence configuration

### "Unsupported file type" error

**Problem**: `ValueError: Unsupported file type: docx. MVP only supports PDF.`

**Solution**: MVP only supports PDF files. DOCX, PNG, JPG support coming in Phase 8. Convert your document to PDF for now.

### "No text could be extracted" error

**Problem**: PDF appears blank or has no extractable text

**Solution**:
1. Verify the PDF is not password-protected
2. Check if the PDF is a scanned image (these now require Azure Document Intelligence; there is no vision-model fallback)
3. Try opening the PDF and checking if text is selectable
4. MVP only supports first page - ensure data is on page 1

### Authentication errors

**Problem**: `DefaultAzureCredential` authentication fails

**Solution**:
1. Run `az login` to authenticate
2. If using multiple tenants, set `AZURE_TENANT_ID` in `.env`
3. Verify you have appropriate RBAC permissions:
   - `Cognitive Services OpenAI User` on AI Foundry project
   - Or `Cognitive Services Contributor`

### Connection timeout or slow responses

**Problem**: Requests take very long or timeout

**Solution**:
1. Check your internet connection to Azure
2. Verify Azure AI Foundry endpoint is correct
3. Check Azure service health status
4. Large documents may take longer (MVP has 10MB limit)

### Need more help?

1. Check [AGENTS.md](AGENTS.md) for architecture details
2. Review [test.http](test.http) for working examples
3. Check server logs (printed to console) for detailed error messages
4. Open an issue on GitHub with error details and logs

## Project Structure

```
agent-extractor/
├── src/
│   ├── config/          # Configuration management
│   ├── extraction/      # Core extraction modules
│   │   ├── router.py
│   │   ├── document_parser.py
│   │   ├── extractor.py
│   │   └── validator.py
│   ├── agents/          # Agent Framework agents
│   │   ├── extractor_agent.py
│   │   ├── validator_agent.py
│   │   └── orchestrator.py
│   └── interfaces/      # MCP and A2A servers
│       ├── mcp_server.py
│       └── agent_server.py
├── tests/               # Unit and integration tests
├── config.json          # Default configuration
├── requirements.txt     # Python dependencies
└── pyproject.toml       # Project metadata
```

## Development

### Pre-commit Hooks

```bash
# Install the hook runner once
uv pip install pre-commit

# Register hooks (ruff, mypy, pytest) for this repo
pre-commit install

# Optional: run across the entire tree
pre-commit run --all-files
```

> **Why it matters:** the hooks wrap `ruff`, `mypy`, and
> `uv run pytest --maxfail=1`, catching style, type, and async
> orchestration regressions before they land in CI.

### Running Tests

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=src

# Focus on the async orchestrator workflow
uv run pytest tests/test_orchestrator_async.py -v
```

### Code Formatting

```bash
# Format code
uv run black src/ tests/

# Lint
uv run ruff check src/ tests/

# Type checking
uv run mypy src/
```

## Deployment

### Docker

```bash
# Build image
docker build -t agent-extractor:latest .

# Run container
docker run -p 8000:8000 -p 8001:8001 \
  --env-file .env \
  agent-extractor:latest

> **Note:** The FastAPI/uvicorn stack now lives in the optional `server` extra. Make
> sure you install with `pip install -e .[server]` (or `uv pip install -e .[server]`)
> before running `python src/main.py` locally.
```

### Azure Container Apps

```bash
# Push to Azure Container Registry
az acr build --registry YOUR_ACR --image agent-extractor:latest .

# Deploy with managed identity for Entra ID authentication
az containerapp create \
  --name agent-extractor \
  --resource-group YOUR_RG \
  --environment YOUR_ENV \
  --image YOUR_ACR.azurecr.io/agent-extractor:latest \
  --ingress external \
  --target-port 8000 \
  --user-assigned YOUR_MANAGED_IDENTITY_ID
```

See [AGENTS.md](AGENTS.md) for detailed deployment instructions.

## Architecture

### Multi-Agent Orchestration

**Sequential Workflow with Handoff Pattern:**
1. **Router Agent** → Analyzes document and selects extraction strategy
2. **Extractor Agent** → Processes document using selected method
3. **Validator Agent** → Verifies results and assigns confidence scores
4. Results aggregated and returned to caller

### Model Selection

- **gpt-4o**: Primary extraction with vision capabilities for multimodal processing
- **gpt-4o-mini**: Lightweight validation for cost-effective confidence scoring

See [AGENTS.md](AGENTS.md) for complete architecture documentation.

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -am 'Add new feature'`
4. Push to the branch: `git push origin feature/your-feature`
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Resources

- [Microsoft Agent Framework GitHub](https://github.com/microsoft/agent-framework)
- [Azure AI Foundry Documentation](https://learn.microsoft.com/azure/ai-foundry/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Azure Document Intelligence](https://learn.microsoft.com/azure/ai-services/document-intelligence/)

## Support

For issues and questions:
- Open an issue on [GitHub](https://github.com/nabeelp/agent-extractor/issues)
- Review [AGENTS.md](AGENTS.md) for detailed documentation
