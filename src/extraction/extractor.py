"""Data extraction using Azure AI Foundry models and Azure Document Intelligence."""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from azure.ai.formrecognizer.aio import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from openai import AsyncAzureOpenAI
from agent_framework.openai import OpenAIChatClient
from agent_framework._types import ChatMessage, DataContent, TextContent

from ..config.settings import Settings
from ..exceptions import (
    DocumentIntelligenceError,
    DocumentIntelligenceNotConfiguredError,
    ExtractionError,
    InvalidExtractionResultError,
    RequiredFieldMissingError,
    TextExtractionError,
    VisionExtractionError,
)


log = logging.getLogger(__name__)


@dataclass
class ExtractionHelpers:
    """Bundle helper components for the extraction workflow."""

    chat_client: OpenAIChatClient
    async_openai_client: AsyncAzureOpenAI
    document_intelligence_client: Optional[DocumentAnalysisClient]
    prompt_template: str


@dataclass
class ExtractionPayload:
    """Structured extraction output with optional document content."""

    data: Dict[str, Any]
    document_content: Optional[str]


class ChatClientFactory:
    """Create Azure AI chat clients with consistent configuration."""

    def __init__(self, settings: Settings):
        self._settings = settings

    def create(self) -> tuple[OpenAIChatClient, AsyncAzureOpenAI]:
        """Create OpenAIChatClient with Azure AD authentication.
        
        Returns:
            OpenAIChatClient configured for Azure AI Foundry
        """
        # Create async token provider for Azure AD authentication
        async def get_azure_ad_token() -> str:
            """Get Azure AD token for OpenAI API authentication."""
            token = self._settings.azure_credential.get_token(
                "https://cognitiveservices.azure.com/.default"
            )
            return token.token
        
        # Create AsyncAzureOpenAI client with token provider
        azure_client = AsyncAzureOpenAI(
            azure_endpoint=self._settings.azure_ai_foundry_endpoint,
            azure_ad_token_provider=get_azure_ad_token,
            api_version="2024-02-01",  # Azure OpenAI API version
        )
        
        # Create OpenAIChatClient with the Azure client
        chat_client = OpenAIChatClient(
            model_id=self._settings.extraction_model,
            async_client=azure_client,
        )

        return chat_client, azure_client


class DocumentIntelligenceFactory:
    """Create Document Intelligence clients when configuration is available."""

    def __init__(self, settings: Settings):
        self._settings = settings

    def create(self) -> Optional[DocumentAnalysisClient]:
        config = self._settings.azure_document_intelligence
        if not config or not config.endpoint:
            return None

        if config.use_managed_identity:
            return DocumentAnalysisClient(
                endpoint=config.endpoint,
                credential=self._settings.azure_credential,
            )

        if config.key:
            return DocumentAnalysisClient(
                endpoint=config.endpoint,
                credential=AzureKeyCredential(config.key),
            )

        return None


class PromptBuilder:
    """Compose prompts for extraction tasks."""

    def __init__(self, template: str):
        self._template = template

    def build(self, data_elements: List[Dict[str, Any]]) -> str:
        element_descriptions = []
        for element in data_elements:
            required_text = " (REQUIRED)" if element.get("required", False) else ""
            element_descriptions.append(
                f"- {element['name']}: {element['description']} "
                f"[format: {element.get('format', 'string')}]"
                f"{required_text}"
            )

        elements_text = "\n".join(element_descriptions)
        return self._template.replace("{elements}", elements_text)


class ExtractionResultParser:
    """Parse LLM responses into structured results."""

    @staticmethod
    def parse(result_text: str) -> Dict[str, Any]:
        try:
            result_text = result_text.strip()
            start_idx = result_text.find("{")
            end_idx = result_text.rfind("}")

            if start_idx == -1 or end_idx == -1:
                raise InvalidExtractionResultError("No JSON object found in response")

            json_text = result_text[start_idx : end_idx + 1]
            return json.loads(json_text)

        except json.JSONDecodeError as exc:
            raise InvalidExtractionResultError(
                f"Failed to parse extraction result as JSON: {exc}"
            ) from exc


def build_helpers(settings: Settings) -> ExtractionHelpers:
    """Construct helper bundle for the extractor."""

    chat_client, async_openai_client = ChatClientFactory(settings).create()
    doc_intel_client = DocumentIntelligenceFactory(settings).create()
    return ExtractionHelpers(
        chat_client=chat_client,
        async_openai_client=async_openai_client,
        document_intelligence_client=doc_intel_client,
        prompt_template=settings.extraction_prompt,
    )


