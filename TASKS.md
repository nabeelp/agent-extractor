# TASKS

Detailed engineering tasks derived from the latest code-quality review. Each item below covers recommendations **not** already planned in `AGENTS.md`.

## 1. Request & Validation Hardening
- **Early file-type and payload validation**
  - Normalize and validate `file_type` plus base64 payload length inside `ExtractorAgent.extract_from_document` before routing begins.
  - Return structured `UnsupportedFileTypeError`/`Base64DecodingError` immediately so FastAPI can surface clean 4xx errors.
  - Add unit tests covering invalid types, lowercase/uppercase variants, and malformed base64 strings.
- **Validator failure semantics**
  - Update `Validator.validate` to treat empty `data_elements` or zero confidence scores as a failed validation with a descriptive error.
  - Ensure orchestrator propagates the failure and surfaces a 4xx with actionable messaging.

## 2. Async Resource Lifecycle
- **Share OpenAI clients with graceful shutdown**
  - Move `AsyncAzureOpenAI`/`OpenAIChatClient` creation into an app-level singleton (e.g., FastAPI lifespan manager) so the async session is reused across requests.
  - Expose an `aclose()` hook and call it on shutdown to prevent hanging sockets when the server restarts.
- **Adopt async Document Intelligence client**
  - Switch to `azure.ai.formrecognizer.aio.DocumentAnalysisClient` (or wrap sync calls inside `anyio.to_thread.run_sync`) so DI preprocessing no longer blocks the event loop.
  - Update `Extractor.extract_with_document_intelligence` to `await` the async poller and add tests to confirm concurrency.

## 3. Extraction Workflow Improvements
- **Preserve parsed document content once**
  - Capture the parsed text/image/OCR output inside each extraction strategy and store it on `ExtractionResult.document_content` instead of reparsing in `_get_document_content_for_validation`.
  - Remove the fallback reparse logic and ensure validator handoff always receives consistent content, even for vision/DI flows.
- **Correct strategy typing**
  - Change `StrategyFn` to `Callable[..., Awaitable[Dict[str, Any]]]` and add the necessary `Awaitable` import.
  - Run `mypy` to verify the async strategies conform and adjust call sites accordingly.

## 4. Error Reporting & Observability
- **Return orchestration metadata with failures**
  - Extend `map_exception_to_http_error` (and the orchestrator response model) to include routing/extraction metadata when errors occur.
  - Document the error schema in `README.md` so MCP consumers can inspect routing choices without server logs.

## 5. Dependency Hygiene
- **Remove duplicate PDF dependency**
  - Pick either `PyPDF2` or `pypdf`, update `pyproject.toml` and `requirements.txt`, and run `uv sync` to refresh the lockfile.
- **Pin preview Agent Framework**
  - Add an explicit version constraint for `agent-framework-azure-ai` (e.g., `==<current-preview>` with a comment about updating when GA lands) to make builds reproducible.
- **Split optional server extras**
  - Move FastAPI/uvicorn/websocket packages into an extras group (e.g., `server`) so library consumers can install the core extraction stack without web dependencies.
  - Update the README with installation instructions for the new extra.

## 6. Testing & Tooling Enhancements
- **Async integration harness**
  - Introduce `pytest-asyncio` tests that stub OpenAI/DI clients to verify extractor↔validator flows without hitting Azure services.
  - Cover success, validation failure, and DI fallback scenarios to catch regressions in orchestration behavior.
- **Pre-commit/static analysis gate**
  - Add a `.pre-commit-config.yaml` that runs `ruff`, `mypy`, and `pytest --maxfail=1`.
  - Document the workflow in `README.md` and wire it into CI so pull requests fail fast on lint/type/test regressions.
