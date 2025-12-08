"""Base interface for LLM providers."""

from abc import ABC, abstractmethod
from pathlib import Path
from PIL import Image


class BaseLLM(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    def extract_from_image(self, image: Image.Image, prompt: str) -> str:
        """Extract structured data from an image using vision LLM.

        Args:
            image: PIL Image to analyze
            prompt: Extraction prompt

        Returns:
            LLM response as string (expected to be JSON)
        """
        pass
