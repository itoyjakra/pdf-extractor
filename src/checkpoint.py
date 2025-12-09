"""Checkpoint management for resumable extraction."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .schemas import PageExtraction


class Checkpoint:
    """Manages checkpoint state for resumable PDF extraction."""

    def __init__(self, checkpoint_path: Path):
        """Initialize checkpoint manager.

        Args:
            checkpoint_path: Path to checkpoint file
        """
        self.checkpoint_path = checkpoint_path

    def save(
        self,
        pdf_path: Path,
        total_pages: int,
        last_processed_page: int,
        all_extractions: list[PageExtraction],
        previous_page_context: dict | None,
        resolve_references: bool,
    ) -> None:
        """Save checkpoint to disk.

        Args:
            pdf_path: Path to the PDF being processed
            total_pages: Total number of pages in PDF
            last_processed_page: Last page that was successfully processed
            all_extractions: All page extractions so far
            previous_page_context: Context from last processed page
            resolve_references: Whether cross-reference resolution is enabled
        """
        checkpoint_data = {
            "pdf_path": str(pdf_path.absolute()),
            "total_pages": total_pages,
            "last_processed_page": last_processed_page,
            "timestamp": datetime.now().isoformat(),
            "resolve_references": resolve_references,
            "previous_page_context": previous_page_context,
            "all_extractions": [
                {
                    "page_number": pe.page_number,
                    "questions": [
                        {
                            "question_id": q.question_id,
                            "page_range": list(q.page_range),
                            "parts": [
                                {
                                    "part_id": p.part_id,
                                    "question_latex": p.question_latex,
                                    "answer_latex": p.answer_latex,
                                    "figures": [f.model_dump() for f in p.figures],
                                    "continues_next_page": p.continues_next_page,
                                    "continued_from_previous": p.continued_from_previous,
                                }
                                for p in q.parts
                            ],
                        }
                        for q in pe.questions
                    ],
                }
                for pe in all_extractions
            ],
        }

        # Write atomically using temp file
        temp_path = self.checkpoint_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(checkpoint_data, f, indent=2)
        temp_path.replace(self.checkpoint_path)

    def load(self) -> Optional[dict]:
        """Load checkpoint from disk.

        Returns:
            Checkpoint data dict or None if no checkpoint exists
        """
        if not self.checkpoint_path.exists():
            return None

        with open(self.checkpoint_path) as f:
            return json.load(f)

    def exists(self) -> bool:
        """Check if a checkpoint exists.

        Returns:
            True if checkpoint file exists
        """
        return self.checkpoint_path.exists()

    def delete(self) -> None:
        """Delete the checkpoint file."""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()

    def get_summary(self) -> Optional[str]:
        """Get a human-readable summary of the checkpoint.

        Returns:
            Summary string or None if no checkpoint
        """
        data = self.load()
        if not data:
            return None

        timestamp = datetime.fromisoformat(data["timestamp"])
        progress_pct = (data["last_processed_page"] / data["total_pages"]) * 100

        return (
            f"Found checkpoint from {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"  PDF: {Path(data['pdf_path']).name}\n"
            f"  Progress: {data['last_processed_page']}/{data['total_pages']} pages ({progress_pct:.1f}%)\n"
            f"  Extracted Q&As: {sum(len(pe['questions']) for pe in data['all_extractions'])}"
        )

    @staticmethod
    def restore_page_extractions(checkpoint_data: dict) -> list[PageExtraction]:
        """Restore PageExtraction objects from checkpoint data.

        Args:
            checkpoint_data: Loaded checkpoint dict

        Returns:
            List of PageExtraction objects
        """
        from .schemas import Question, QuestionPart, Figure

        all_extractions = []
        for pe_data in checkpoint_data["all_extractions"]:
            questions = []
            for q_data in pe_data["questions"]:
                parts = []
                for p_data in q_data["parts"]:
                    figures = [Figure(**fig_data) for fig_data in p_data["figures"]]
                    part = QuestionPart(
                        part_id=p_data["part_id"],
                        question_latex=p_data["question_latex"],
                        answer_latex=p_data["answer_latex"],
                        figures=figures,
                        continues_next_page=p_data["continues_next_page"],
                        continued_from_previous=p_data["continued_from_previous"],
                    )
                    parts.append(part)

                question = Question(
                    question_id=q_data["question_id"],
                    parts=parts,
                    page_range=tuple(q_data["page_range"]),
                )
                questions.append(question)

            page_extraction = PageExtraction(
                page_number=pe_data["page_number"],
                questions=questions,
            )
            all_extractions.append(page_extraction)

        return all_extractions
