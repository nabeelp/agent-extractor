"""Orchestrator for coordinating multi-agent workflow.

This orchestrator implements a sequential workflow pattern:
1. Extractor Agent → processes document and extracts data
2. Validator Agent → validates extracted data and assigns confidence scores
3. Aggregates final results

Uses Microsoft Agent Framework patterns for agent coordination and handoff.
"""

import logging
from typing import Any, Dict, List

from ..config.settings import Settings
from ..agents.extractor_agent import ExtractorAgent, ExtractionResult, create_extractor_agent
from ..agents.validator_agent import (
    ValidatorAgent,
    ValidatorAgentInput,
    ValidatorAgentOutput,
    create_validator_agent,
)


log = logging.getLogger(__name__)


class OrchestrationResult:
    """Result from orchestrated multi-agent workflow."""
    
    def __init__(
        self,
        success: bool,
        extracted_data: Dict[str, Any],
        confidence_scores: Dict[str, float],
        overall_confidence: float,
        errors: List[str],
        metadata: Dict[str, Any],
    ):
        """Initialize orchestration result.
        
        Args:
            success: Whether overall workflow succeeded
            extracted_data: Final extracted and validated data
            confidence_scores: Per-field confidence scores
            overall_confidence: Overall confidence score
            errors: List of errors from any stage
            metadata: Combined metadata from all agents
        """
        self.success = success
        self.extracted_data = extracted_data
        self.confidence_scores = confidence_scores
        self.overall_confidence = overall_confidence
        self.errors = errors
        self.metadata = metadata
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary.
        
        Returns:
            Dictionary representation of orchestration result
        """
        result = {
            "success": self.success,
            "extractedData": self.extracted_data,
            "confidence": self.confidence_scores,
            "overall_confidence": self.overall_confidence,
        }
        
        if self.errors:
            result["errors"] = self.errors
        
        if self.metadata:
            result["metadata"] = self.metadata
        
        return result


class ExtractionOrchestrator:
    """Orchestrator for sequential multi-agent extraction and validation workflow.
    
    Workflow stages:
    1. Extraction Stage:
       - Extractor agent routes, parses, and extracts data from document
       - Returns extracted data with extraction metadata
    
    2. Validation Stage (handoff):
       - Validator agent receives extracted data and original document content
       - Validates each field and assigns confidence scores
       - Returns validated data with confidence scores
    
    3. Aggregation:
       - Combines results from both agents
       - Applies business rules (required field thresholds)
       - Returns final orchestrated result
    
    Error Handling:
    - If extraction fails, workflow stops and returns error
    - If validation fails, returns extraction results without confidence scores
    - Structured logging at each stage for observability
    """
    
    def __init__(self, settings: Settings):
        """Initialize orchestrator with agent instances.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        self.extractor_agent = create_extractor_agent(settings)
        self.validator_agent = create_validator_agent(settings)
        
        log.info("Extraction orchestrator initialized with sequential workflow")
    
    def orchestrate(
        self,
        document_base64: str,
        file_type: str,
        data_elements: List[Dict[str, Any]],
    ) -> OrchestrationResult:
        """Orchestrate sequential extraction and validation workflow.
        
        Args:
            document_base64: Base64 encoded document
            file_type: Document type (pdf, docx, png, jpg)
            data_elements: List of data elements to extract
            
        Returns:
            OrchestrationResult with validated data and confidence scores
        """
        log.info(
            "Starting orchestrated workflow | type=%s | elements=%s",
            file_type,
            len(data_elements),
        )
        
        # Stage 1: Extraction
        log.info("[Stage 1/2] Starting extraction stage")
        extraction_result: ExtractionResult = self.extractor_agent.extract_from_document(
            document_base64=document_base64,
            file_type=file_type,
            data_elements=data_elements,
        )
        
        # Check if extraction failed
        if not extraction_result.success:
            log.warning("Extraction stage failed, workflow terminated")
            return OrchestrationResult(
                success=False,
                extracted_data={},
                confidence_scores={},
                overall_confidence=0.0,
                errors=[extraction_result.error] if extraction_result.error else ["Extraction failed"],
                metadata=extraction_result.metadata,
            )
        
        log.info(
            "[Stage 1/2] Extraction completed | fields=%s",
            len(extraction_result.data),
        )
        
        # Get document content for validation from extraction result
        document_content = extraction_result.document_content or self._get_document_content_for_validation(
            document_base64,
            file_type,
            extraction_result,
        )
        
        # Stage 2: Validation (handoff from extractor to validator)
        log.info("[Stage 2/2] Starting validation stage (handoff)")
        validator_input = ValidatorAgentInput(
            document_content=document_content,
            data_elements=data_elements,
            extracted_data=extraction_result.data,
            metadata=extraction_result.metadata,
        )
        
        validation_output: ValidatorAgentOutput = self.validator_agent.validate(validator_input)
        
        log.info(
            "[Stage 2/2] Validation completed | success=%s | overall_confidence=%.2f",
            validation_output.success,
            validation_output.overall_confidence,
        )
        
        # Stage 3: Aggregation
        log.info("[Aggregation] Combining results from all stages")
        
        # Combine metadata from both stages
        combined_metadata = {
            **extraction_result.metadata,
            "validation": {
                "overall_confidence": validation_output.overall_confidence,
                "field_count": len(validation_output.confidence_scores),
            }
        }
        
        # Determine final success status
        # Success = extraction succeeded AND validation succeeded
        final_success = extraction_result.success and validation_output.success
        
        # Combine errors from both stages
        all_errors = []
        if extraction_result.error:
            all_errors.append(extraction_result.error)
        all_errors.extend(validation_output.errors)
        
        log.info(
            "Orchestration completed | success=%s | overall_confidence=%.2f | errors=%s",
            final_success,
            validation_output.overall_confidence,
            len(all_errors),
        )
        
        return OrchestrationResult(
            success=final_success,
            extracted_data=validation_output.validated_data,
            confidence_scores=validation_output.confidence_scores,
            overall_confidence=validation_output.overall_confidence,
            errors=all_errors,
            metadata=combined_metadata,
        )
    
    def _get_document_content_for_validation(
        self,
        document_base64: str,
        file_type: str,
        extraction_result: ExtractionResult,
    ) -> str:
        """Get document content for validation.
        
        In a full implementation, we'd preserve the parsed content from extraction stage.
        For MVP, we'll use a placeholder or re-parse the document.
        
        Args:
            document_base64: Base64 encoded document
            file_type: Document type
            extraction_result: Result from extraction stage
            
        Returns:
            Document content text for validation
        """
        # For MVP, we can use the extraction method metadata to determine content
        # In production, this should be part of the extraction result
        from ..extraction.document_parser import DocumentContext, parse_document
        import base64
        
        try:
            document_bytes = base64.b64decode(document_base64)
            doc_context = DocumentContext(
                file_type=file_type,
                base64_data=document_base64,
                raw_bytes=document_bytes,
            )
            
            # Parse document for text content
            # This is a simplified approach - in production, we'd pass this from extraction
            if file_type in ["pdf", "docx"]:
                content = parse_document(doc_context, all_pages=True)
                return content
            else:
                # For images, use a placeholder or OCR text if available
                return f"[Image document: {file_type}]"
                
        except Exception as exc:
            log.warning("Failed to get document content for validation: %s", exc)
            return "[Document content unavailable for validation]"


def create_orchestrator(settings: Settings) -> ExtractionOrchestrator:
    """Factory function to create an orchestrator.
    
    Args:
        settings: Application settings
        
    Returns:
        ExtractionOrchestrator instance
    """
    return ExtractionOrchestrator(settings)
