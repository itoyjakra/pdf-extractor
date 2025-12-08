"""Main extraction pipeline orchestrator."""

import json
from pathlib import Path
from typing import Optional

from .pdf_processor import PDFProcessor
from .llm_extractor import LLMExtractor
from .latex_generator import LaTeXGenerator
from .schemas import DocumentExtraction, ExtractionResult, PageExtraction
from .config import Settings


class ExtractionPipeline:
    """Orchestrates the full PDF Q&A extraction pipeline."""

    def __init__(self, settings: Settings):
        """Initialize pipeline.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.pdf_processor = PDFProcessor(dpi=settings.dpi)
        self.llm_extractor = LLMExtractor.from_settings(settings)
        self.latex_generator = LaTeXGenerator()

    def process_pdf(
        self,
        pdf_path: Path,
        output_dir: Optional[Path] = None
    ) -> DocumentExtraction:
        """Process a PDF and extract all Q&A pairs.

        Args:
            pdf_path: Path to input PDF
            output_dir: Output directory (defaults to settings.output_dir)

        Returns:
            Complete document extraction
        """
        if output_dir is None:
            output_dir = Path(self.settings.output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"Processing PDF: {pdf_path}")

        # Get page count
        total_pages = self.pdf_processor.get_page_count(pdf_path)
        print(f"Total pages: {total_pages}")

        # Process each page
        all_extractions: list[PageExtraction] = []

        for page_num in range(1, total_pages + 1):
            print(f"Processing page {page_num}/{total_pages}...", end=" ")

            # Convert page to image
            image = self.pdf_processor.convert_page_to_image(pdf_path, page_num)

            # Extract Q&A pairs
            extraction = self.llm_extractor.extract_page(image, page_num)
            all_extractions.append(extraction)

            print(f"Found {len(extraction.questions)} questions")

        # Flatten to individual Q&A pairs
        questions = []
        for page_extraction in all_extractions:
            for question in page_extraction.questions:
                for part in question.parts:
                    # Build full ID
                    if part.part_id:
                        full_id = f"{question.question_id}{part.part_id}"
                    else:
                        full_id = question.question_id

                    qa = ExtractionResult(
                        id=full_id,
                        question_latex=part.question_latex,
                        answer_latex=part.answer_latex,
                        figures=[],  # MVP: no figure extraction yet
                        page_range=question.page_range
                    )
                    questions.append(qa)

        # Create document extraction
        doc_extraction = DocumentExtraction(
            source_pdf=str(pdf_path),
            model_used=f"{self.settings.default_provider}:{self.settings.openai_model if self.settings.default_provider == 'openai' else self.settings.anthropic_model}",
            total_pages=total_pages,
            questions=questions
        )

        print(f"\nTotal Q&A pairs extracted: {len(questions)}")

        # Save JSON output
        json_path = output_dir / "extracted_qas.json"
        with open(json_path, "w") as f:
            json.dump(doc_extraction.to_json_output(), f, indent=2)
        print(f"Saved JSON to: {json_path}")

        # Generate and save LaTeX
        latex_path = output_dir / "extracted_qas.tex"
        self.latex_generator.save_document(doc_extraction, latex_path)
        print(f"Saved LaTeX to: {latex_path}")

        return doc_extraction
