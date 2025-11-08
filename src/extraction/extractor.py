"""Data extraction using Azure AI Foundry models."""

import json
from typing import Any, Dict, List
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential

from ..config.settings import Settings


class Extractor:
    """Extract structured data from document text using LLM."""
    
    def __init__(self, settings: Settings):
        """Initialize extractor with Azure AI Foundry client.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        
        # Initialize Azure AI Inference client with Entra ID authentication
        # Note: Using get_token() to get bearer token from DefaultAzureCredential
        token = settings.azure_credential.get_token("https://cognitiveservices.azure.com/.default")
        
        self.client = ChatCompletionsClient(
            endpoint=settings.azure_ai_foundry_endpoint,
            credential=AzureKeyCredential(token.token)
        )
    
    def extract(self, text: str, data_elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract data elements from document text.
        
        Args:
            text: Document text content
            data_elements: List of data elements to extract, each with:
                - name: Field name
                - description: What to extract
                - format: Expected data format (string, number, date, etc.)
                - required: Boolean indicating if field is required
                
        Returns:
            Dictionary with extracted data, keyed by field name
            
        Raises:
            ValueError: If extraction fails or required fields missing
        """
        try:
            # Build extraction prompt
            system_prompt = self._build_system_prompt(data_elements)
            user_prompt = f"Document text:\n\n{text}\n\nExtract the requested data elements."
            
            # Call LLM for extraction
            response = self.client.complete(
                messages=[
                    SystemMessage(system_prompt),
                    UserMessage(user_prompt)
                ],
                temperature=0.1,  # Low temperature for consistent extraction
                top_p=0.9,
                model=self.settings.extraction_model
            )
            
            # Parse response
            result_text = response.choices[0].message.content
            extracted_data = self._parse_extraction_result(result_text)
            
            # Basic validation: check required fields are present
            for element in data_elements:
                if element.get('required', False):
                    field_name = element['name']
                    if field_name not in extracted_data or not extracted_data[field_name]:
                        raise ValueError(f"Required field '{field_name}' not found in document")
            
            return extracted_data
            
        except Exception as e:
            raise ValueError(f"Extraction failed: {str(e)}")
    
    def _build_system_prompt(self, data_elements: List[Dict[str, Any]]) -> str:
        """Build system prompt for extraction.
        
        Args:
            data_elements: List of data elements to extract
            
        Returns:
            System prompt string
        """
        element_descriptions = []
        for element in data_elements:
            required_text = " (REQUIRED)" if element.get('required', False) else ""
            element_descriptions.append(
                f"- {element['name']}: {element['description']} "
                f"[format: {element.get('format', 'string')}]{required_text}"
            )
        
        elements_text = "\n".join(element_descriptions)
        
        # Get prompt template from settings and substitute elements
        prompt_template = self.settings.extraction_prompt
        return prompt_template.replace("{elements}", elements_text)
    
    def _parse_extraction_result(self, result_text: str) -> Dict[str, Any]:
        """Parse LLM response into structured data.
        
        Args:
            result_text: Raw LLM response text
            
        Returns:
            Parsed data dictionary
            
        Raises:
            ValueError: If response cannot be parsed as JSON
        """
        try:
            # Try to extract JSON from response (handle cases where LLM adds extra text)
            result_text = result_text.strip()
            
            # Find JSON object boundaries
            start_idx = result_text.find('{')
            end_idx = result_text.rfind('}')
            
            if start_idx == -1 or end_idx == -1:
                raise ValueError("No JSON object found in response")
            
            json_text = result_text[start_idx:end_idx + 1]
            return json.loads(json_text)
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse extraction result as JSON: {str(e)}")


def extract_data(
    text: str,
    data_elements: List[Dict[str, Any]],
    settings: Settings
) -> Dict[str, Any]:
    """Extract structured data from document text.
    
    Args:
        text: Document text content
        data_elements: List of data element definitions
        settings: Application settings
        
    Returns:
        Extracted data dictionary
        
    Raises:
        ValueError: If extraction fails
    """
    extractor = Extractor(settings)
    return extractor.extract(text, data_elements)
