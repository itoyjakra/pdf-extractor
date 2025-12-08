"""OpenAI GPT-4o vision implementation."""

import base64
import io
from openai import OpenAI
from PIL import Image
from .base import BaseLLM


class OpenAILLM(BaseLLM):
    """OpenAI GPT-4o provider."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        """Initialize OpenAI client.

        Args:
            api_key: OpenAI API key
            model: Model name to use
        """
        self.client = OpenAI(api_key=api_key)
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
        """Extract structured data from an image using GPT-4o vision.

        Args:
            image: PIL Image to analyze
            prompt: Extraction prompt

        Returns:
            LLM response as string (JSON)
        """
        base64_image = self._image_to_base64(image)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=4096,
            temperature=0,  # Deterministic for extraction
        )

        return response.choices[0].message.content
