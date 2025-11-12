"""Document extraction agent using Microsoft Agent Framework."""

from typing import Any, Dict, List, Optional

from ..config.settings import Settings
from ..extraction.router import route_document, ExtractionMethod
from ..extraction.document_parser import parse_document, parse_image_document
from ..extraction.extractor import extract_data


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
        self.has_document_intelligence = (
            settings.azure_document_intelligence is not None and
            settings.azure_document_intelligence.endpoint is not None
        )
        print(f"[ExtractorAgent] Initialized with model: {settings.extraction_model}")
        print(f"[ExtractorAgent] Document Intelligence available: {self.has_document_intelligence}")
    
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
            print(f"[ExtractorAgent] Starting extraction for {file_type} document")
            print(f"[ExtractorAgent] Data elements to extract: {len(data_elements)}")
            
            # Step 1: Route document to select extraction method
            print("[ExtractorAgent] Step 1: Routing document...")
            routing_result = route_document(
                document_base64,
                file_type,
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
            
            print(f"[ExtractorAgent] Selected method: {method.value}")
            print(f"[ExtractorAgent] Reasoning: {reasoning}")
            
            # Step 2 & 3: Parse and extract based on selected method
            extracted_data = self._execute_extraction(
                document_base64,
                file_type,
                method,
                data_elements,
                doc_metadata
            )
            
            # Step 4: Return results with metadata
            print("[ExtractorAgent] Extraction completed successfully")
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
            
        except ValueError as e:
            # Handle expected errors
            print(f"[ExtractorAgent] Extraction failed: {str(e)}")
            return ExtractionResult(success=False, error=str(e))
        
        except Exception as e:
            # Handle unexpected errors
            print(f"[ExtractorAgent] Unexpected error: {str(e)}")
            return ExtractionResult(success=False, error=f"Unexpected error: {str(e)}")
    
    def _execute_extraction(
        self,
        document_base64: str,
        file_type: str,
        method: ExtractionMethod,
        data_elements: List[Dict[str, Any]],
        doc_metadata: Dict[str, Any]
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
        if method == ExtractionMethod.LLM_TEXT:
            # Text-based extraction
            print("[ExtractorAgent] Step 2: Parsing document (text)...")
            text = parse_document(document_base64, file_type, all_pages=True)
            print(f"[ExtractorAgent] Extracted {len(text)} characters of text")
            
            print("[ExtractorAgent] Step 3: Extracting data with LLM (text)...")
            return extract_data(
                text=text,
                data_elements=data_elements,
                settings=self.settings
            )
        
        elif method == ExtractionMethod.LLM_VISION:
            # Vision-based extraction
            if file_type.lower() == 'pdf':
                # For PDFs, pass directly to vision model (no image parsing needed)
                print("[ExtractorAgent] Step 2: Preparing PDF for vision extraction...")
                document_data = {
                    "base64_data": document_base64,
                    "media_type": "application/pdf",
                    "document_type": "pdf"
                }
                print("[ExtractorAgent] PDF prepared for vision model")
            else:
                # For images (PNG/JPG), parse to get metadata
                print("[ExtractorAgent] Step 2: Parsing document (image)...")
                document_data = parse_image_document(document_base64, file_type)
                print(f"[ExtractorAgent] Parsed image: {document_data['width']}x{document_data['height']}")
            
            print("[ExtractorAgent] Step 3: Extracting data with LLM (vision)...")
            return extract_data(
                text=None,
                data_elements=data_elements,
                settings=self.settings,
                image_data=document_data
            )
        
        elif method == ExtractionMethod.DOCUMENT_INTELLIGENCE:
            # Document Intelligence extraction
            print("[ExtractorAgent] Step 2 & 3: Extracting with Document Intelligence...")
            return extract_data(
                text=None,
                data_elements=data_elements,
                settings=self.settings,
                document_base64=document_base64,
                use_document_intelligence=True
            )
        
        else:
            raise ValueError(f"Unsupported extraction method: {method}")


def create_extractor_agent(settings: Settings) -> ExtractorAgent:
    """Factory function to create an extractor agent.
    
    Args:
        settings: Application settings
        
    Returns:
        ExtractorAgent instance
    """
    return ExtractorAgent(settings)
