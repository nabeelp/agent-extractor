"""Validation and confidence scoring for extracted data using gpt-4o-mini."""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import AsyncAzureOpenAI
from agent_framework.openai import OpenAIChatClient
from agent_framework._types import ChatMessage

from ..config.settings import Settings
from ..exceptions import InvalidExtractionResultError, ValidationError
from .structured_parser import StructuredResponseParser


log = logging.getLogger(__name__)


@dataclass
class FieldValidationResult:
    """Result of validating a single field."""
    
    field_name: str
    is_valid: bool
    confidence_score: float  # 0.0 to 1.0
    extracted_value: Any
    reasoning: Optional[str] = None
    

@dataclass
class ValidationResult:
    """Complete validation result for all fields."""
    
    success: bool
    field_results: Dict[str, FieldValidationResult]
    overall_confidence: float
    errors: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert validation result to dictionary.
        
        Returns:
            Dictionary with validation results and confidence scores
        """
        confidence_scores = {
            field_name: result.confidence_score
            for field_name, result in self.field_results.items()
        }
        
        return {
            "success": self.success,
            "confidence": confidence_scores,
            "overall_confidence": self.overall_confidence,
            "errors": self.errors,
            "field_details": {
                field_name: {
                    "is_valid": result.is_valid,
                    "confidence": result.confidence_score,
                    "value": result.extracted_value,
                    "reasoning": result.reasoning,
                }
                for field_name, result in self.field_results.items()
            }
        }


class ValidationPromptBuilder:
    """Build prompts for validation tasks."""
    
    DEFAULT_TEMPLATE = """You are a data validation assistant. Your task is to validate extracted data against the original document content.

For each field, assess:
1. Whether the extracted value is present in the document
2. Whether the value matches the expected format
3. How confident you are that the extraction is correct (0.0 to 1.0)

Original document content:
{document_content}

Data elements definition:
{elements_definition}

Extracted data to validate:
{extracted_data}

Return a JSON object with this structure:
{{
  "field_name_1": {{
    "is_valid": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
  }},
  "field_name_2": {{
    "is_valid": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
  }}
}}

Guidelines:
- confidence 0.9-1.0: Value clearly present and correctly formatted
- confidence 0.7-0.9: Value present but may have minor formatting issues
- confidence 0.5-0.7: Value partially matches or inferred
- confidence 0.0-0.5: Value not found or incorrect

