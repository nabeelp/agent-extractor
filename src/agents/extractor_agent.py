"""Document extraction agent using Microsoft Agent Framework."""

import base64
import binascii
import logging
from typing import Any, Awaitable, Callable, ClassVar, Dict, List, Optional

from ..config.settings import Settings
from ..exceptions import Base64DecodingError, DocumentRoutingError, UnsupportedFileTypeError
from ..extraction.document_parser import DocumentContext, parse_document, parse_image_document
from ..extraction.extractor import Extractor, ExtractionPayload
from ..extraction.router import (
    DocumentRouter,
    ExtractionMethod,
    RoutingDecision,
)


log = logging.getLogger(__name__)


StrategyFn = Callable[[DocumentContext, List[Dict[str, Any]], Dict[str, Any]], Awaitable[ExtractionPayload]]


class ExtractionResult:
    """Result from document extraction."""
    
    def __init__(
        self,
        success: bool,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        document_content: Optional[str] = None,
    ):
        """Initialize extraction result.
        
        Args:
            success: Whether extraction succeeded
            data: Extracted data dictionary (if successful)
            error: Error message (if failed)
            metadata: Additional metadata about extraction process
            document_content: Original document text content (for validation handoff)
        """
        self.success = success
        self.data = data or {}
        self.error = error
        self.metadata = metadata or {}
        self.document_content = document_content
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary.
        
        Returns:
            Dictionary representation of result
        """
        result = {
            "success": self.success,
            "extractedData": self.data
        }
        
        if self.error:
            result["errors"] = [self.error]
        
        if self.metadata:
            result["metadata"] = self.metadata
        
        return result


class ExtractorAgent:
    """Agent for extracting structured data from multi-format documents.
    
    This agent coordinates:
    1. Document routing (selecting optimal extraction method)
    2. Document parsing (text/image extraction)
    3. Data extraction (LLM-based or Document Intelligence)
    """
    
    SUPPORTED_FILE_TYPES: ClassVar[set[str]] = {"pdf", "docx", "png", "jpg", "jpeg"}

    def __init__(self, settings: Settings):
        """Initialize extractor agent.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        self.extractor = Extractor(settings)
        self.has_document_intelligence = (
            settings.azure_document_intelligence is not None and
            settings.azure_document_intelligence.endpoint is not None
        )
        self.router = DocumentRouter(
            use_document_intelligence=self.has_document_intelligence,
            text_density_threshold=self.settings.routing_thresholds.text_density_threshold,
            low_resolution_threshold=self.settings.routing_thresholds.low_resolution_threshold,
            use_di_for_low_text=self.settings.routing_thresholds.use_document_intelligence.low_text_density,
            use_di_for_poor_quality=self.settings.routing_thresholds.use_document_intelligence.poor_image_quality,
        )
        # Map each extraction method to the handler that knows how to execute it.
        self._strategies: Dict[ExtractionMethod, StrategyFn] = {
            ExtractionMethod.LLM_TEXT: self._extract_with_text,
            ExtractionMethod.LLM_VISION: self._extract_with_vision,
            ExtractionMethod.DOCUMENT_INTELLIGENCE: self._extract_with_document_intelligence,
        }
        log.info(
            "Extractor agent initialised | model=%s | document_intelligence=%s",
            settings.extraction_model,
            self.has_document_intelligence,
        )
    
    async def aclose(self) -> None:
        """Release underlying extractor resources."""
        await self.extractor.aclose()

    @classmethod
    def normalize_file_type(cls, file_type: str) -> str:
        """Normalize and validate the supplied file type string."""
        if file_type is None:
            raise UnsupportedFileTypeError("", sorted(cls.SUPPORTED_FILE_TYPES))

        normalized = file_type.strip().lower()
        if not normalized:
            raise UnsupportedFileTypeError(normalized, sorted(cls.SUPPORTED_FILE_TYPES))

        if normalized not in cls.SUPPORTED_FILE_TYPES:
            raise UnsupportedFileTypeError(normalized, sorted(cls.SUPPORTED_FILE_TYPES))

        return normalized

    @staticmethod
    def decode_document_payload(document_base64: str) -> bytes:
        """Decode a base64 document payload with validation."""
        if not document_base64 or not document_base64.strip():
            raise Base64DecodingError("Document payload is empty")

        try:
            decoded = base64.b64decode(document_base64, validate=True)
        except (binascii.Error, ValueError) as exc:  # pragma: no cover - defensive
            raise Base64DecodingError(f"Invalid base64 document payload: {exc}") from exc

        if not decoded:
            raise Base64DecodingError("Document payload decoded to zero bytes")

        return decoded

    async def extract_from_document(
        self,
        document_base64: str,
        file_type: str,
        data_elements: List[Dict[str, Any]]
    ) -> ExtractionResult:
        """Extract data from a document using intelligent routing.
        
        Workflow:
        1. Route document (analyze and select extraction method)
        2. Parse document (text or image extraction)
        3. Extract data using selected method
        4. Return results with metadata
        
        Args:
            document_base64: Base64 encoded document
            file_type: Document type (pdf, docx, png, jpg, jpeg)
            data_elements: List of data elements to extract
            
        Returns:
            ExtractionResult with extracted data or error
        """
        try:
            normalized_type = self.normalize_file_type(file_type)
            document_bytes = self.decode_document_payload(document_base64)

            log.info(
                "Starting extraction | type=%s | elements=%s",
                normalized_type,
                len(data_elements),
            )

            # Step 1: Route document to select extraction method
            doc_context = DocumentContext(
                file_type=normalized_type,
                base64_data=document_base64,
                raw_bytes=document_bytes,
            )

            routing_decision: RoutingDecision = self.router.analyze_and_route(doc_context)
            method = routing_decision.method
            doc_type = routing_decision.doc_type
            reasoning = routing_decision.reasoning
            doc_metadata = routing_decision.metadata
            
            log.info(
                "Routing decision | method=%s | reasoning=%s",
                method.value,
                reasoning,
            )
            
            # Step 2 & 3: Parse and extract based on selected method
            payload = await self._execute_extraction(
                doc_context,
                method,
                data_elements,
                doc_metadata,
            )
            
            # Step 4: Return results with metadata and document content for handoff
            log.info("Extraction completed successfully")
            return ExtractionResult(
                success=True,
                data=payload.data,
                metadata={
                    "extraction_method": method.value,
                    "document_type": doc_type.value,
                    "routing_reasoning": reasoning,
                    **doc_metadata
                },
                document_content=payload.document_content,
            )
            
        except (UnsupportedFileTypeError, Base64DecodingError):
            raise
        except DocumentRoutingError as exc:
            log.warning("Routing failed | error=%s", exc)
            return ExtractionResult(success=False, error=str(exc))
        except ValueError as exc:
            log.warning("Extraction failed | error=%s", exc)
            return ExtractionResult(success=False, error=str(exc))

        except Exception as exc:  # pragma: no cover - defensive failure path
            log.exception("Unexpected error during extraction")
            return ExtractionResult(success=False, error=f"Unexpected error: {exc}")
    
    async def _execute_extraction(
        self,
        context: DocumentContext,
        method: ExtractionMethod,
        data_elements: List[Dict[str, Any]],
        doc_metadata: Dict[str, Any],
    ) -> ExtractionPayload:
        """Execute extraction using the selected method."""
        # Lookup the handler for the chosen method. This keeps branching logic out of the
        # main workflow and makes it easy to plug in new strategies later.
        strategy = self._strategies.get(method)
        if strategy is None:
            raise ValueError(f"Unsupported extraction method: {method}")

        return await strategy(
            context,
            data_elements,
            doc_metadata,
        )

    async def _extract_with_text(
        self,
        context: DocumentContext,
        data_elements: List[Dict[str, Any]],
        _: Dict[str, Any],
    ) -> ExtractionPayload:
        # Decode text-first documents and run the text-only extraction pipeline.
        text = parse_document(context, all_pages=True)
        log.debug("Parsed text document | chars=%s", len(text))

        return await self.extractor.extract(
            text=text,
            data_elements=data_elements,
        )

    async def _extract_with_vision(
        self,
        context: DocumentContext,
        data_elements: List[Dict[str, Any]],
        _: Dict[str, Any],
    ) -> ExtractionPayload:
        # Prepare image or PDF content for the vision-capable model before extraction.
        if context.file_type == "pdf":
            document_data = {
                "base64_data": context.base64_data,
                "media_type": "application/pdf",
                "document_type": "pdf",
            }
        else:
            document_data = parse_image_document(context)
            log.debug(
                "Parsed image metadata | width=%s | height=%s",
                document_data.get("width"),
                document_data.get("height"),
            )

        return await self.extractor.extract(
            text=None,
            data_elements=data_elements,
            image_data=document_data,
        )
    
    async def _extract_with_document_intelligence(
        self,
        context: DocumentContext,
        data_elements: List[Dict[str, Any]],
        _metadata: Dict[str, Any],
    ) -> ExtractionPayload:
        # Hand off to the Document Intelligence + LLM flow when OCR preprocessing is needed.
        return await self.extractor.extract(
            text=None,
            data_elements=data_elements,
            document_base64=context.base64_data,
            use_document_intelligence=True,
        )


def create_extractor_agent(settings: Settings) -> ExtractorAgent:
    """Factory function to create an extractor agent.
    
    Args:
        settings: Application settings
        
    Returns:
        ExtractorAgent instance
    """
    return ExtractorAgent(settings)
