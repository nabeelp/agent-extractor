"""Document parser for extracting text from PDF documents."""

import base64
from io import BytesIO
from typing import Optional
from PyPDF2 import PdfReader


class DocumentParser:
    """Parser for extracting text content from documents."""
    
    def parse_pdf(self, document_base64: str) -> str:
        """Extract text from a PDF document (first page only for MVP).
        
        Args:
            document_base64: Base64 encoded PDF document
            
        Returns:
            Extracted text content from first page
            
        Raises:
            ValueError: If document cannot be decoded or parsed
        """
        try:
            # Decode base64 to bytes
            pdf_bytes = base64.b64decode(document_base64)
            
            # Create PDF reader from bytes
            pdf_file = BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)
            
            # Extract text from first page only (MVP limitation)
            if len(reader.pages) == 0:
                raise ValueError("PDF document has no pages")
            
            first_page = reader.pages[0]
            text = first_page.extract_text()
            
            if not text or not text.strip():
                raise ValueError("No text could be extracted from PDF first page")
            
            return text.strip()
            
        except base64.binascii.Error as e:
            raise ValueError(f"Invalid base64 encoding: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to parse PDF document: {str(e)}")


def parse_document(document_base64: str, file_type: str) -> str:
    """Parse document and extract text content.
    
    Args:
        document_base64: Base64 encoded document
        file_type: Document type (currently only 'pdf' supported)
        
    Returns:
        Extracted text content
        
    Raises:
        ValueError: If file type not supported or parsing fails
    """
    if file_type.lower() != 'pdf':
        raise ValueError(f"Unsupported file type: {file_type}. MVP only supports PDF.")
    
    parser = DocumentParser()
    return parser.parse_pdf(document_base64)
