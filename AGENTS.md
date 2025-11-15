# Agent Blueprint: Document Extraction with Confidence

## Mission
Deliver a Microsoft Agent Framework (Python) solution that ingests a single document plus an explicit list of fields, classifies the document, locks an extraction strategy (LLM, Azure Document Intelligence, or hybrid), extracts each requested field with provenance, and returns both value and confidence per field via MCP and A2A interfaces.

## Golden Workflow (Immutable Sequence)
1. **Intake** – Validate the envelope contains `documentBase64` and non-empty `dataElements` (each with name, description, format, required flag). Reject otherwise.
2. **Classification** – Detect file type (PDF, scanned PDF, DOCX, PNG, JPG, etc.), scan/digital status, and quality flags. Persist this metadata.
3. **Strategy Lock** – Choose LLM, Azure Document Intelligence, or hybrid based on classification. Record rationale; no silent fallbacks unless a hard failure triggers a logged retry.
4. **Evidence Extraction** – For every requested field, capture the matching snippet/page/bounding box using the locked strategy.
5. **Confidence Validation** – Run the validator (gpt-4o-mini via Azure AI Foundry) to assign a 0–1 confidence and reason code per field; enforce minimum thresholds for required fields.
6. **Response Assembly** – Return a deterministic payload with `documentType`, `extractionStrategy`, `extractedData`, `confidencePerField`, provenance metadata, and any failure diagnostics.

## Non-Negotiable Requirements
- **Input Contract**: No processing without both payload elements. Log actionable errors.
- **Document Awareness**: Downstream modules consume the persisted type/quality metadata; reruns reuse it.
- **Strategy Traceability**: Router decisions surface in logs and responses.
- **Per-Field Provenance**: Each value references the originating evidence (page, bbox, snippet text).
- **Confidence Gate**: Required fields below threshold trigger validation failure, not low-quality output.
- **Deterministic Schema**: Response shape never changes and is shared across MCP + A2A.
- **Phase Diagnostics**: Failures identify the exact phase (routing, parsing, extraction, validation) plus remediation guidance.

## Component Responsibilities
### Router (`src/extraction/router.py`)
- Inspect type, scan status, density, and quality to pick the extraction path.
- Force scanned PDFs through Azure Document Intelligence; raise routing error if unavailable.
- Emit immutable decision record (strategy, rationale, timestamps).

### Document Parser (`src/extraction/document_parser.py`)
- Decode base64, enforce buffer limits, and normalize formats (PDF text via `pypdf`, DOCX via `python-docx`, images via Pillow).
- Validate `dataElements` structure and alignment with document boundaries before passing work downstream.

### Extractor (`src/extraction/extractor.py`)
- Invoke Azure AI Foundry gpt-4o for text-first or image documents; integrate Document Intelligence output for scanned PDFs prior to LLM reasoning.
- Produce structured field candidates with provenance metadata per request item.
- Never emit a field lacking concrete evidence.

### Validator (`src/extraction/validator.py`)
- Use gpt-4o-mini to verify each extracted field against source evidence.
- Assign confidence scores, reasons, and pass/fail status aligned with configured thresholds.
- Surface remediation notes when confidence is insufficient.

### Agents & Orchestration
- **Extractor Agent** – Runs router → parser → extractor chain, aggregates multi-page results, enforces provenance.
- **Validator Agent** – Scores each field, rejects failures, and emits per-field diagnostics.
- **Orchestrator** – Guarantees the golden workflow executes once per request, with retries only after logged hard failures; passes along metadata to both MCP and A2A layers.

## Interface Contracts
### MCP Tool `extract_document_data`
- **Input**: `{ documentBase64, fileType, dataElements[] }`.
- **Output**: `{ success, documentType, extractionStrategy, extractedData, confidencePerField, provenance, errors[] }`.
- Enforce timeouts, size limits, and structured error responses.

### A2A Events
- `document.extraction.requested` – carries the same envelope as MCP.
- `document.extraction.completed` – mirrors MCP output schema.
- `document.extraction.failed` – reports phase + remediation guidance.

## Implementation Checklist
- Dependencies: `agent-framework-azure-ai --pre`, `@modelcontextprotocol/sdk` (Python), `azure-ai-formrecognizer`, `pypdf`, `python-docx`, `Pillow`, `python-dotenv`.
- Configuration: load all secrets/endpoints via `.env` into `src/config/settings.py`; include min confidence, buffer limit, routing thresholds, MCP/A2A ports.
- Deployment: package for Azure Container Apps (python:3.11-slim, uv/`pip install agent-framework-azure-ai --pre`, exposed ports 8000/8001, managed identity auth).
- Observability: capture router decisions, validator outcomes, and per-field status in logs to satisfy traceability requirements.
