#!/usr/bin/env python3
"""Simulate an interrupted extraction to test checkpoint recovery."""

from pathlib import Path
from src.config import get_settings
from src.pipeline import ExtractionPipeline

# Clean up any existing checkpoint and output
output_dir = Path("./output")
checkpoint_path = output_dir / ".checkpoint.json"
if checkpoint_path.exists():
    checkpoint_path.unlink()
    print("Cleaned up old checkpoint")

print("="*60)
print("SIMULATING INTERRUPTED EXTRACTION")
print("="*60)
print("This will process only 1 page, then 'crash'")
print("to simulate an interruption.\n")

settings = get_settings()
pipeline = ExtractionPipeline(settings, resolve_references=False, enable_checkpoints=True)

# Override the process_pdf to stop after 1 page
pdf_path = Path("test_sample.pdf")

# Process just the first page
from src.pdf_processor import PDFProcessor
from src.checkpoint import Checkpoint

pdf_processor = PDFProcessor(dpi=settings.dpi)
total_pages = pdf_processor.get_page_count(pdf_path)
checkpoint = Checkpoint(output_dir / ".checkpoint.json")

print(f"Processing PDF: {pdf_path}")
print(f"Total pages: {total_pages}")

# Process only page 1
all_extractions = []
previous_page_context = None

for page_num in range(1, 2):  # Only page 1
    print(f"\nProcessing page {page_num}/{total_pages}...", end=" ")

    image = pdf_processor.convert_page_to_image(pdf_path, page_num)
    extraction = pipeline.llm_extractor.extract_page(image, page_num, previous_page_context)
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
            "last_question_id": last_q.question_id,
            "last_full_id": last_id,
        }

    print(f"Found {len(extraction.questions)} questions")

    # Save checkpoint
    checkpoint.save(
        pdf_path=pdf_path,
        total_pages=total_pages,
        last_processed_page=page_num,
        all_extractions=all_extractions,
        previous_page_context=previous_page_context,
        resolve_references=False,
    )
    print(f"✓ Checkpoint saved after page {page_num}")

print("\n" + "="*60)
print("SIMULATED CRASH - Extraction stopped after 1 page")
print("="*60)
print("\nCheckpoint file created at: output/.checkpoint.json")
print("\nNow run:")
print("  uv run pdf-extractor extract test_sample.pdf")
print("\nYou should see a prompt to resume from the checkpoint.")
