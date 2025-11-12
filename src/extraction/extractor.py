"""Data extraction using Azure AI Foundry models and Azure Document Intelligence."""

import json
from typing import Any, Dict, List, Optional
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage, ImageContentItem, ImageUrl, TextContentItem
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

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
        self.client = ChatCompletionsClient(
            endpoint=settings.azure_ai_foundry_endpoint,
            credential=settings.azure_credential,
            credential_scopes=["https://cognitiveservices.azure.com/.default"]
        )
        
        # Initialize Azure Document Intelligence client if configured
        self.doc_intelligence_client = None
        if settings.azure_document_intelligence:
            doc_intel_config = settings.azure_document_intelligence
            if doc_intel_config.endpoint:
                if doc_intel_config.use_managed_identity:
                    # Use managed identity
                    self.doc_intelligence_client = DocumentAnalysisClient(
                        endpoint=doc_intel_config.endpoint,
                        credential=settings.azure_credential
                    )
                elif doc_intel_config.key:
                    # Use API key
                    self.doc_intelligence_client = DocumentAnalysisClient(
                        endpoint=doc_intel_config.endpoint,
                        credential=AzureKeyCredential(doc_intel_config.key)
                    )
    
    def extract_from_text(
        self,
        text: str,
        data_elements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract data elements from document text using text-based LLM.
        
        Args:
            text: Document text content
            data_elements: List of data elements to extract
                
        Returns:
            Dictionary with extracted data, keyed by field name
            
        Raises:
            ValueError: If extraction fails
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
            
            return extracted_data
            
        except Exception as e:
            raise ValueError(f"Text extraction failed: {str(e)}")
    
    def extract_from_image(
        self,
        image_data: Dict[str, Any],
        data_elements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract data elements from image or PDF using vision-capable LLM.
        
        Args:
            image_data: Dictionary with image/PDF data and metadata
                - base64_data: Base64 encoded document
                - media_type: MIME type (image/png, image/jpeg, application/pdf)
                - Additional metadata for images (width, height, etc.)
            data_elements: List of data elements to extract
                
        Returns:
            Dictionary with extracted data, keyed by field name
            
        Raises:
            ValueError: If extraction fails
        """
        try:
            # Build extraction prompt
            system_prompt = self._build_system_prompt(data_elements)
            
            # Create vision message with image or PDF
            media_type = image_data['media_type']
            image_url = f"data:{media_type};base64,{image_data['base64_data']}"
            
            # Adjust prompt text based on document type
            if media_type == "application/pdf":
                prompt_text = "Extract the requested data elements from this PDF document:"
            else:
                prompt_text = "Extract the requested data elements from this image:"
            
            user_message_content = [
                TextContentItem(text=prompt_text),
                ImageContentItem(image_url=ImageUrl(url=image_url))
            ]
            
            # Call vision-capable LLM
            response = self.client.complete(
                messages=[
                    SystemMessage(system_prompt),
                    UserMessage(content=user_message_content)
                ],
                temperature=0.1,
                top_p=0.9,
                model=self.settings.extraction_model
            )
            
            # Parse response
            result_text = response.choices[0].message.content
            extracted_data = self._parse_extraction_result(result_text)
            
            return extracted_data
            
        except Exception as e:
            raise ValueError(f"Vision extraction failed: {str(e)}")
    
    def extract_with_document_intelligence(
        self,
        document_base64: str,
        data_elements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract data using Azure Document Intelligence for OCR preprocessing.
        
        Args:
            document_base64: Base64 encoded document
            data_elements: List of data elements to extract
                
        Returns:
            Dictionary with extracted data, keyed by field name
            
        Raises:
            ValueError: If Document Intelligence is not configured or extraction fails
        """
        if not self.doc_intelligence_client:
            raise ValueError(
                "Azure Document Intelligence not configured. "
                "Add azureDocumentIntelligence section to config.json"
            )
        
        try:
            import base64
            from io import BytesIO
            
            # Decode document
            document_bytes = base64.b64decode(document_base64)
            
            # Analyze document with Document Intelligence (read model)
            poller = self.doc_intelligence_client.begin_analyze_document(
                "prebuilt-read",
                document=BytesIO(document_bytes)
            )
            result = poller.result()
            
            # Extract all text content
            text_content = []
            for page in result.pages:
                page_text = []
                for line in page.lines:
                    page_text.append(line.content)
                if page_text:
                    text_content.append(f"=== Page {page.page_number} ===\n" + "\n".join(page_text))
            
            if not text_content:
                raise ValueError("No text extracted by Document Intelligence")
            
            full_text = "\n\n".join(text_content)
            
            # Use LLM for structured extraction from OCR text
            return self.extract_from_text(full_text, data_elements)
            
        except Exception as e:
            raise ValueError(f"Document Intelligence extraction failed: {str(e)}")
    
    def extract(
        self,
        text: Optional[str],
        data_elements: List[Dict[str, Any]],
        image_data: Optional[Dict[str, Any]] = None,
        document_base64: Optional[str] = None,
        use_document_intelligence: bool = False
    ) -> Dict[str, Any]:
        """Extract data elements using appropriate method.
        
        Args:
            text: Document text content (for text-based extraction)
            data_elements: List of data elements to extract
            image_data: Image data dictionary (for vision-based extraction)
            document_base64: Base64 document (for Document Intelligence)
            use_document_intelligence: Whether to use Azure Document Intelligence
                
        Returns:
            Dictionary with extracted data, keyed by field name
            
        Raises:
            ValueError: If extraction fails or required fields missing
        """
        try:
            # Route to appropriate extraction method
            if use_document_intelligence and document_base64:
                extracted_data = self.extract_with_document_intelligence(
                    document_base64,
                    data_elements
                )
            elif image_data:
                extracted_data = self.extract_from_image(image_data, data_elements)
            elif text:
                extracted_data = self.extract_from_text(text, data_elements)
            else:
                raise ValueError("No valid input provided for extraction")
            
            # Validate required fields
            for element in data_elements:
                if element.get('required', False):
                    field_name = element['name']
                    if field_name not in extracted_data or extracted_data[field_name] is None:
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
            # Try to extract JSON from response
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
    text: Optional[str],
    data_elements: List[Dict[str, Any]],
    settings: Settings,
    image_data: Optional[Dict[str, Any]] = None,
    document_base64: Optional[str] = None,
    use_document_intelligence: bool = False
) -> Dict[str, Any]:
    """Extract structured data from document.
    
    Args:
        text: Document text content
        data_elements: List of data element definitions
        settings: Application settings
        image_data: Image data for vision extraction
        document_base64: Base64 document for Document Intelligence
        use_document_intelligence: Whether to use Azure Document Intelligence
        
    Returns:
        Extracted data dictionary
        
    Raises:
        ValueError: If extraction fails
    """
    extractor = Extractor(settings)
    return extractor.extract(
        text=text,
        data_elements=data_elements,
        image_data=image_data,
        document_base64=document_base64,
        use_document_intelligence=use_document_intelligence
    )
