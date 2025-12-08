"""Anthropic Claude vision implementation."""

import base64
import io
from anthropic import Anthropic
from PIL import Image
from .base import BaseLLM


class AnthropicLLM(BaseLLM):
    """Anthropic Claude provider."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """Initialize Anthropic client.

        Args:
            api_key: Anthropic API key
            model: Model name to use
        """
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string.

        Args:
            image: PIL Image

        Returns:
            Base64 encoded image string
        """
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def extract_from_image(self, image: Image.Image, prompt: str) -> str:
        """Extract structured data from an image using Claude vision.

        Args:
            image: PIL Image to analyze
            prompt: Extraction prompt

        Returns:
            LLM response as string (JSON)
        """
        base64_image = self._image_to_base64(image)

        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=0,  # Deterministic for extraction
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": base64_image,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ],
                }
            ],
        )

        return message.content[0].text
