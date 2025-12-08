"""Evaluation pipeline for extraction quality assessment."""

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image
import numpy as np

from .schemas import ExtractionResult


@dataclass
class ComparisonResult:
    """Result of comparing two images or texts."""
    score: float  # 0.0 to 1.0
    passed: bool
    details: str


@dataclass
class QAEvaluation:
    """Evaluation result for a single Q&A pair."""
    qa_id: str
    latex_compiles: bool
    answer_similarity: Optional[float]  # Only for resolved Q&As
    answer_exact_match: Optional[bool]
    has_remaining_refs: bool
    visual_similarity: Optional[float]
    overall_passed: bool
    review_priority: str  # "none", "low", "medium", "high"
    notes: list[str]


@dataclass
class EvaluationReport:
    """Complete evaluation report."""
    total_qas: int
    passed: int
    failed: int
    needs_review: int
    qa_evaluations: list[QAEvaluation]
    summary: dict


class Evaluator:
    """Evaluates extraction quality."""

    # Common cross-reference patterns to check for remaining refs
    REF_PATTERNS = [
        r"theorem\s+\d+",
        r"lemma\s+\d+",
        r"corollary\s+\d+",
        r"proposition\s+\d+",
        r"remark\s+\d+",
        r"example\s+\d+",
        r"definition\s+\d+",
        r"exercise\s+\d+",
        r"problem\s+\d+",
        r"equation\s*\(\d+",
        r"section\s+\d+",
        r"chapter\s+\d+",
        r"page\s+\d+",
        r"see\s+\(\d+",
        r"from\s+\(\d+",
    ]

    def __init__(self, output_dir: Path):
        """Initialize evaluator.

        Args:
            output_dir: Directory for evaluation outputs
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def normalize_latex(self, latex: str) -> str:
        """Normalize LaTeX for comparison.

        Removes formatting differences that don't affect meaning.

        Args:
            latex: Raw LaTeX string

        Returns:
            Normalized string
        """
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', latex.strip())

        # Normalize common LaTeX variations
        text = text.replace(r'\left(', '(')
        text = text.replace(r'\right)', ')')
        text = text.replace(r'\left[', '[')
        text = text.replace(r'\right]', ']')
        text = text.replace(r'\left\{', r'\{')
        text = text.replace(r'\right\}', r'\}')

        # Normalize spacing around operators
        text = re.sub(r'\s*=\s*', '=', text)
        text = re.sub(r'\s*\+\s*', '+', text)
        text = re.sub(r'\s*-\s*', '-', text)

        return text

    def compute_text_similarity(self, text1: str, text2: str) -> float:
        """Compute similarity between two text strings.

        Uses character-level Levenshtein ratio.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score 0.0 to 1.0
        """
        if text1 == text2:
            return 1.0

        if not text1 or not text2:
            return 0.0

        # Simple character-level similarity
        # (Could use difflib.SequenceMatcher for more sophisticated matching)
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1, text2).ratio()

    def check_remaining_references(self, qa: ExtractionResult) -> list[str]:
        """Check if Q&A still contains cross-references.

        Args:
            qa: Q&A to check

        Returns:
            List of found reference patterns
        """
        found = []
        text = qa.question_latex.lower() + " " + qa.answer_latex.lower()

        for pattern in self.REF_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            found.extend(matches)

        return found

    def compile_latex_snippet(self, latex: str, output_path: Path) -> bool:
        """Compile a LaTeX snippet to PDF.

        Args:
            latex: LaTeX content
            output_path: Where to save the PDF

        Returns:
            True if compilation succeeded
        """
        # Create a minimal document
        document = r"""\documentclass{article}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{amsthm}