class Extractor:
    """Extract structured data from document text using LLM."""

    def __init__(self, settings: Settings):
        """Initialize extractor with helper bundle."""

        self.settings = settings
        helpers = build_helpers(settings)
        self.client = helpers.chat_client
        self._async_openai_client = helpers.async_openai_client
        self.doc_intelligence_client = helpers.document_intelligence_client
        self.prompt_builder = PromptBuilder(helpers.prompt_template)
        self.result_parser = ExtractionResultParser()

    async def aclose(self) -> None:
        """Close any underlying async clients."""
        try:
            await self._async_openai_client.close()
        except AttributeError:  # pragma: no cover - defensive
            pass

        if self.doc_intelligence_client is not None:
            await self.doc_intelligence_client.close()

    async def extract_from_text(
        self,
        text: str,
        data_elements: List[Dict[str, Any]],
    ) -> ExtractionPayload:
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
            system_prompt = self.prompt_builder.build(data_elements)
            user_prompt = f"Document text:\n\n{text}\n\nExtract the requested data elements."
            
            # Call LLM for extraction using Agent Framework OpenAI client
            response = await self.client.get_response(
                messages=[
                    ChatMessage("system", text=system_prompt),
                    ChatMessage("user", text=user_prompt)
                ],
                temperature=0.1,  # Low temperature for consistent extraction
                top_p=0.9,
            )
            
            # Parse response - ChatResponse has a text attribute
            result_text = response.text or ""
            extracted_data = self.result_parser.parse(result_text)
            
            return ExtractionPayload(data=extracted_data, document_content=text)
            
        except InvalidExtractionResultError:
            raise
        except Exception as exc:
            log.exception("Text extraction failed")
            raise TextExtractionError(f"Text extraction failed: {exc}") from exc
    
    async def extract_from_image(
        self,
        image_data: Dict[str, Any],
        data_elements: List[Dict[str, Any]],
    ) -> ExtractionPayload:
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
            system_prompt = self.prompt_builder.build(data_elements)
            
            # Create vision message with image or PDF
            media_type = image_data['media_type']
            image_url = f"data:{media_type};base64,{image_data['base64_data']}"
            
            # Adjust prompt text based on document type
            if media_type == "application/pdf":
                prompt_text = "Extract the requested data elements from this PDF document:"
            else:
                prompt_text = "Extract the requested data elements from this image:"
            
            # Call vision-capable LLM using Agent Framework OpenAI client
            # Use ChatMessage with contents array for multimodal input
            response = await self.client.get_response(
                messages=[
                    ChatMessage("system", text=system_prompt),
                    ChatMessage(
                        "user",
                        contents=[
                            TextContent(text=prompt_text),
                            DataContent(uri=image_url, media_type=media_type)
                        ]
                    )
                ],
                temperature=0.1,
                top_p=0.9,
            )
            
            # Parse response - ChatResponse has a text attribute
            result_text = response.text or ""
            extracted_data = self.result_parser.parse(result_text)

            doc_descriptor = (
                f"[Vision document] media={media_type} "
                f"type={image_data.get('document_type', image_data.get('format', 'unknown'))} "
                f"width={image_data.get('width', 'n/a')} "
                f"height={image_data.get('height', 'n/a')}"
            )
            
            return ExtractionPayload(data=extracted_data, document_content=doc_descriptor)
            
        except InvalidExtractionResultError:
            raise
        except Exception as exc:
            log.exception("Vision extraction failed")
            raise VisionExtractionError(f"Vision extraction failed: {exc}") from exc
    
    async def extract_with_document_intelligence(
        self,
        document_base64: str,
        data_elements: List[Dict[str, Any]],
    ) -> ExtractionPayload:
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
            raise DocumentIntelligenceNotConfiguredError(
                "Azure Document Intelligence not configured. "
                "Set AZURE_DOCUMENT_INTELLIGENCE_* values in your .env",
            )
        
        try:
            import base64
            from io import BytesIO
            
            # Decode document
            document_bytes = base64.b64decode(document_base64)
            
            # Analyze document with Document Intelligence (read model)
            poller = await self.doc_intelligence_client.begin_analyze_document(
                "prebuilt-read",
                document=BytesIO(document_bytes)
            )
            result = await poller.result()
            
            # Extract all text content
            text_content = []
            for page in result.pages:
                page_text = []
                for line in page.lines:
                    page_text.append(line.content)
                if page_text:
                    text_content.append(f"=== Page {page.page_number} ===\n" + "\n".join(page_text))
            
            if not text_content:
                raise DocumentIntelligenceError("No text extracted by Document Intelligence")
            
            full_text = "\n\n".join(text_content)
            
            # Use LLM for structured extraction from OCR text
            extraction_payload = await self.extract_from_text(full_text, data_elements)
            return extraction_payload
            
        except DocumentIntelligenceNotConfiguredError:
            raise
        except DocumentIntelligenceError:
            raise
        except TextExtractionError:
            raise
        except InvalidExtractionResultError:
            raise
        except Exception as exc:
            log.exception("Document Intelligence extraction failed")
            raise DocumentIntelligenceError(
                f"Document Intelligence extraction failed: {exc}"
            ) from exc
    
    async def extract(
        self,
        text: Optional[str],
        data_elements: List[Dict[str, Any]],
        image_data: Optional[Dict[str, Any]] = None,
        document_base64: Optional[str] = None,
        use_document_intelligence: bool = False,
    ) -> ExtractionPayload:
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
                payload = await self.extract_with_document_intelligence(
                    document_base64,
                    data_elements,
                )
            elif image_data:
                payload = await self.extract_from_image(image_data, data_elements)
            elif text:
                payload = await self.extract_from_text(text, data_elements)
            else:
                raise ExtractionError("No valid input provided for extraction")
            
            # Validate required fields
            for element in data_elements:
                if element.get('required', False):
                    field_name = element['name']
                    if field_name not in payload.data or payload.data[field_name] is None:
                        field_description = element.get('description')
                        raise RequiredFieldMissingError(field_name, field_description)
            
            return payload
            
        except (DocumentIntelligenceNotConfiguredError, DocumentIntelligenceError,
                TextExtractionError, VisionExtractionError, InvalidExtractionResultError,
                RequiredFieldMissingError, ExtractionError):
            raise
        except Exception as exc:
            log.exception("Extraction pipeline failed")
            raise ExtractionError(f"Extraction failed: {exc}") from exc
    
