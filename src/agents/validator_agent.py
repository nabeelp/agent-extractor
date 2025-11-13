"""Validator agent for validating extracted data and assigning confidence scores.

This agent uses Microsoft Agent Framework for integration with multi-agent orchestration.
It receives extracted data from the extractor agent via handoff and validates it against
the original document content using gpt-4o-mini.
"""

import logging
from typing import Any, Dict, List, Optional

from ..config.settings import Settings
from ..extraction.validator import Validator, ValidationResult


log = logging.getLogger(__name__)


class ValidatorAgentInput:
    """Input data for validator agent."""
    
    def __init__(
        self,
        document_content: str,
        data_elements: List[Dict[str, Any]],
        extracted_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize validator input.
        
        Args:
            document_content: Original document text content
            data_elements: Data element definitions
            extracted_data: Extracted data to validate
            metadata: Additional metadata from extraction
        """
        self.document_content = document_content
        self.data_elements = data_elements
        self.extracted_data = extracted_data
        self.metadata = metadata or {}


class ValidatorAgentOutput:
    """Output data from validator agent."""
    
    def __init__(
        self,
        success: bool,
        validated_data: Dict[str, Any],
        confidence_scores: Dict[str, float],
        overall_confidence: float,
        errors: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize validator output.
        
        Args:
            success: Whether validation succeeded
            validated_data: Validated extracted data
            confidence_scores: Per-field confidence scores (0.0-1.0)
            overall_confidence: Overall confidence score
            errors: List of validation errors
            metadata: Additional metadata from validation
        """
        self.success = success
        self.validated_data = validated_data
        self.confidence_scores = confidence_scores
        self.overall_confidence = overall_confidence
        self.errors = errors
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert output to dictionary.
        
        Returns:
            Dictionary representation of validation output
        """
        return {
            "success": self.success,
            "extractedData": self.validated_data,
            "confidence": self.confidence_scores,
            "overall_confidence": self.overall_confidence,
            "errors": self.errors if self.errors else None,
            "metadata": self.metadata,
        }


class ValidatorAgent:
    """Agent for validating extracted data and assigning confidence scores.
    
    This agent:
    1. Receives extracted data and original document content via handoff
    2. Validates each field against the document using gpt-4o-mini
    3. Assigns confidence scores (0.0-1.0) per field
    4. Checks required fields against configured threshold
    5. Returns validated data with confidence scores
    
    Integration with Agent Framework:
    - Can be used in sequential workflows with handoff from extractor agent
    - Tracks validation state for multi-step processing
    - Provides structured output for orchestrator aggregation
    """
    
    def __init__(self, settings: Settings):
        """Initialize validator agent.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        self.validator = Validator(settings)
        
        log.info(
            "Validator agent initialized | model=%s | threshold=%.2f",
            settings.validation_model or "gpt-4o-mini",
            settings.min_confidence_threshold,
        )
    
    def validate(
        self,
        validator_input: ValidatorAgentInput,
    ) -> ValidatorAgentOutput:
        """Validate extracted data and assign confidence scores.
        
        This is the main agent function that can be called in a workflow.
        
        Args:
            validator_input: Input containing document content and extracted data
            
        Returns:
            ValidatorAgentOutput with validation results and confidence scores
        """
        try:
            log.info(
                "Starting validation | fields=%s",
                len(validator_input.extracted_data),
            )
            
            # Execute validation using validator module
            validation_result: ValidationResult = self.validator.validate(
                document_content=validator_input.document_content,
                data_elements=validator_input.data_elements,
                extracted_data=validator_input.extracted_data,
            )
            
            # Extract confidence scores from validation result
            confidence_scores = {
                field_name: field_result.confidence_score
                for field_name, field_result in validation_result.field_results.items()
            }
            
            # Combine extraction metadata with validation metadata
            combined_metadata = {
                **validator_input.metadata,
                **validation_result.to_dict().get("field_details", {}),
            }
            
            log.info(
                "Validation completed | success=%s | overall_confidence=%.2f | errors=%s",
                validation_result.success,
                validation_result.overall_confidence,
                len(validation_result.errors),
            )
            
            return ValidatorAgentOutput(
                success=validation_result.success,
                validated_data=validator_input.extracted_data,
                confidence_scores=confidence_scores,
                overall_confidence=validation_result.overall_confidence,
                errors=validation_result.errors,
                metadata=combined_metadata,
            )
            
        except Exception as exc:
            log.exception("Validator agent failed")
            return ValidatorAgentOutput(
                success=False,
                validated_data={},
                confidence_scores={},
                overall_confidence=0.0,
                errors=[f"Validation failed: {str(exc)}"],
                metadata=validator_input.metadata,
            )


def create_validator_agent(settings: Settings) -> ValidatorAgent:
    """Factory function to create a validator agent.
    
    Args:
        settings: Application settings
        
    Returns:
        ValidatorAgent instance
    """
    return ValidatorAgent(settings)