\pagestyle{empty}
\begin{document}
""" + latex + r"""
\end{document}
"""
        tex_path = output_path.with_suffix('.tex')
        tex_path.write_text(document)

        try:
            result = subprocess.run(
                [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    "-output-directory", str(output_path.parent),
                    str(tex_path)
                ],
                capture_output=True,
                timeout=30
            )
            return output_path.exists()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def compute_ssim(self, img1: Image.Image, img2: Image.Image) -> float:
        """Compute Structural Similarity Index between two images.

        Args:
            img1: First image
            img2: Second image

        Returns:
            SSIM score 0.0 to 1.0
        """
        try:
            from skimage.metrics import structural_similarity as ssim

            # Convert to grayscale numpy arrays
            arr1 = np.array(img1.convert('L'))
            arr2 = np.array(img2.convert('L'))

            # Resize if needed
            if arr1.shape != arr2.shape:
                # Resize arr2 to match arr1
                img2_resized = img2.convert('L').resize(img1.size)
                arr2 = np.array(img2_resized)

            return ssim(arr1, arr2)
        except ImportError:
            # Fallback if skimage not available
            return -1.0

    def evaluate_qa(
        self,
        qa: ExtractionResult,
        original_qa: Optional[ExtractionResult] = None,
        was_resolved: bool = False
    ) -> QAEvaluation:
        """Evaluate a single Q&A pair.

        Args:
            qa: Q&A to evaluate
            original_qa: Original Q&A before resolution (if resolved)
            was_resolved: Whether cross-reference resolution was applied

        Returns:
            Evaluation result
        """
        notes = []
        answer_similarity = None
        answer_exact_match = None
        visual_similarity = None
        review_priority = "none"

        # Check for remaining references
        remaining_refs = self.check_remaining_references(qa)
        has_remaining_refs = len(remaining_refs) > 0
        if has_remaining_refs:
            notes.append(f"Remaining references: {remaining_refs[:3]}")
            review_priority = "medium"

        # Check LaTeX compilation
        eval_dir = self.output_dir / "eval_temp"
        eval_dir.mkdir(exist_ok=True)

        qa_latex = f"\\textbf{{Question:}} {qa.question_latex}\n\n\\textbf{{Answer:}} {qa.answer_latex}"
        pdf_path = eval_dir / f"{qa.id}.pdf"
        latex_compiles = self.compile_latex_snippet(qa_latex, pdf_path)

        if not latex_compiles:
            notes.append("LaTeX compilation failed")
            review_priority = "high"

        # If resolved, compare answers
        if was_resolved and original_qa:
            orig_normalized = self.normalize_latex(original_qa.answer_latex)
            resolved_normalized = self.normalize_latex(qa.answer_latex)

            answer_exact_match = orig_normalized == resolved_normalized
            answer_similarity = self.compute_text_similarity(
                orig_normalized, resolved_normalized
            )

            if answer_similarity < 0.95:
                notes.append(f"Answer changed significantly: {answer_similarity:.2%}")
                review_priority = "high"
            elif answer_similarity < 0.99:
                notes.append(f"Minor answer changes: {answer_similarity:.2%}")
                if review_priority == "none":
                    review_priority = "low"

        # Determine if passed
        overall_passed = (
            latex_compiles and
            not has_remaining_refs and
            (answer_similarity is None or answer_similarity >= 0.95)
        )

        return QAEvaluation(
            qa_id=qa.id,
            latex_compiles=latex_compiles,
            answer_similarity=answer_similarity,
            answer_exact_match=answer_exact_match,
            has_remaining_refs=has_remaining_refs,
            visual_similarity=visual_similarity,
            overall_passed=overall_passed,
            review_priority=review_priority,
            notes=notes
        )

    def evaluate_extraction(
        self,
        extracted_qas: list[ExtractionResult],
        resolution_results: Optional[dict] = None
    ) -> EvaluationReport:
        """Evaluate all extracted Q&As.

        Args:
            extracted_qas: List of extracted Q&A pairs
            resolution_results: Resolution tracking data (if available)

        Returns:
            Complete evaluation report
        """
        evaluations = []
        passed = 0
        failed = 0
        needs_review = 0

        # Build map of original Q&As from resolution results
        original_map = {}
        resolved_ids = set()
        if resolution_results:
            for detail in resolution_results.get("details", []):
                if detail.get("context_inlined"):
                    resolved_ids.add(detail["id"])
                    # Store original question if available
                    if detail.get("original_question"):
                        original_map[detail["id"]] = detail

        for qa in extracted_qas:
            was_resolved = qa.id in resolved_ids

            # Create original QA for comparison if we have the data
            original_qa = None
            if was_resolved and qa.id in original_map:
                orig_data = original_map[qa.id]
                original_qa = ExtractionResult(
                    id=qa.id,
                    question_latex=orig_data.get("original_question", ""),
                    answer_latex=qa.answer_latex,  # Answers should be same
                    figures=[],
                    page_range=qa.page_range
                )

            evaluation = self.evaluate_qa(qa, original_qa, was_resolved)
            evaluations.append(evaluation)

            if evaluation.overall_passed:
                passed += 1
            else:
                failed += 1

            if evaluation.review_priority in ("medium", "high"):
                needs_review += 1

        # Generate summary
        summary = {
            "pass_rate": passed / len(extracted_qas) if extracted_qas else 0,
            "resolved_count": len(resolved_ids),
            "compilation_failures": sum(1 for e in evaluations if not e.latex_compiles),
            "remaining_refs": sum(1 for e in evaluations if e.has_remaining_refs),
            "answer_changes": sum(
                1 for e in evaluations
                if e.answer_similarity is not None and e.answer_similarity < 0.99
            ),
            "high_priority_reviews": sum(
                1 for e in evaluations if e.review_priority == "high"
            ),
        }

        return EvaluationReport(
            total_qas=len(extracted_qas),
            passed=passed,
            failed=failed,
            needs_review=needs_review,
            qa_evaluations=evaluations,
            summary=summary
        )

    def save_report(self, report: EvaluationReport, output_path: Path) -> None:
        """Save evaluation report to JSON.

        Args:
            report: Evaluation report
            output_path: Where to save
        """
        data = {
            "summary": {
                "total_qas": report.total_qas,
                "passed": report.passed,
                "failed": report.failed,
                "needs_review": report.needs_review,
                **report.summary
            },
            "evaluations": [
                {
                    "qa_id": e.qa_id,
                    "latex_compiles": e.latex_compiles,
                    "answer_similarity": e.answer_similarity,
                    "answer_exact_match": e.answer_exact_match,
                    "has_remaining_refs": e.has_remaining_refs,
                    "visual_similarity": e.visual_similarity,
                    "overall_passed": e.overall_passed,
                    "review_priority": e.review_priority,
                    "notes": e.notes,
                }
                for e in report.qa_evaluations
            ]
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

    def print_report(self, report: EvaluationReport) -> None:
        """Print evaluation report to console.

        Args:
            report: Evaluation report
        """
        print("\n" + "=" * 60)
        print("EVALUATION REPORT")
        print("=" * 60)
        print(f"Total Q&As: {report.total_qas}")
        print(f"Passed: {report.passed} ({report.passed/report.total_qas:.1%})")
        print(f"Failed: {report.failed}")
        print(f"Needs Review: {report.needs_review}")
        print()
        print("Summary:")
        for key, value in report.summary.items():
            print(f"  {key}: {value}")
        print()

        # Show high priority items
        high_priority = [e for e in report.qa_evaluations if e.review_priority == "high"]
        if high_priority:
            print("HIGH PRIORITY REVIEWS:")
            for e in high_priority[:10]:
                print(f"  - {e.qa_id}: {', '.join(e.notes)}")
            if len(high_priority) > 10:
                print(f"  ... and {len(high_priority) - 10} more")
        print("=" * 60)
