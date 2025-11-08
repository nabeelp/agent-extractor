"""Document extraction agent using Microsoft Agent Framework."""

from typing import Any, Dict, List, Optional

from ..config.settings import Settings
from ..extraction.document_parser import parse_document
from ..extraction.extractor import extract_data


class ExtractionResult:
    """Result from document extraction."""
    
    def __init__(self, success: bool, data: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
        """Initialize extraction result.
        
        Args:
            success: Whether extraction succeeded
            data: Extracted data dictionary (if successful)
            error: Error message (if failed)
        """
        self.success = success
        self.data = data or {}
        self.error = error
    
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
        
        return result


class ExtractorAgent:
    """Agent for extracting structured data from documents.
    
    This is a simple MVP agent that coordinates document parsing and extraction.
    Future versions will use Microsoft Agent Framework's orchestration capabilities.
    """
    
    def __init__(self, settings: Settings):
        """Initialize extractor agent.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        print(f"[ExtractorAgent] Initialized with model: {settings.extraction_model}")
    
    def extract_from_document(
        self,
        document_base64: str,
        file_type: str,
        data_elements: List[Dict[str, Any]]
    ) -> ExtractionResult:
        """Extract data from a document.
        
        This implements a simple workflow:
        1. Parse document (base64 -> text)
        2. Extract data using LLM
        3. Return results
        
        Args:
            document_base64: Base64 encoded document
            file_type: Document type (e.g., 'pdf')
            data_elements: List of data elements to extract
            
        Returns:
            ExtractionResult with extracted data or error
        """
        try:
            print(f"[ExtractorAgent] Starting extraction for {file_type} document")
            print(f"[ExtractorAgent] Data elements to extract: {len(data_elements)}")
            
            # Step 1: Parse document to extract text
            print("[ExtractorAgent] Step 1: Parsing document...")
            text = parse_document(document_base64, file_type)
            print(f"[ExtractorAgent] Extracted {len(text)} characters of text")
            
            # Step 2: Extract data using LLM
            print("[ExtractorAgent] Step 2: Extracting data with LLM...")
            extracted_data = extract_data(text, data_elements, self.settings)
            print(f"[ExtractorAgent] Extracted {len(extracted_data)} fields")
            
            # Step 3: Return results (no validation for MVP)
            print("[ExtractorAgent] Extraction completed successfully")
            return ExtractionResult(success=True, data=extracted_data)
            
        except ValueError as e:
            # Handle expected errors (validation, parsing failures)
            print(f"[ExtractorAgent] Extraction failed: {str(e)}")
            return ExtractionResult(success=False, error=str(e))
        
        except Exception as e:
            # Handle unexpected errors
            print(f"[ExtractorAgent] Unexpected error: {str(e)}")
            return ExtractionResult(success=False, error=f"Unexpected error: {str(e)}")


def create_extractor_agent(settings: Settings) -> ExtractorAgent:
    """Factory function to create an extractor agent.
    
    Args:
        settings: Application settings
        
    Returns:
        ExtractorAgent instance
    """
    return ExtractorAgent(settings)
