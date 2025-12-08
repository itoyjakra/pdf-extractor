"""Pydantic models for Q&A extraction."""

from datetime import datetime
from pydantic import BaseModel, Field


class Figure(BaseModel):
    """A figure/diagram extracted from the PDF."""

    figure_id: str = Field(description="Unique identifier for the figure")
    bbox: tuple[float, float, float, float] | None = Field(
        default=None,
        description="Bounding box (x1, y1, x2, y2) in page coordinates"
    )
    path: str | None = Field(default=None, description="Path to extracted image file")
    description: str | None = Field(default=None, description="Brief description of the figure")


class QuestionPart(BaseModel):
    """A single part of a question (or the whole question if no parts)."""

    part_id: str | None = Field(
        default=None,
        description="Part identifier (e.g., 'a', 'b', 'c') or None if no parts"
    )
    question_latex: str = Field(description="Question text in LaTeX format")
    answer_latex: str = Field(description="Answer/solution text in LaTeX format")
    figures: list[Figure] = Field(default_factory=list, description="Figures for this part")
    continues_next_page: bool = Field(
        default=False,
        description="Whether this Q&A continues on the next page"
    )
    continued_from_previous: bool = Field(
        default=False,
        description="Whether this is a continuation from the previous page"
    )


class Question(BaseModel):
    """A complete question with all its parts."""

    question_id: str = Field(description="Question number (e.g., '2.7', '2.8')")
    parts: list[QuestionPart] = Field(description="Question parts (or single part if no sub-parts)")
    page_range: tuple[int, int] = Field(description="(start_page, end_page) 1-indexed")


class PageExtraction(BaseModel):
    """Extraction result from a single page."""

    page_number: int = Field(description="1-indexed page number")
    questions: list[Question] = Field(default_factory=list, description="Questions found on this page")
    raw_text: str | None = Field(default=None, description="Raw text extracted (for debugging)")


class ExtractionResult(BaseModel):
    """A single Q&A pair ready for output."""

    id: str = Field(description="Full ID including part (e.g., '2.8a')")
    question_latex: str = Field(description="Complete question in LaTeX")
    answer_latex: str = Field(description="Complete answer in LaTeX")
    figures: list[str] = Field(default_factory=list, description="Paths to figure images")
    page_range: tuple[int, int] = Field(description="Source pages (start, end)")


class DocumentExtraction(BaseModel):
    """Complete extraction result for a document."""

    source_pdf: str = Field(description="Path to source PDF")
    extraction_date: datetime = Field(default_factory=datetime.now)
    model_used: str = Field(description="LLM model used for extraction")
    total_pages: int = Field(description="Total pages in PDF")
    questions: list[ExtractionResult] = Field(description="All extracted Q&A pairs")

    def to_json_output(self) -> dict:
        """Convert to JSON-serializable output format."""
        return {
            "metadata": {
                "source_pdf": self.source_pdf,
                "extraction_date": self.extraction_date.isoformat(),
                "total_questions": len(self.questions),
                "total_pages": self.total_pages,
                "model_used": self.model_used,
            },
            "questions": [q.model_dump() for q in self.questions]
        }
