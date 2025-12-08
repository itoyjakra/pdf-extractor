"""Generate LaTeX documents from extracted Q&A pairs."""

from pathlib import Path
from .schemas import DocumentExtraction, ExtractionResult


class LaTeXGenerator:
    """Generates LaTeX documents from Q&A extractions."""

    PREAMBLE = r"""\documentclass{article}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{amsthm}
\usepackage{graphicx}
\usepackage{geometry}
\geometry{margin=1in}

\title{Extracted Q\&A Pairs}
\date{}

\begin{document}
\maketitle
"""

    POSTAMBLE = r"""
\end{document}
"""

    def __init__(self):
        """Initialize LaTeX generator."""
        pass

    def generate_question_section(self, qa: ExtractionResult) -> str:
        """Generate LaTeX for a single Q&A pair.

        Args:
            qa: Extracted Q&A pair

        Returns:
            LaTeX string for this Q&A
        """
        lines = []

        # Section header
        lines.append(f"\\subsection*{{Question {qa.id}}}")
        lines.append("")

        # Question
        lines.append("\\textbf{Question:} " + qa.question_latex)
        lines.append("")

        # Figures (if any)
        for fig_path in qa.figures:
            lines.append("\\begin{figure}[h]")
            lines.append("  \\centering")
            lines.append(f"  \\includegraphics[width=0.6\\textwidth]{{{fig_path}}}")
            lines.append("\\end{figure}")
            lines.append("")

        # Answer
        lines.append("\\textbf{Answer:} " + qa.answer_latex)
        lines.append("")
        lines.append("\\vspace{1em}")
        lines.append("\\hrule")
        lines.append("\\vspace{1em}")
        lines.append("")

        return "\n".join(lines)

    def generate_document(self, extraction: DocumentExtraction) -> str:
        """Generate complete LaTeX document.

        Args:
            extraction: Complete document extraction

        Returns:
            Full LaTeX document as string
        """
        lines = [self.PREAMBLE]

        # Add metadata as comment
        lines.append(f"% Source: {extraction.source_pdf}")
        lines.append(f"% Extracted: {extraction.extraction_date.isoformat()}")
        lines.append(f"% Model: {extraction.model_used}")
        lines.append(f"% Total Questions: {len(extraction.questions)}")
        lines.append("")

        # Add each Q&A
        for qa in extraction.questions:
            lines.append(self.generate_question_section(qa))

        lines.append(self.POSTAMBLE)

        return "\n".join(lines)

    def save_document(
        self,
        extraction: DocumentExtraction,
        output_path: Path
    ) -> None:
        """Generate and save LaTeX document.

        Args:
            extraction: Complete document extraction
            output_path: Where to save the .tex file
        """
        latex_content = self.generate_document(extraction)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(latex_content)
