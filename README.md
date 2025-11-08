# Agent Extractor

Document extraction agent using Microsoft Agent Framework with MCP and A2A interfaces for extracting structured data from multi-format documents (PDF, DOCX, images).

## Features

- **Multi-Format Support**: Extract data from PDF, DOCX, PNG, and JPG documents
- **Intelligent Routing**: Automatically selects optimal extraction method (LLM vision or Azure Document Intelligence)
- **Dual Interfaces**: 
  - **MCP Server**: HTTP/WebSocket endpoint for AI assistant integration (Claude Desktop, VS Code)
  - **A2A Agent**: Agent-to-agent communication for orchestrated workflows
- **Multi-Agent Orchestration**: Sequential workflow with Router → Extractor → Validator pattern
- **Confidence Scoring**: Per-field confidence validation with configurable thresholds
- **Production Ready**: Azure Container App deployment with managed identity support

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
3. **Managed Identity** (recommended for production)

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

# Install Agent Framework with --pre flag
uv pip install agent-framework-azure-ai --pre
```

**Note**: `uv` automatically creates and manages the virtual environment in `.venv/`

### 4. Configure Environment

Create a `.env` file in the project root:

```env
# Azure AI Foundry
AZURE_AI_FOUNDRY_PROJECT_ENDPOINT=https://YOUR_PROJECT.api.azureml.ms
AZURE_AI_FOUNDRY_CONNECTION_STRING=YOUR_CONNECTION_STRING
AZURE_AI_FOUNDRY_EXTRACTION_MODEL=gpt-4o
AZURE_AI_FOUNDRY_VALIDATION_MODEL=gpt-4o-mini

# Azure Document Intelligence
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://YOUR_ENDPOINT.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=YOUR_KEY

# Authentication (optional - use managed identity in production)
USE_MANAGED_IDENTITY=false

# Server Configuration
MCP_SERVER_PORT=8000
A2A_SERVER_PORT=8001
MIN_CONFIDENCE_THRESHOLD=0.8
MAX_BUFFER_SIZE_MB=10
```

Alternatively, copy and edit `config.json` for default values.

## Usage

### Running Locally

```bash
# Start both MCP and A2A servers
uv run python src/main.py

# MCP server: http://localhost:8000
# A2A server: http://localhost:8001
```

### MCP Tool Usage

From Claude Desktop or any MCP client:

```json
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
      }
    ]
  }
}
```

### A2A Agent Usage

```python
from agent_framework import Agent

# Send extraction request
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

## Configuration

Edit `config.json` to customize:

- `minConfidenceThreshold`: Minimum confidence score for required fields (default: 0.8)
- `maxBufferSizeMB`: Maximum document size in MB (default: 10)
- `routingThresholds`: Criteria for selecting extraction method
- `serverPorts`: MCP and A2A server ports

See [AGENTS.md](AGENTS.md) for detailed configuration options.

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

### Running Tests

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=src
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
```

### Azure Container Apps

```bash
# Push to Azure Container Registry
az acr build --registry YOUR_ACR --image agent-extractor:latest .

# Deploy with managed identity
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
