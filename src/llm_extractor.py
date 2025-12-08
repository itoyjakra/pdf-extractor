"""LLM-based extraction of Q&A pairs from PDF page images."""

import json
from pathlib import Path
from PIL import Image
from typing import Optional

from .models import BaseLLM, OpenAILLM, AnthropicLLM
from .schemas import PageExtraction, Question, QuestionPart
from .config import Settings


class LLMExtractor:
    """Extracts Q&A pairs from page images using vision LLM."""

    def __init__(self, llm: BaseLLM, prompt_path: Optional[Path] = None):
        """Initialize extractor.

        Args:
            llm: LLM provider instance
            prompt_path: Path to extraction prompt (defaults to prompts/extraction.md)
        """
        self.llm = llm

        if prompt_path is None:
            prompt_path = Path(__file__).parent.parent / "prompts" / "extraction.md"

        self.prompt_template = prompt_path.read_text()

    def extract_page(self, image: Image.Image, page_number: int) -> PageExtraction:
        """Extract Q&A pairs from a single page image.

        Args:
            image: Page image
            page_number: Page number (1-indexed)

        Returns:
            PageExtraction with all questions found
        """
        # Get LLM response
        response = self.llm.extract_from_image(image, self.prompt_template)

        # Parse JSON response
        try:
            # Try to extract JSON from response (in case LLM adds explanation)
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)

            # Convert to Pydantic models
            questions = []
            for q_data in data.get("questions", []):
                parts = []
                for p_data in q_data.get("parts", []):
                    part = QuestionPart(
                        part_id=p_data.get("part_id"),
                        question_latex=p_data.get("question_latex", ""),
                        answer_latex=p_data.get("answer_latex", ""),
                        continues_next_page=p_data.get("continues_next_page", False),
                        continued_from_previous=p_data.get("continued_from_previous", False),
                    )
                    parts.append(part)

                question = Question(
                    question_id=q_data.get("question_id", ""),
                    parts=parts,
                    page_range=(page_number, page_number)
                )
                questions.append(question)

            return PageExtraction(
                page_number=page_number,
                questions=questions,
            )

        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response: {e}")
            print(f"Raw response: {response}")
            return PageExtraction(page_number=page_number, questions=[])

    @classmethod
    def from_settings(cls, settings: Settings) -> "LLMExtractor":
        """Create extractor from settings.

        Args:
            settings: Application settings

        Returns:
            LLMExtractor instance
        """
        if settings.default_provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key not set")
            llm = OpenAILLM(
                api_key=settings.openai_api_key,
                model=settings.openai_model
            )
        elif settings.default_provider == "anthropic":
            if not settings.anthropic_api_key:
                raise ValueError("Anthropic API key not set")
            llm = AnthropicLLM(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model
            )
        else:
            raise ValueError(f"Unknown provider: {settings.default_provider}")

        return cls(llm)
