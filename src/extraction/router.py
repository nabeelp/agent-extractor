"""Document routing logic to select optimal extraction strategy."""

import logging
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from typing import Any, Dict

from PIL import Image
from PyPDF2 import PdfReader

from ..exceptions import DocumentRoutingError, UnsupportedFileTypeError
from .document_parser import DocumentContext


log = logging.getLogger(__name__)


class ExtractionMethod(Enum):
    """Available extraction methods."""
    LLM_TEXT = "llm_text"  # LLM-based extraction from text
    LLM_VISION = "llm_vision"  # LLM-based extraction with vision capabilities
    DOCUMENT_INTELLIGENCE = "document_intelligence"  # Azure Document Intelligence


class DocumentType(Enum):
    """Supported document types."""
    PDF = "pdf"
    DOCX = "docx"
    PNG = "png"
    JPG = "jpg"
    JPEG = "jpeg"


@dataclass
class RoutingDecision:
    method: ExtractionMethod
    doc_type: DocumentType
    reasoning: str
    metadata: Dict[str, Any]


class DocumentRouter:
    """Analyze documents and route to optimal extraction method."""
    
    def __init__(
        self,
        use_document_intelligence: bool = False,
        text_density_threshold: int = 100,
        low_resolution_threshold: int = 500000,
        use_di_for_scanned: bool = True,
        use_di_for_low_text: bool = True,
        use_di_for_poor_quality: bool = True
    ):
        """Initialize document router.
        
        Args:
            use_document_intelligence: Whether Azure Document Intelligence is available
            text_density_threshold: Minimum chars/page for text-based extraction
            low_resolution_threshold: Pixel count threshold for low resolution
            use_di_for_scanned: Use Document Intelligence for scanned documents
            use_di_for_low_text: Use Document Intelligence for low text density
            use_di_for_poor_quality: Use Document Intelligence for poor image quality
        """
        self.use_document_intelligence = use_document_intelligence
        self.text_density_threshold = text_density_threshold
        self.low_resolution_threshold = low_resolution_threshold
        self.use_di_for_scanned = use_di_for_scanned
        self.use_di_for_low_text = use_di_for_low_text
        self.use_di_for_poor_quality = use_di_for_poor_quality
    
    def analyze_and_route(
        self,
        context: DocumentContext,
    ) -> RoutingDecision:
        """Analyze document and determine best extraction strategy.
        
        Args:
            context: Shared document context containing metadata and raw bytes
            
        Returns:
            RoutingDecision containing method, document type, reasoning, and metadata
                
        Raises:
            ValueError: If document type not supported or analysis fails
        """
        try:
            doc_type = self._detect_document_type(context.file_type)
            metadata = self._analyze_document(context, doc_type)
            method, reasoning = self._select_extraction_method(doc_type, metadata)

            return RoutingDecision(
                method=method,
                doc_type=doc_type,
                reasoning=reasoning,
                metadata=metadata,
            )
            
        except DocumentRoutingError:
            raise
        except UnsupportedFileTypeError:
            raise
        except Exception as e:
            raise DocumentRoutingError(f"Document routing failed: {str(e)}") from e
    
    def _detect_document_type(self, file_type: str) -> DocumentType:
        """Detect and validate document type.
        
        Args:
            file_type: File type string
            
        Returns:
            DocumentType enum
            
        Raises:
            ValueError: If file type not supported
        """
        file_type_map = {
            "pdf": DocumentType.PDF,
            "docx": DocumentType.DOCX,
            "png": DocumentType.PNG,
            "jpg": DocumentType.JPG,
            "jpeg": DocumentType.JPEG
        }
        
        if file_type not in file_type_map:
            supported = list(file_type_map.keys())
            raise UnsupportedFileTypeError(file_type, supported)
        
        return file_type_map[file_type]
    
    def _analyze_document(
        self,
        context: DocumentContext,
        doc_type: DocumentType,
    ) -> Dict[str, Any]:
        """Analyze document characteristics.
        
        Args:
            context: Shared document context
            doc_type: Document type
            
        Returns:
            Dictionary with document metadata
        """
        metadata = {"doc_type": doc_type.value}
        
        try:
            if doc_type == DocumentType.PDF:
                metadata.update(self._analyze_pdf(context))
            elif doc_type == DocumentType.DOCX:
                metadata.update(self._analyze_docx(context))
            elif doc_type in [DocumentType.PNG, DocumentType.JPG, DocumentType.JPEG]:
                metadata.update(self._analyze_image(context))
        except Exception as e:
            # Non-fatal: continue with basic metadata
            metadata["analysis_error"] = str(e)
        
        return metadata
    
    def _analyze_pdf(
        self,
        context: DocumentContext,
    ) -> Dict[str, Any]:
        """Analyze PDF document characteristics.
        
        Args:
            document_base64: Base64 encoded PDF
            
        Returns:
            PDF metadata
        """
        try:
            pdf_file = BytesIO(context.raw_bytes)
            reader = PdfReader(pdf_file)
            
            total_pages = len(reader.pages)
            
            # Sample first page for text density
            if total_pages > 0:
                first_page = reader.pages[0]
                text = first_page.extract_text() or ""
                
                # Calculate text density (characters per page)
                text_density = len(text.strip())
                has_text = text_density > 50  # Threshold for "digital" PDF
                
                return {
                    "total_pages": total_pages,
                    "text_density": text_density,
                    "has_extractable_text": has_text,
                    "is_likely_scanned": not has_text
                }
            
            return {"total_pages": 0}
            
        except Exception as e:
            return {"error": f"PDF analysis failed: {str(e)}"}
    
    def _analyze_docx(
        self,
        context: DocumentContext,
    ) -> Dict[str, Any]:
        """Analyze DOCX document characteristics.
        
        Args:
            document_base64: Base64 encoded DOCX
            
        Returns:
            DOCX metadata
        """
        # DOCX files always have extractable text
        return {
            "has_extractable_text": True,
            "is_structured": True
        }
    
    def _analyze_image(
        self,
        context: DocumentContext,
    ) -> Dict[str, Any]:
        """Analyze image characteristics.
        
        Args:
            document_base64: Base64 encoded image
            
        Returns:
            Image metadata
        """
        try:
            image = Image.open(BytesIO(context.raw_bytes))
            
            width, height = image.size
            mode = image.mode
            
            # Assess image quality (very basic heuristic)
            total_pixels = width * height
            is_low_resolution = total_pixels < self.low_resolution_threshold
            
            return {
                "width": width,
                "height": height,
                "mode": mode,
                "total_pixels": total_pixels,
                "is_low_resolution": is_low_resolution,
                "is_image": True
            }
            
        except Exception as e:
            return {"error": f"Image analysis failed: {str(e)}"}
    
    def _select_extraction_method(
        self,
        doc_type: DocumentType,
        metadata: Dict[str, Any]
    ) -> tuple[ExtractionMethod, str]:
        """Select optimal extraction method based on document analysis.
        
        Args:
            doc_type: Document type
            metadata: Document metadata from analysis
            
        Returns:
            Tuple of (ExtractionMethod, reasoning string)
        """
        # Image files always use vision
        if doc_type in [DocumentType.PNG, DocumentType.JPG, DocumentType.JPEG]:
            return (
                ExtractionMethod.LLM_VISION,
                "Image document requires vision-capable model for extraction"
            )
        
        # DOCX files have structured text
        if doc_type == DocumentType.DOCX:
            return (
                ExtractionMethod.LLM_TEXT,
                "DOCX document has structured extractable text"
            )
        
        # PDF routing logic
        if doc_type == DocumentType.PDF:
            # Check if PDF has extractable text
            has_text = metadata.get("has_extractable_text", False)
            is_scanned = metadata.get("is_likely_scanned", False)
            text_density = metadata.get("text_density", 0)
            
            # Determine if Document Intelligence should be used based on configured thresholds
            should_use_di = False
            if self.use_document_intelligence:
                if is_scanned and self.use_di_for_scanned:
                    should_use_di = True
                elif text_density < self.text_density_threshold and self.use_di_for_low_text:
                    should_use_di = True
            
            # Route to Document Intelligence if conditions are met
            if should_use_di:
                return (
                    ExtractionMethod.DOCUMENT_INTELLIGENCE,
                    f"Scanned/low-text PDF (density: {text_density}, threshold: {self.text_density_threshold}) requires OCR preprocessing"
                )
            
            # Use LLM with vision for scanned PDFs if no Document Intelligence
            if is_scanned or text_density < self.text_density_threshold:
                return (
                    ExtractionMethod.LLM_VISION,
                    f"Scanned/low-text PDF (density: {text_density}, threshold: {self.text_density_threshold}) requires vision-capable model"
                )
            
            # Digital PDF with good text extraction
            return (
                ExtractionMethod.LLM_TEXT,
                f"Digital PDF with extractable text (density: {text_density}, threshold: {self.text_density_threshold})"
            )
        
        # Default to text-based extraction
        return (
            ExtractionMethod.LLM_TEXT,
            "Default text-based extraction"
        )
