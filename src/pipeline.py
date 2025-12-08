"""Main extraction pipeline orchestrator."""

import json
import re
from pathlib import Path
from typing import Optional

from .pdf_processor import PDFProcessor
from .llm_extractor import LLMExtractor
from .latex_generator import LaTeXGenerator
from .reference_resolver import CrossReferenceResolver, ResolutionResult
from .schemas import DocumentExtraction, ExtractionResult, PageExtraction
from .config import Settings


def parse_qa_id(qa_id: str) -> tuple[float, float, str]:
    """Parse a Q&A ID into sortable components.

    Handles IDs like "2.18", "2.18a", "2.18b", "3.4", "10.15c".
    Returns (chapter, question_number, suffix) where suffix is empty string for parent.

    Args:
        qa_id: The question ID string

    Returns:
        Tuple of (chapter_num, question_num, suffix) for sorting
    """
    # Match pattern: optional chapter, dot, question number, optional letter suffix
    match = re.match(r'^(\d+)\.(\d+)([a-z]*)$', qa_id.strip())
    if match:
        chapter = float(match.group(1))
        question = float(match.group(2))
        suffix = match.group(3) or ""  # Empty string for parent questions
        return (chapter, question, suffix)

    # Fallback: try to extract any numbers and sort lexicographically
    return (0.0, 0.0, qa_id)


def sort_qa_list(questions: list[ExtractionResult]) -> list[ExtractionResult]:
    """Sort Q&A list so parent questions come before sub-parts.

    Ensures ordering like: 2.17a, 2.18, 2.18a, 2.18b, 2.18c, 2.19a

    Args:
        questions: List of Q&A pairs

    Returns:
        Sorted list with proper ordering
    """
    return sorted(questions, key=lambda q: parse_qa_id(q.id))


class ExtractionPipeline:
    """Orchestrates the full PDF Q&A extraction pipeline."""

    def __init__(self, settings: Settings, resolve_references: bool = True):
        """Initialize pipeline.

        Args:
            settings: Application settings
            resolve_references: Whether to resolve cross-references
        """
        self.settings = settings
        self.resolve_references = resolve_references
        self.pdf_processor = PDFProcessor(dpi=settings.dpi)
        self.llm_extractor = LLMExtractor.from_settings(settings)
        self.latex_generator = LaTeXGenerator()
        self.reference_resolver = CrossReferenceResolver(self.llm_extractor.llm)

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

        # Process each page with context passing
        all_extractions: list[PageExtraction] = []
        previous_page_context: dict | None = None

        for page_num in range(1, total_pages + 1):
            print(f"Processing page {page_num}/{total_pages}...", end=" ")

            # Convert page to image
            image = self.pdf_processor.convert_page_to_image(pdf_path, page_num)

            # Extract Q&A pairs with context from previous page
            extraction = self.llm_extractor.extract_page(
                image, page_num, previous_page_context
            )
            all_extractions.append(extraction)

            # Build context for next page
            if extraction.questions:
                question_ids = []
                for q in extraction.questions:
                    for p in q.parts:
                        part_id = p.part_id or ""
                        question_ids.append(f"{q.question_id}{part_id}")
                last_q = extraction.questions[-1]
                last_part = last_q.parts[-1] if last_q.parts else None
                last_id = f"{last_q.question_id}{last_part.part_id or ''}" if last_part else last_q.question_id

                previous_page_context = {
                    "questions_summary": ", ".join(question_ids),
                    "last_question_id": last_q.question_id,  # Base ID without part
                    "last_full_id": last_id,
                }
            else:
                previous_page_context = None

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

        print(f"\nTotal Q&A pairs extracted: {len(questions)}")

        # Resolve cross-references
        resolution_results: list[ResolutionResult] = []
        if self.resolve_references and questions:
            print("\nResolving cross-references...")
            resolved_questions, resolution_results = self.reference_resolver.resolve_all(questions)

            # Count resolutions
            refs_found = sum(1 for r in resolution_results if r.had_references)
            refs_resolved = sum(1 for r in resolution_results if r.context_inlined)
            answers_changed = sum(1 for r in resolution_results if r.answer_changed)

            print(f"  Q&As with references: {refs_found}")
            print(f"  References resolved: {refs_resolved}")
            if answers_changed > 0:
                print(f"  [WARNING] Answers modified: {answers_changed}")

            questions = resolved_questions

        # Sort questions so parent questions come before sub-parts (2.18 before 2.18a)
        questions = sort_qa_list(questions)
        print(f"Sorted {len(questions)} Q&A pairs by ID")

        # Create document extraction
        doc_extraction = DocumentExtraction(
            source_pdf=str(pdf_path),
            model_used=f"{self.settings.default_provider}:{self.settings.openai_model if self.settings.default_provider == 'openai' else self.settings.anthropic_model}",
            total_pages=total_pages,
            questions=questions
        )

        # Save JSON output
        json_path = output_dir / "extracted_qas.json"
        with open(json_path, "w") as f:
            json.dump(doc_extraction.to_json_output(), f, indent=2)
        print(f"\nSaved JSON to: {json_path}")

        # Save resolution tracking (for evaluation)
        if resolution_results:
            resolution_path = output_dir / "resolution_results.json"
            resolution_data = {
                "summary": {
                    "total_qas": len(resolution_results),
                    "with_references": sum(1 for r in resolution_results if r.had_references),
                    "resolved": sum(1 for r in resolution_results if r.context_inlined),
                    "answers_modified": sum(1 for r in resolution_results if r.answer_changed),
                },
                "details": [
                    {
                        "id": r.original.id,
                        "had_references": r.had_references,
                        "references_found": r.references_found,
                        "context_inlined": r.context_inlined,
                        "answer_changed": r.answer_changed,
                        "original_question": r.original.question_latex if r.had_references else None,
                        "resolved_question": r.resolved.question_latex if r.context_inlined else None,
                    }
                    for r in resolution_results
                    if r.had_references
                ]
            }
            with open(resolution_path, "w") as f:
                json.dump(resolution_data, f, indent=2)
            print(f"Saved resolution tracking to: {resolution_path}")

        # Generate and save LaTeX
        latex_path = output_dir / "extracted_qas.tex"
        self.latex_generator.save_document(doc_extraction, latex_path)
        print(f"Saved LaTeX to: {latex_path}")

        return doc_extraction