Return ONLY the JSON object, no additional text."""
    
    def __init__(self, template: Optional[str] = None):
        """Initialize prompt builder.
        
        Args:
            template: Custom validation prompt template
        """
        self.template = template or self.DEFAULT_TEMPLATE
    
    def build(
        self,
        document_content: str,
        data_elements: List[Dict[str, Any]],
        extracted_data: Dict[str, Any],
    ) -> str:
        """Build validation prompt.
        
        Args:
            document_content: Original document text content
            data_elements: Data element definitions
            extracted_data: Extracted data to validate
            
        Returns:
            Formatted validation prompt
        """
        # Format elements definition
        elements_text = []
        for element in data_elements:
            required_text = " (REQUIRED)" if element.get("required", False) else ""
            elements_text.append(
                f"- {element['name']}: {element['description']} "
                f"[format: {element.get('format', 'string')}]{required_text}"
            )
        
        # Format extracted data
        extracted_text = json.dumps(extracted_data, indent=2)
        
        return self.template.format(
            document_content=document_content[:5000],  # Limit content size
            elements_definition="\n".join(elements_text),
            extracted_data=extracted_text,
        )


class ValidationResultParser:
    """Parse LLM validation responses into structured results."""

    def __init__(self) -> None:
        self._parser = StructuredResponseParser("validation response")

    def parse(
        self,
        response_text: str,
        extracted_data: Dict[str, Any],
    ) -> Dict[str, FieldValidationResult]:
        """Parse validation response into field results."""
        try:
            validation_data = self._parser.parse(response_text)

            field_results = {}
            for field_name, field_data in validation_data.items():
                field_results[field_name] = FieldValidationResult(
                    field_name=field_name,
                    is_valid=field_data.get("is_valid", False),
                    confidence_score=float(field_data.get("confidence", 0.0)),
                    extracted_value=extracted_data.get(field_name),
                    reasoning=field_data.get("reasoning"),
                )

            return field_results

        except InvalidExtractionResultError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidExtractionResultError(
                f"Invalid validation result structure: {exc}"
            ) from exc


class Validator:
    """Validate extracted data and assign confidence scores using gpt-4o-mini."""
    
    def __init__(self, settings: Settings):
        """Initialize validator.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        
        # Create async token provider for Azure AD authentication
        async def get_azure_ad_token() -> str:
            """Get Azure AD token for OpenAI API authentication."""
            token = settings.azure_credential.get_token(
                "https://cognitiveservices.azure.com/.default"
            )
            return token.token
        
        # Get validation model name
        validation_model = settings.validation_model or "gpt-4o-mini"
        
        # Create AsyncAzureOpenAI client with token provider
        azure_client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_ai_foundry_endpoint,
            azure_ad_token_provider=get_azure_ad_token,
            api_version="2024-02-01",  # Azure OpenAI API version
        )
        
        # Create chat client for validation using Agent Framework OpenAI client
        self.client = OpenAIChatClient(
            model_id=validation_model,
            async_client=azure_client,
        )
        self._async_openai_client = azure_client
        
        # Use validation prompt if configured, otherwise use default
        prompt_template = settings.validation_prompt
        self.prompt_builder = ValidationPromptBuilder(prompt_template)
        self.result_parser = ValidationResultParser()
        
        log.info(
            "Validator initialized | model=%s",
            validation_model,
        )

    async def aclose(self) -> None:
        """Close the underlying async OpenAI client."""
        try:
            await self._async_openai_client.close()
        except AttributeError:  # pragma: no cover - defensive
            pass
    
    async def validate(
        self,
        document_content: str,
        data_elements: List[Dict[str, Any]],
        extracted_data: Dict[str, Any],
    ) -> ValidationResult:
        """Validate extracted data against original document content.
        
        Args:
            document_content: Original document text content
            data_elements: Data element definitions
            extracted_data: Extracted data to validate
            
        Returns:
            ValidationResult with per-field confidence scores and validation status
            
        Raises:
            ValidationError: If validation process fails
        """
        try:
            if not data_elements:
                error_msg = "Validation requires at least one data element"
                log.warning(error_msg)
                return ValidationResult(
                    success=False,
                    field_results={},
                    overall_confidence=0.0,
                    errors=[error_msg],
                )

            log.info("Starting validation for %s fields", len(extracted_data))
            
            # Build validation prompt
            validation_prompt = self.prompt_builder.build(
                document_content=document_content,
                data_elements=data_elements,
                extracted_data=extracted_data,
            )
            
            # Call validation model using Agent Framework OpenAI client
            response = await self.client.get_response(
                messages=[
                    ChatMessage("system", text="You are a data validation assistant."),
                    ChatMessage("user", text=validation_prompt),
                ],
                temperature=0.1,  # Low temperature for consistent validation
                top_p=0.9,
            )
            
            # Parse validation response - ChatResponse has a text attribute
            response_text = response.text or ""
            field_results = self.result_parser.parse(response_text, extracted_data)
            
            # Calculate overall confidence and validate required fields
            errors = []
            confidence_scores = []
            
            for element in data_elements:
                field_name = element["name"]
                is_required = element.get("required", False)
                
                # Check if field was validated
                if field_name not in field_results:
                    if is_required:
                        errors.append(f"Required field '{field_name}' missing from validation results")
                    continue
                
                field_result = field_results[field_name]
                confidence_scores.append(field_result.confidence_score)
                
                # Check required field confidence threshold
                if is_required:
                    min_threshold = self.settings.min_confidence_threshold
                    if field_result.confidence_score < min_threshold:
                        errors.append(
                            f"Required field '{field_name}' confidence {field_result.confidence_score:.2f} "
                            f"below threshold {min_threshold:.2f}"
                        )
                    if not field_result.is_valid:
                        errors.append(f"Required field '{field_name}' failed validation")
            
            # Calculate overall confidence (average of all fields)
            if not confidence_scores:
                errors.append("Validation produced no confidence scores")

            overall_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
            
            success = len(errors) == 0
            
            log.info(
                "Validation completed | success=%s | overall_confidence=%.2f | errors=%s",
                success,
                overall_confidence,
                len(errors),
            )
            
            return ValidationResult(
                success=success,
                field_results=field_results,
                overall_confidence=overall_confidence,
                errors=errors,
            )
            
        except InvalidExtractionResultError:
            raise
        except Exception as exc:
            log.exception("Validation failed")
            raise ValidationError(f"Validation failed: {exc}") from exc
