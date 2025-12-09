"""Command-line interface for PDF Q&A extractor."""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel

from .pipeline import ExtractionPipeline
from .config import get_settings

app = typer.Typer(help="Extract Q&A pairs from math-heavy PDFs into LaTeX")
console = Console()


@app.command()
def extract(
    pdf_path: Path = typer.Argument(..., help="Path to the PDF file to process"),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Output directory (default: ./output)"
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider", "-p",
        help="LLM provider: 'openai' or 'anthropic'"
    ),
    no_resolve: bool = typer.Option(
        False,
        "--no-resolve",
        help="Skip cross-reference resolution"
    ),
    compile_pdf: bool = typer.Option(
        False,
        "--compile",
        help="Compile LaTeX to PDF after extraction"
    ),
    no_checkpoint: bool = typer.Option(
        False,
        "--no-checkpoint",
        help="Disable checkpoint saving/loading"
    ),
    force_restart: bool = typer.Option(
        False,
        "--force-restart",
        help="Ignore existing checkpoint and start from scratch"
    ),
):
    """Extract Q&A pairs from a PDF document.

    Processes the PDF page by page, extracting questions and answers using
    vision LLM, and outputs both JSON and LaTeX formats. Cross-references
    are automatically resolved to make Q&As self-contained.
    """
    # Validate PDF exists
    if not pdf_path.exists():
        console.print(f"[red]Error: PDF file not found: {pdf_path}[/red]")
        raise typer.Exit(1)

    # Load settings
    settings = get_settings()

    # Override provider if specified
    if provider:
        if provider not in ["openai", "anthropic"]:
            console.print("[red]Error: Provider must be 'openai' or 'anthropic'[/red]")
            raise typer.Exit(1)
        settings.default_provider = provider

    # Check API key
    if settings.default_provider == "openai" and not settings.openai_api_key:
        console.print("[red]Error: OPENAI_API_KEY not set[/red]")
        console.print("Set it in .env file or environment variable")
        raise typer.Exit(1)
    elif settings.default_provider == "anthropic" and not settings.anthropic_api_key:
        console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]")
        console.print("Set it in .env file or environment variable")
        raise typer.Exit(1)

    # Show config
    resolve_refs = not no_resolve
    enable_checkpoints = not no_checkpoint
    console.print(Panel.fit(
        f"[bold]PDF:[/bold] {pdf_path}\n"
        f"[bold]Provider:[/bold] {settings.default_provider}\n"
        f"[bold]Output:[/bold] {output_dir or './output'}\n"
        f"[bold]Resolve refs:[/bold] {'Yes' if resolve_refs else 'No'}\n"
        f"[bold]Checkpoints:[/bold] {'Enabled' if enable_checkpoints else 'Disabled'}",
        title="Extraction Configuration"
    ))

    try:
        # Run pipeline
        pipeline = ExtractionPipeline(
            settings,
            resolve_references=resolve_refs,
            enable_checkpoints=enable_checkpoints
        )
        extraction = pipeline.process_pdf(pdf_path, output_dir, force_restart=force_restart)

        # Success summary
        console.print("\n[green]✓ Extraction complete![/green]")
        console.print(f"  Total Q&A pairs: {len(extraction.questions)}")

        # Compile PDF if requested
        if compile_pdf:
            from .latex_generator import LaTeXGenerator
            latex_gen = LaTeXGenerator()
            out_dir = output_dir or Path("./output")
            tex_path = out_dir / "extracted_qas.tex"

            console.print("\n[bold]Compiling LaTeX to PDF...[/bold]")
            result = latex_gen.compile_latex(tex_path)

            if result.success:
                console.print(f"[green]✓ PDF generated: {result.pdf_path}[/green]")
            else:
                console.print(f"[yellow]⚠ PDF generated with errors[/yellow]")

            if result.errors:
                console.print(f"  [red]Errors ({len(result.errors)}):[/red]")
                for err in result.errors[:5]:  # Show first 5
                    console.print(f"    {err}")
                if len(result.errors) > 5:
                    console.print(f"    ... and {len(result.errors) - 5} more")

    except Exception as e:
        console.print(f"[red]Error during extraction: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def figures(
    pdf_path: Path = typer.Argument(..., help="Path to the PDF file"),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Output directory (default: ./output/figures)"
    ),
    min_size: int = typer.Option(
        50,
        "--min-size",
        help="Minimum dimension (pixels) to extract as figure"
    ),
):
    """Extract figures/images from a PDF document.

    Extracts all embedded images from the PDF and saves them to the output directory.
    Small images (icons, bullets) are filtered out based on min-size.
    """
    from .pdf_processor import PDFProcessor

    if not pdf_path.exists():
        console.print(f"[red]Error: PDF file not found: {pdf_path}[/red]")
        raise typer.Exit(1)

    out_dir = output_dir or Path("./output")
    processor = PDFProcessor()

    console.print(f"[bold]Extracting figures from:[/bold] {pdf_path}")

    # Try embedded images first, then vector drawings
    all_figures = processor.extract_all_figures(pdf_path, out_dir, min_size)

    if not all_figures:
        console.print("[dim]No embedded images found, checking for vector drawings...[/dim]")
        all_figures = processor.extract_vector_figures(pdf_path, out_dir)

    total_figures = sum(len(figs) for figs in all_figures.values())

    if total_figures == 0:
        console.print("[yellow]No figures found in the PDF.[/yellow]")
    else:
        console.print(f"\n[green]✓ Extracted {total_figures} figures:[/green]")
        for page_num, figs in sorted(all_figures.items()):
            console.print(f"  Page {page_num}: {len(figs)} figures")
            for fig in figs:
                console.print(f"    - {fig['figure_id']}: {fig['width']}x{fig['height']} → {fig['path']}")


