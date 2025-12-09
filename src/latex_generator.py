"""Generate LaTeX documents from extracted Q&A pairs."""

import subprocess
import tempfile
from pathlib import Path
from typing import NamedTuple

from .schemas import DocumentExtraction, ExtractionResult


class CompilationResult(NamedTuple):
    """Result of LaTeX compilation attempt."""
    success: bool
    pdf_path: Path | None
    errors: list[str]
    warnings: list[str]

# Unicode to LaTeX mapping for common math symbols
UNICODE_TO_LATEX = {
    # Greek letters
    "α": r"\alpha",
    "β": r"\beta",
    "γ": r"\gamma",
    "δ": r"\delta",
    "ε": r"\epsilon",
    "ζ": r"\zeta",
    "η": r"\eta",
    "θ": r"\theta",
    "ι": r"\iota",
    "κ": r"\kappa",
    "λ": r"\lambda",
    "μ": r"\mu",
    "ν": r"\nu",
    "ξ": r"\xi",
    "π": r"\pi",
    "ρ": r"\rho",
    "σ": r"\sigma",
    "τ": r"\tau",
    "υ": r"\upsilon",
    "φ": r"\phi",
    "χ": r"\chi",
    "ψ": r"\psi",
    "ω": r"\omega",
    "Γ": r"\Gamma",
    "Δ": r"\Delta",
    "Θ": r"\Theta",
    "Λ": r"\Lambda",
    "Ξ": r"\Xi",
    "Π": r"\Pi",
    "Σ": r"\Sigma",
    "Φ": r"\Phi",
    "Ψ": r"\Psi",
    "Ω": r"\Omega",
    # Comparison operators
    "≤": r"\leq",
    "≥": r"\geq",
    "≠": r"\neq",
    "≈": r"\approx",
    "≡": r"\equiv",
    "≺": r"\prec",
    "≻": r"\succ",
    "⪯": r"\preceq",
    "⪰": r"\succeq",
    # Set operations
    "∈": r"\in",
    "∉": r"\notin",
    "⊂": r"\subset",
    "⊃": r"\supset",
    "⊆": r"\subseteq",
    "⊇": r"\supseteq",
    "∪": r"\cup",
    "∩": r"\cap",
    "∅": r"\emptyset",
    # Arrows
    "→": r"\to",
    "←": r"\leftarrow",
    "↔": r"\leftrightarrow",
    "⇒": r"\Rightarrow",
    "⇐": r"\Leftarrow",
    "⇔": r"\Leftrightarrow",
    "↦": r"\mapsto",
    # Calculus and operators
    "∞": r"\infty",
    "∂": r"\partial",
    "∇": r"\nabla",
    "∑": r"\sum",
    "∏": r"\prod",
    "∫": r"\int",
    "√": r"\sqrt",
    # Logic
    "∀": r"\forall",
    "∃": r"\exists",
    "¬": r"\neg",
    "∧": r"\land",
    "∨": r"\lor",
    # Misc math
    "×": r"\times",
    "÷": r"\div",
    "±": r"\pm",
    "∓": r"\mp",
    "·": r"\cdot",
    "°": r"^\circ",
    "′": r"'",
    "″": r"''",
    "‖": r"\|",
    "⊥": r"\perp",
    "∥": r"\parallel",
    "⊗": r"\otimes",
    "⊕": r"\oplus",
    "ℝ": r"\mathbb{R}",
    "ℂ": r"\mathbb{C}",
    "ℕ": r"\mathbb{N}",
    "ℤ": r"\mathbb{Z}",
    "ℚ": r"\mathbb{Q}",
}


def sanitize_latex(text: str) -> str:
    """Convert unicode math symbols to LaTeX commands.

    Args:
        text: Text potentially containing unicode math symbols

    Returns:
        Text with unicode replaced by LaTeX commands
    """
    for unicode_char, latex_cmd in UNICODE_TO_LATEX.items():
        text = text.replace(unicode_char, latex_cmd)
    return text


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

        # Question (sanitize unicode)
        question_latex = sanitize_latex(qa.question_latex)
        lines.append("\\textbf{Question:} " + question_latex)
        lines.append("")

        # Figures (if any)
        for fig_path in qa.figures:
            lines.append("\\begin{figure}[h]")
            lines.append("  \\centering")
            lines.append(f"  \\includegraphics[width=0.6\\textwidth]{{{fig_path}}}")
            lines.append("\\end{figure}")
            lines.append("")

        # Answer (sanitize unicode and strip "Solution." prefix if present)
        answer_latex = sanitize_latex(qa.answer_latex)
        # Remove common solution prefixes
        answer_latex = answer_latex.strip()
        if answer_latex.startswith(r"\textbf{Solution.}"):
            answer_latex = answer_latex[len(r"\textbf{Solution.}"):].strip()
        elif answer_latex.startswith("Solution."):
            answer_latex = answer_latex[len("Solution."):].strip()

        lines.append("\\textbf{Answer:} " + answer_latex)
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

    def compile_latex(self, tex_path: Path) -> CompilationResult:
        """Compile a LaTeX file to PDF.

        Args:
            tex_path: Path to .tex file

        Returns:
            CompilationResult with success status, PDF path, and any errors/warnings
        """
        if not tex_path.exists():
            return CompilationResult(
                success=False,
                pdf_path=None,
                errors=[f"File not found: {tex_path}"],
                warnings=[]
            )

        output_dir = tex_path.parent
        try:
            result = subprocess.run(
                [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    "-output-directory", str(output_dir),
                    str(tex_path)
                ],
                capture_output=True,
                text=True,
                timeout=60
            )

            # Parse output for errors and warnings
            errors = []
            warnings = []
            for line in result.stdout.split("\n"):
                if line.startswith("!"):
                    errors.append(line)
                elif "Warning" in line:
                    warnings.append(line)

            pdf_path = tex_path.with_suffix(".pdf")
            success = pdf_path.exists() and result.returncode == 0

            return CompilationResult(
                success=success,
                pdf_path=pdf_path if pdf_path.exists() else None,
                errors=errors,
                warnings=warnings
            )

        except FileNotFoundError:
            return CompilationResult(
                success=False,
                pdf_path=None,
                errors=["pdflatex not found. Please install TeX Live or similar."],
                warnings=[]
            )
        except subprocess.TimeoutExpired:
            return CompilationResult(
                success=False,
                pdf_path=None,
                errors=["LaTeX compilation timed out after 60 seconds."],
                warnings=[]
            )

    def validate_and_save(
        self,
        extraction: DocumentExtraction,
        output_path: Path,
        compile_pdf: bool = True
    ) -> CompilationResult | None:
        """Generate, save, and optionally compile LaTeX document.

        Args:
            extraction: Complete document extraction
            output_path: Where to save the .tex file
            compile_pdf: Whether to compile to PDF

        Returns:
            CompilationResult if compile_pdf=True, None otherwise
        """
        self.save_document(extraction, output_path)

        if compile_pdf:
            return self.compile_latex(output_path)
        return None
