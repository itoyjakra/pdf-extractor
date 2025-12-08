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
    console.print(Panel.fit(
        f"[bold]PDF:[/bold] {pdf_path}\n"
        f"[bold]Provider:[/bold] {settings.default_provider}\n"
        f"[bold]Output:[/bold] {output_dir or './output'}\n"
        f"[bold]Resolve refs:[/bold] {'Yes' if resolve_refs else 'No'}",
        title="Extraction Configuration"
    ))

    try:
        # Run pipeline
        pipeline = ExtractionPipeline(settings, resolve_references=resolve_refs)
        extraction = pipeline.process_pdf(pdf_path, output_dir)

        # Success summary
        console.print("\n[green]✓ Extraction complete![/green]")
        console.print(f"  Total Q&A pairs: {len(extraction.questions)}")

    except Exception as e:
        console.print(f"[red]Error during extraction: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def version():
    """Show version information."""
    console.print("pdf-extractor v0.1.0")


if __name__ == "__main__":
    app()
