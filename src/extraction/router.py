"""Document routing logic to select optimal extraction strategy."""

import base64
from enum import Enum
from typing import Dict, Any, Optional
from io import BytesIO
from PIL import Image
from PyPDF2 import PdfReader


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


class DocumentRouter:
    """Analyze documents and route to optimal extraction method."""
    
    def __init__(self, use_document_intelligence: bool = False):
        """Initialize document router.
        
        Args:
            use_document_intelligence: Whether Azure Document Intelligence is available
        """
        self.use_document_intelligence = use_document_intelligence
    
    def analyze_and_route(
        self,
        document_base64: str,
        file_type: str
    ) -> Dict[str, Any]:
        """Analyze document and determine best extraction strategy.
        
        Args:
            document_base64: Base64 encoded document
            file_type: Document file type (pdf, docx, png, jpg)
            
        Returns:
            Dictionary with routing decision:
                - method: ExtractionMethod to use
                - doc_type: DocumentType detected
                - reasoning: Explanation of routing decision
                - metadata: Additional document metadata
                
        Raises:
            ValueError: If document type not supported or analysis fails
        """
        try:
            # Normalize file type
            file_type_lower = file_type.lower().strip()
            
            # Validate and detect document type
            doc_type = self._detect_document_type(file_type_lower)
            
            # Analyze document characteristics
            metadata = self._analyze_document(document_base64, doc_type)
            
            # Determine extraction method based on characteristics
            method, reasoning = self._select_extraction_method(doc_type, metadata)
            
            return {
                "method": method,
                "doc_type": doc_type,
                "reasoning": reasoning,
                "metadata": metadata
            }
            
        except Exception as e:
            raise ValueError(f"Document routing failed: {str(e)}")
    
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
            supported = ", ".join(file_type_map.keys())
            raise ValueError(
                f"Unsupported file type: {file_type}. Supported types: {supported}"
            )
        
        return file_type_map[file_type]
    
    def _analyze_document(
        self,
        document_base64: str,
        doc_type: DocumentType
    ) -> Dict[str, Any]:
        """Analyze document characteristics.
        
        Args:
            document_base64: Base64 encoded document
            doc_type: Document type
            
        Returns:
            Dictionary with document metadata
        """
        metadata = {"doc_type": doc_type.value}
        
        try:
            if doc_type == DocumentType.PDF:
                metadata.update(self._analyze_pdf(document_base64))
            elif doc_type == DocumentType.DOCX:
                metadata.update(self._analyze_docx(document_base64))
            elif doc_type in [DocumentType.PNG, DocumentType.JPG, DocumentType.JPEG]:
                metadata.update(self._analyze_image(document_base64))
        except Exception as e:
            # Non-fatal: continue with basic metadata
            metadata["analysis_error"] = str(e)
        
        return metadata
    
    def _analyze_pdf(self, document_base64: str) -> Dict[str, Any]:
        """Analyze PDF document characteristics.
        
        Args:
            document_base64: Base64 encoded PDF
            
        Returns:
            PDF metadata
        """
        try:
            pdf_bytes = base64.b64decode(document_base64)
            pdf_file = BytesIO(pdf_bytes)
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
    
    def _analyze_docx(self, document_base64: str) -> Dict[str, Any]:
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
    
    def _analyze_image(self, document_base64: str) -> Dict[str, Any]:
        """Analyze image characteristics.
        
        Args:
            document_base64: Base64 encoded image
            
        Returns:
            Image metadata
        """
        try:
            image_bytes = base64.b64decode(document_base64)
            image = Image.open(BytesIO(image_bytes))
            
            width, height = image.size
            mode = image.mode
            
            # Assess image quality (very basic heuristic)
            total_pixels = width * height
            is_low_resolution = total_pixels < 500000  # < 0.5 megapixels
            
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
            
            # Route to Document Intelligence if available and needed
            if self.use_document_intelligence and (is_scanned or text_density < 100):
                return (
                    ExtractionMethod.DOCUMENT_INTELLIGENCE,
                    f"Scanned/low-text PDF (density: {text_density}) requires OCR preprocessing"
                )
            
            # Use LLM with vision for scanned PDFs if no Document Intelligence
            if is_scanned or text_density < 100:
                return (
                    ExtractionMethod.LLM_VISION,
                    f"Scanned/low-text PDF (density: {text_density}) requires vision-capable model"
                )
            
            # Digital PDF with good text extraction
            return (
                ExtractionMethod.LLM_TEXT,
                f"Digital PDF with extractable text (density: {text_density})"
            )
        
        # Default to text-based extraction
        return (
            ExtractionMethod.LLM_TEXT,
            "Default text-based extraction"
        )


def route_document(
    document_base64: str,
    file_type: str,
    use_document_intelligence: bool = False
) -> Dict[str, Any]:
    """Route document to optimal extraction method.
    
    Args:
        document_base64: Base64 encoded document
        file_type: Document file type
        use_document_intelligence: Whether Azure Document Intelligence is available
        
    Returns:
        Routing decision dictionary
        
    Raises:
        ValueError: If routing fails
    """
    router = DocumentRouter(use_document_intelligence)
    return router.analyze_and_route(document_base64, file_type)
