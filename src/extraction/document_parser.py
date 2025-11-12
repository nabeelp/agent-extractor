"""Document parser for extracting text and images from multi-format documents."""

import base64
import logging
from io import BytesIO
from typing import Any, Dict, Optional

from docx import Document
from PIL import Image
from PyPDF2 import PdfReader


log = logging.getLogger(__name__)


class DocumentParser:
    """Parser for extracting text and image content from documents."""
    
    def parse_pdf(
        self,
        document_base64: str,
        all_pages: bool = True,
        document_bytes: Optional[bytes] = None,
    ) -> str:
        """Extract text from a PDF document.
        
        Args:
            document_base64: Base64 encoded PDF document
            all_pages: If True, extract from all pages; if False, first page only
            
        Returns:
            Extracted text content
            
        Raises:
            ValueError: If document cannot be decoded or parsed
        """
        try:
            pdf_bytes = document_bytes or base64.b64decode(document_base64)
            
            # Create PDF reader from bytes
            pdf_file = BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)
            
            if len(reader.pages) == 0:
                raise ValueError("PDF document has no pages")
            
            # Extract text from pages
            if all_pages:
                # Multi-page extraction
                texts = []
                for page_num, page in enumerate(reader.pages, 1):
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        texts.append(f"=== Page {page_num} ===\n{page_text.strip()}")
                
                if not texts:
                    raise ValueError("No text could be extracted from any PDF page")
                
                return "\n\n".join(texts)
            else:
                # Single page extraction (backward compatible)
                first_page = reader.pages[0]
                text = first_page.extract_text()
                
                if not text or not text.strip():
                    raise ValueError("No text could be extracted from PDF first page")
                
                return text.strip()
            
        except base64.binascii.Error as exc:
            raise ValueError(f"Invalid base64 encoding: {exc}") from exc
        except Exception as exc:
            raise ValueError(f"Failed to parse PDF document: {exc}") from exc
    
    def parse_docx(
        self,
        document_base64: str,
        document_bytes: Optional[bytes] = None,
    ) -> str:
        """Extract text from a DOCX document.
        
        Args:
            document_base64: Base64 encoded DOCX document
            
        Returns:
            Extracted text content
            
        Raises:
            ValueError: If document cannot be decoded or parsed
        """
        try:
            docx_bytes = document_bytes or base64.b64decode(document_base64)
            docx_file = BytesIO(docx_bytes)
            doc = Document(docx_file)
            
            # Extract text from all paragraphs
            paragraphs = []
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    paragraphs.append(text)
            
            # Extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    row_data = []
                    for cell in row.cells:
                        cell_text = cell.text.strip()
                        if cell_text:
                            row_data.append(cell_text)
                    if row_data:
                        paragraphs.append(" | ".join(row_data))
            
            if not paragraphs:
                raise ValueError("No text could be extracted from DOCX document")
            
            return "\n\n".join(paragraphs)
            
        except base64.binascii.Error as exc:
            raise ValueError(f"Invalid base64 encoding: {exc}") from exc
        except Exception as exc:
            raise ValueError(f"Failed to parse DOCX document: {exc}") from exc
    
    def parse_image(
        self,
        document_base64: str,
        file_type: str,
        document_bytes: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """Parse image and return metadata for vision-based extraction.
        
        Args:
            document_base64: Base64 encoded image
            file_type: Image file type (png, jpg, jpeg)
            
        Returns:
            Dictionary with image data and metadata
            
        Raises:
            ValueError: If image cannot be decoded or parsed
        """
        try:
            image_bytes = document_bytes or base64.b64decode(document_base64)
            
            # Open image
            image = Image.open(BytesIO(image_bytes))
            
            # Get image metadata
            width, height = image.size
            mode = image.mode
            format_name = image.format or file_type.upper()
            
            # Convert to RGB if needed (for consistency)
            if mode not in ['RGB', 'L']:
                image = image.convert('RGB')
            
            # Return image data for vision API
            return {
                "base64_data": document_base64,
                "width": width,
                "height": height,
                "mode": mode,
                "format": format_name,
                "media_type": f"image/{file_type.lower()}"
            }
            
        except base64.binascii.Error as exc:
            raise ValueError(f"Invalid base64 encoding: {exc}") from exc
        except Exception as exc:
            raise ValueError(f"Failed to parse image: {exc}") from exc


def parse_document(
    document_base64: str,
    file_type: str,
    all_pages: bool = True,
    document_bytes: Optional[bytes] = None,
) -> str:
    """Parse document and extract text content.
    
    Args:
        document_base64: Base64 encoded document
        file_type: Document type (pdf, docx, png, jpg, jpeg)
        all_pages: For PDFs, extract all pages (True) or first page only (False)
        
    Returns:
        Extracted text content
        
    Raises:
        ValueError: If file type not supported or parsing fails
    """
    parser = DocumentParser()
    file_type_lower = file_type.lower().strip()
    
    if file_type_lower == 'pdf':
        return parser.parse_pdf(document_base64, all_pages, document_bytes=document_bytes)
    elif file_type_lower == 'docx':
        return parser.parse_docx(document_base64, document_bytes=document_bytes)
    elif file_type_lower in ['png', 'jpg', 'jpeg']:
        raise ValueError(
            f"Image files ({file_type}) require vision-based extraction. "
            "Use parse_image() instead."
        )
    else:
        raise ValueError(
            f"Unsupported file type: {file_type}. "
            "Supported types: pdf, docx, png, jpg, jpeg"
        )


def parse_image_document(
    document_base64: str,
    file_type: str,
    document_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Parse image document for vision-based extraction.
    
    Args:
        document_base64: Base64 encoded image
        file_type: Image file type (png, jpg, jpeg)
        
    Returns:
        Dictionary with image data and metadata
        
    Raises:
        ValueError: If parsing fails
    """
    parser = DocumentParser()
    return parser.parse_image(document_base64, file_type, document_bytes=document_bytes)