@app.command()
def evaluate(
    output_dir: Path = typer.Argument(
        ...,
        help="Directory containing extraction results (extracted_qas.json)"
    ),
):
    """Evaluate extraction quality.

    Checks LaTeX compilation, remaining cross-references, and answer changes.
    Generates an evaluation report with pass/fail status and review priorities.
    """
    from .evaluator import Evaluator
    from .schemas import ExtractionResult
    import json

    json_path = output_dir / "extracted_qas.json"
    if not json_path.exists():
        console.print(f"[red]Error: {json_path} not found[/red]")
        raise typer.Exit(1)

    # Load extracted Q&As
    with open(json_path) as f:
        data = json.load(f)

    qas = [
        ExtractionResult(
            id=q["id"],
            question_latex=q["question_latex"],
            answer_latex=q["answer_latex"],
            figures=q.get("figures", []),
            page_range=tuple(q["page_range"])
        )
        for q in data["questions"]
    ]

    # Load resolution results if available
    resolution_path = output_dir / "resolution_results.json"
    resolution_results = None
    if resolution_path.exists():
        with open(resolution_path) as f:
            resolution_results = json.load(f)

    console.print(f"[bold]Evaluating {len(qas)} Q&A pairs...[/bold]")

    evaluator = Evaluator(output_dir / "evaluation")
    report = evaluator.evaluate_extraction(qas, resolution_results)

    # Save report
    report_path = output_dir / "evaluation_report.json"
    evaluator.save_report(report, report_path)
    console.print(f"Saved report to: {report_path}")

    # Print summary
    evaluator.print_report(report)

    if report.failed > 0:
        console.print(f"\n[yellow]⚠ {report.failed} Q&As failed evaluation[/yellow]")
    else:
        console.print("\n[green]✓ All Q&As passed evaluation[/green]")


@app.command()
def review(
    output_dir: Path = typer.Argument(
        ...,
        help="Directory containing extraction results"
    ),
    priority: str = typer.Option(
        "all",
        "--priority", "-p",
        help="Filter: 'all', 'failed', 'high', 'medium'"
    ),
    sample_rate: float = typer.Option(
        1.0,
        "--sample", "-s",
        help="Fraction of Q&As to sample (0.0 to 1.0)"
    ),
):
    """Interactively review extracted Q&A pairs.

    Displays each Q&A for human review and collects accept/reject decisions.
    Reviews are saved to reviews.json in the output directory.
    """
    from .reviewer import Reviewer

    try:
        reviewer = Reviewer(output_dir)
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    reviews = reviewer.run_review_session(priority, sample_rate)

    if reviews:
        review_path = reviewer.save_reviews()
        console.print(f"\nSaved reviews to: {review_path}")
        reviewer.print_summary()


@app.command()
def version():
    """Show version information."""
    console.print("pdf-extractor v0.1.0")


if __name__ == "__main__":
    app()
