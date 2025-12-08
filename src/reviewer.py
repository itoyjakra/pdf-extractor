"""Human review interface for Q&A extraction quality."""

import json
import random
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.syntax import Syntax

from .schemas import ExtractionResult


class Reviewer:
    """Interactive reviewer for Q&A pairs."""

    def __init__(self, output_dir: Path):
        """Initialize reviewer.

        Args:
            output_dir: Directory containing extraction results
        """
        self.output_dir = output_dir
        self.console = Console()
        self.reviews: list[dict] = []

        # Load data
        self.qas = self._load_qas()
        self.resolution_results = self._load_resolution_results()
        self.evaluation_report = self._load_evaluation_report()

    def _load_qas(self) -> list[ExtractionResult]:
        """Load extracted Q&As."""
        json_path = self.output_dir / "extracted_qas.json"
        if not json_path.exists():
            raise FileNotFoundError(f"No extraction found: {json_path}")

        with open(json_path) as f:
            data = json.load(f)

        return [
            ExtractionResult(
                id=q["id"],
                question_latex=q["question_latex"],
                answer_latex=q["answer_latex"],
                figures=q.get("figures", []),
                page_range=tuple(q["page_range"])
            )
            for q in data["questions"]
        ]

    def _load_resolution_results(self) -> Optional[dict]:
        """Load resolution results if available."""
        path = self.output_dir / "resolution_results.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None

    def _load_evaluation_report(self) -> Optional[dict]:
        """Load evaluation report if available."""
        path = self.output_dir / "evaluation_report.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None

    def get_qa_by_id(self, qa_id: str) -> Optional[ExtractionResult]:
        """Get a Q&A by ID."""
        for qa in self.qas:
            if qa.id == qa_id:
                return qa
        return None

    def get_review_candidates(
        self,
        priority: str = "all",
        sample_rate: float = 1.0
    ) -> list[ExtractionResult]:
        """Get Q&As for review.

        Args:
            priority: "all", "high", "medium", "failed", or "random"
            sample_rate: Fraction of Q&As to sample (0.0 to 1.0)

        Returns:
            List of Q&As to review
        """
        candidates = list(self.qas)

        # Filter by priority if evaluation report exists
        if self.evaluation_report and priority != "all":
            eval_map = {
                e["qa_id"]: e
                for e in self.evaluation_report.get("evaluations", [])
            }

            if priority == "failed":
                candidates = [
                    qa for qa in candidates
                    if not eval_map.get(qa.id, {}).get("overall_passed", True)
                ]
            elif priority in ("high", "medium"):
                candidates = [
                    qa for qa in candidates
                    if eval_map.get(qa.id, {}).get("review_priority") == priority
                ]

        # Sample if needed
        if sample_rate < 1.0:
            sample_size = max(1, int(len(candidates) * sample_rate))
            candidates = random.sample(candidates, min(sample_size, len(candidates)))

        return candidates

    def display_qa(self, qa: ExtractionResult) -> None:
        """Display a Q&A for review."""
        self.console.clear()

        # Header
        self.console.print(f"\n[bold blue]Q&A Review: {qa.id}[/bold blue]")
        self.console.print(f"Pages: {qa.page_range[0]}-{qa.page_range[1]}")

        # Check if resolved
        was_resolved = False
        if self.resolution_results:
            for detail in self.resolution_results.get("details", []):
                if detail["id"] == qa.id and detail.get("context_inlined"):
                    was_resolved = True
                    self.console.print("[yellow]Cross-references resolved[/yellow]")
                    break

        # Show evaluation status
        if self.evaluation_report:
            for e in self.evaluation_report.get("evaluations", []):
                if e["qa_id"] == qa.id:
                    status = "[green]PASSED[/green]" if e["overall_passed"] else "[red]FAILED[/red]"
                    self.console.print(f"Evaluation: {status}")
                    if e["notes"]:
                        self.console.print(f"Notes: {', '.join(e['notes'])}")
                    break

        self.console.print()

        # Question panel
        question_display = qa.question_latex[:1000]
        if len(qa.question_latex) > 1000:
            question_display += "..."
        self.console.print(Panel(
            Syntax(question_display, "latex", theme="monokai", word_wrap=True),
            title="Question",
            border_style="blue"
        ))

        # Answer panel
        answer_display = qa.answer_latex[:1500]
        if len(qa.answer_latex) > 1500:
            answer_display += "..."
        self.console.print(Panel(
            Syntax(answer_display, "latex", theme="monokai", word_wrap=True),
            title="Answer",
            border_style="green"
        ))

    def review_qa(self, qa: ExtractionResult) -> dict:
        """Interactively review a single Q&A.

        Returns:
            Review decision dict
        """
        self.display_qa(qa)

        self.console.print("\n[bold]Review Options:[/bold]")
        self.console.print("  [a] Accept - Q&A is correct")
        self.console.print("  [r] Reject - Q&A has errors")
        self.console.print("  [s] Skip - Review later")
        self.console.print("  [n] Add note")
        self.console.print("  [q] Quit review session")

        while True:
            choice = Prompt.ask(
                "\nDecision",
                choices=["a", "r", "s", "n", "q"],
                default="s"
            )

            if choice == "a":
                return {"qa_id": qa.id, "decision": "accepted", "notes": ""}
            elif choice == "r":
                notes = Prompt.ask("Rejection reason")
                return {"qa_id": qa.id, "decision": "rejected", "notes": notes}
            elif choice == "s":
                return {"qa_id": qa.id, "decision": "skipped", "notes": ""}
            elif choice == "n":
                notes = Prompt.ask("Note")
                self.console.print(f"[dim]Note added: {notes}[/dim]")
                # Continue loop to get final decision
            elif choice == "q":
                return {"qa_id": qa.id, "decision": "quit", "notes": ""}

    def run_review_session(
        self,
        priority: str = "all",
        sample_rate: float = 1.0
    ) -> list[dict]:
        """Run an interactive review session.

        Args:
            priority: Filter priority ("all", "high", "medium", "failed")
            sample_rate: Fraction to sample

        Returns:
            List of review decisions
        """
        candidates = self.get_review_candidates(priority, sample_rate)

        if not candidates:
            self.console.print("[yellow]No Q&As match the filter criteria.[/yellow]")
            return []

        self.console.print(f"\n[bold]Starting review session: {len(candidates)} Q&As[/bold]")

        reviews = []
        for i, qa in enumerate(candidates):
            self.console.print(f"\n[dim]({i+1}/{len(candidates)})[/dim]")
            review = self.review_qa(qa)
            reviews.append(review)

            if review["decision"] == "quit":
                break

        self.reviews.extend(reviews)
        return reviews

    def save_reviews(self, output_path: Optional[Path] = None) -> Path:
        """Save review decisions to file.

        Args:
            output_path: Where to save (default: output_dir/reviews.json)

        Returns:
            Path to saved file
        """
        if output_path is None:
            output_path = self.output_dir / "reviews.json"

        # Load existing reviews if any
        existing = []
        if output_path.exists():
            with open(output_path) as f:
                existing = json.load(f)

        # Merge (newer reviews override)
        review_map = {r["qa_id"]: r for r in existing}
        for r in self.reviews:
            if r["decision"] != "quit":
                review_map[r["qa_id"]] = r

        # Save
        with open(output_path, "w") as f:
            json.dump(list(review_map.values()), f, indent=2)

        return output_path

    def print_summary(self) -> None:
        """Print review session summary."""
        if not self.reviews:
            return

        accepted = sum(1 for r in self.reviews if r["decision"] == "accepted")
        rejected = sum(1 for r in self.reviews if r["decision"] == "rejected")
        skipped = sum(1 for r in self.reviews if r["decision"] == "skipped")

        table = Table(title="Review Summary")
        table.add_column("Decision", style="bold")
        table.add_column("Count", justify="right")

        table.add_row("Accepted", f"[green]{accepted}[/green]")
        table.add_row("Rejected", f"[red]{rejected}[/red]")
        table.add_row("Skipped", f"[yellow]{skipped}[/yellow]")

        self.console.print(table)
