"""Document extraction agent using Microsoft Agent Framework."""

import base64
import logging
from typing import Any, Callable, Dict, List, Optional

from ..config.settings import Settings
from ..extraction.document_parser import DocumentContext, parse_document, parse_image_document
from ..extraction.extractor import Extractor
from ..extraction.router import (
    DocumentRouter,
    ExtractionMethod,
    RoutingDecision,
)


log = logging.getLogger(__name__)


StrategyFn = Callable[[DocumentContext, List[Dict[str, Any]], Dict[str, Any]], Dict[str, Any]]


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
            use_di_for_scanned=self.settings.routing_thresholds.use_document_intelligence.scanned_document,
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
            try:
                document_bytes = base64.b64decode(document_base64)
            except (base64.binascii.Error, ValueError) as exc:
                raise ValueError(f"Invalid base64 document payload: {exc}") from exc

            log.info(
                "Starting extraction | type=%s | elements=%s",
                file_type,
                len(data_elements),
            )

            # Step 1: Route document to select extraction method
            doc_context = DocumentContext(
                file_type=file_type,
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
            extracted_data, document_content = await self._execute_extraction(
                doc_context,
                method,
                data_elements,
                doc_metadata,
            )
            
            # Step 4: Return results with metadata and document content for handoff
            log.info("Extraction completed successfully")
            return ExtractionResult(
                success=True,
                data=extracted_data,
                metadata={
                    "extraction_method": method.value,
                    "document_type": doc_type.value,
                    "routing_reasoning": reasoning,
                    **doc_metadata
                },
                document_content=document_content,  # Preserve for validation handoff
            )
            
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
    ) -> tuple[Dict[str, Any], Optional[str]]:
        """Execute extraction using the selected method.
        
        Args:
            context: Shared document context
            method: Selected extraction method
            data_elements: Data elements to extract
            doc_metadata: Document metadata from routing
            
        Returns:
            Tuple of (extracted_data, document_content) for validation handoff
            
        Raises:
            ValueError: If extraction fails
        """
        # Lookup the handler for the chosen method. This keeps branching logic out of the
        # main workflow and makes it easy to plug in new strategies later.
        strategy = self._strategies.get(method)
        if strategy is None:
            raise ValueError(f"Unsupported extraction method: {method}")

        extracted_data = await strategy(
            context,
            data_elements,
            doc_metadata,
        )
        
        # Get document content for validation (if available)
        document_content = self._get_document_content(context, method)
        
        return extracted_data, document_content

    async def _extract_with_text(
        self,
        context: DocumentContext,
        data_elements: List[Dict[str, Any]],
        _: Dict[str, Any],
    ) -> Dict[str, Any]:
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
    ) -> Dict[str, Any]:
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
    ) -> Dict[str, Any]:
        # Hand off to the Document Intelligence + LLM flow when OCR preprocessing is needed.
        return await self.extractor.extract(
            text=None,
            data_elements=data_elements,
            document_base64=context.base64_data,
            use_document_intelligence=True,
        )
    
    def _get_document_content(
        self,
        context: DocumentContext,
        method: ExtractionMethod,
    ) -> Optional[str]:
        """Get document content for validation handoff.
        
        Args:
            context: Document context
            method: Extraction method used
            
        Returns:
            Document text content if available, None otherwise
        """
        try:
            # For text-based methods, parse and return the content
            if method in [ExtractionMethod.LLM_TEXT, ExtractionMethod.DOCUMENT_INTELLIGENCE]:
                if context.file_type in ["pdf", "docx"]:
                    return parse_document(context, all_pages=True)
            
            # For vision methods with images, return a placeholder
            # (validator will use the original document if needed)
            return None
            
        except Exception as exc:
            log.warning("Failed to get document content for handoff: %s", exc)
            return None


def create_extractor_agent(settings: Settings) -> ExtractorAgent:
    """Factory function to create an extractor agent.
    
    Args:
        settings: Application settings
        
    Returns:
        ExtractorAgent instance
    """
    return ExtractorAgent(settings)
