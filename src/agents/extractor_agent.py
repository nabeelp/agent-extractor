"""Document extraction agent using Microsoft Agent Framework."""

import base64
import logging
from typing import Any, Callable, Dict, List, Optional

from ..config.settings import Settings
from ..extraction.document_parser import parse_document, parse_image_document
from ..extraction.extractor import Extractor
from ..extraction.router import ExtractionMethod, route_document


log = logging.getLogger(__name__)


StrategyFn = Callable[[str, str, List[Dict[str, Any]], Dict[str, Any], Optional[bytes]], Dict[str, Any]]


class ExtractionResult:
    """Result from document extraction."""
    
    def __init__(
        self,
        success: bool,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Initialize extraction result.
        
        Args:
            success: Whether extraction succeeded
            data: Extracted data dictionary (if successful)
            error: Error message (if failed)
            metadata: Additional metadata about extraction process
        """
        self.success = success
        self.data = data or {}
        self.error = error
        self.metadata = metadata or {}
    
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
    
    def extract_from_document(
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
            routing_result = route_document(
                document_base64,
                file_type,
                document_bytes=document_bytes,
                use_document_intelligence=self.has_document_intelligence,
                text_density_threshold=self.settings.routing_thresholds.text_density_threshold,
                low_resolution_threshold=self.settings.routing_thresholds.low_resolution_threshold,
                use_di_for_scanned=self.settings.routing_thresholds.use_document_intelligence.scanned_document,
                use_di_for_low_text=self.settings.routing_thresholds.use_document_intelligence.low_text_density,
                use_di_for_poor_quality=self.settings.routing_thresholds.use_document_intelligence.poor_image_quality
            )
            
            method = routing_result["method"]
            doc_type = routing_result["doc_type"]
            reasoning = routing_result["reasoning"]
            doc_metadata = routing_result["metadata"]
            
            log.info(
                "Routing decision | method=%s | reasoning=%s",
                method.value,
                reasoning,
            )
            
            # Step 2 & 3: Parse and extract based on selected method
            extracted_data = self._execute_extraction(
                document_base64,
                file_type,
                method,
                data_elements,
                doc_metadata,
                document_bytes,
            )
            
            # Step 4: Return results with metadata
            log.info("Extraction completed successfully")
            return ExtractionResult(
                success=True,
                data=extracted_data,
                metadata={
                    "extraction_method": method.value,
                    "document_type": doc_type.value,
                    "routing_reasoning": reasoning,
                    **doc_metadata
                }
            )
            
        except ValueError as exc:
            log.warning("Extraction failed | error=%s", exc)
            return ExtractionResult(success=False, error=str(exc))

        except Exception as exc:  # pragma: no cover - defensive failure path
            log.exception("Unexpected error during extraction")
            return ExtractionResult(success=False, error=f"Unexpected error: {exc}")
    
    def _execute_extraction(
        self,
        document_base64: str,
        file_type: str,
        method: ExtractionMethod,
        data_elements: List[Dict[str, Any]],
        doc_metadata: Dict[str, Any],
        document_bytes: bytes,
    ) -> Dict[str, Any]:
        """Execute extraction using the selected method.
        
        Args:
            document_base64: Base64 encoded document
            file_type: Document file type
            method: Selected extraction method
            data_elements: Data elements to extract
            doc_metadata: Document metadata from routing
            
        Returns:
            Extracted data dictionary
            
        Raises:
            ValueError: If extraction fails
        """
        # Lookup the handler for the chosen method. This keeps branching logic out of the
        # main workflow and makes it easy to plug in new strategies later.
        strategy = self._strategies.get(method)
        if strategy is None:
            raise ValueError(f"Unsupported extraction method: {method}")

        return strategy(
            document_base64,
            file_type,
            data_elements,
            doc_metadata,
            document_bytes,
        )

    def _extract_with_text(
        self,
        document_base64: str,
        file_type: str,
        data_elements: List[Dict[str, Any]],
        _: Dict[str, Any],
        document_bytes: Optional[bytes],
    ) -> Dict[str, Any]:
        # Decode text-first documents and run the text-only extraction pipeline.
        text = parse_document(
            document_base64,
            file_type,
            all_pages=True,
            document_bytes=document_bytes,
        )
        log.debug("Parsed text document | chars=%s", len(text))

        return self.extractor.extract(
            text=text,
            data_elements=data_elements,
        )

    def _extract_with_vision(
        self,
        document_base64: str,
        file_type: str,
        data_elements: List[Dict[str, Any]],
        _: Dict[str, Any],
        document_bytes: Optional[bytes],
    ) -> Dict[str, Any]:
        # Prepare image or PDF content for the vision-capable model before extraction.
        if file_type.lower() == "pdf":
            document_data = {
                "base64_data": document_base64,
                "media_type": "application/pdf",
                "document_type": "pdf",
            }
        else:
            document_data = parse_image_document(
                document_base64,
                file_type,
                document_bytes=document_bytes,
            )
            log.debug(
                "Parsed image metadata | width=%s | height=%s",
                document_data.get("width"),
                document_data.get("height"),
            )

        return self.extractor.extract(
            text=None,
            data_elements=data_elements,
            image_data=document_data,
        )

    def _extract_with_document_intelligence(
        self,
        document_base64: str,
        _file_type: str,
        data_elements: List[Dict[str, Any]],
        _metadata: Dict[str, Any],
        _document_bytes: Optional[bytes],
    ) -> Dict[str, Any]:
        # Hand off to the Document Intelligence + LLM flow when OCR preprocessing is needed.
        return self.extractor.extract(
            text=None,
            data_elements=data_elements,
            document_base64=document_base64,
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
