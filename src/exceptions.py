"""Custom exception types for document extraction agent.

This module defines domain-specific exceptions that map to specific failure scenarios,
making error handling more predictable and enabling clean HTTP error mapping.
"""

from typing import Optional


class DocumentExtractionError(Exception):
    """Base exception for all document extraction errors."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        """Initialize exception with message and optional details.
        
        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(DocumentExtractionError):
    """Raised when configuration is invalid or missing required values."""
    pass


class DocumentParsingError(DocumentExtractionError):
    """Raised when document cannot be parsed or decoded."""
    pass


class Base64DecodingError(DocumentParsingError):
    """Raised when base64 decoding fails."""
    pass


class PDFParsingError(DocumentParsingError):
    """Raised when PDF parsing fails."""
    pass


class DOCXParsingError(DocumentParsingError):
    """Raised when DOCX parsing fails."""
    pass


class ImageParsingError(DocumentParsingError):
    """Raised when image parsing fails."""
    pass


class DocumentRoutingError(DocumentExtractionError):
    """Raised when document routing/analysis fails."""
    pass


class UnsupportedFileTypeError(DocumentRoutingError):
    """Raised when file type is not supported."""
    
    def __init__(self, file_type: str, supported_types: list):
        """Initialize with file type information.
        
        Args:
            file_type: The unsupported file type
            supported_types: List of supported file types
        """
        message = f"Unsupported file type: {file_type}"
        details = {
            "file_type": file_type,
            "supported_types": supported_types
        }
        super().__init__(message, details)
        self.file_type = file_type
        self.supported_types = supported_types


class ExtractionError(DocumentExtractionError):
    """Raised when data extraction fails."""
    pass


class TextExtractionError(ExtractionError):
    """Raised when text-based extraction fails."""
    pass


class VisionExtractionError(ExtractionError):
    """Raised when vision-based extraction fails."""
    pass


class DocumentIntelligenceError(ExtractionError):
    """Raised when Azure Document Intelligence extraction fails."""
    pass


class RequiredFieldMissingError(ExtractionError):
    """Raised when a required field is not found in extracted data."""
    
    def __init__(self, field_name: str, field_description: Optional[str] = None):
        """Initialize with field information.
        
        Args:
            field_name: Name of the missing required field
            field_description: Optional description of the field
        """
        message = f"Required field '{field_name}' not found in document"
        details = {
            "field_name": field_name,
            "field_description": field_description
        }
        super().__init__(message, details)
        self.field_name = field_name


class InvalidExtractionResultError(ExtractionError):
    """Raised when extraction result cannot be parsed as valid JSON."""
    pass


class DocumentIntelligenceNotConfiguredError(ExtractionError):
    """Raised when Document Intelligence is required but not configured."""
    pass


class ValidationError(DocumentExtractionError):
    """Raised when data validation fails."""
    pass
