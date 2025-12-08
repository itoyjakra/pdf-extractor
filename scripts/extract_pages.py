#!/usr/bin/env python3
"""Extract selected pages from a PDF document."""

import sys
from pathlib import Path

import fitz  # PyMuPDF


def extract_pages(input_pdf: Path, output_pdf: Path, start_page: int, end_page: int) -> None:
    """Extract pages from a PDF.

    Args:
        input_pdf: Path to input PDF
        output_pdf: Path to output PDF
        start_page: Start page number (1-indexed, inclusive)
        end_page: End page number (1-indexed, inclusive)
    """
    doc = fitz.open(input_pdf)
    total_pages = len(doc)

    # Validate page numbers
    if start_page < 1:
        raise ValueError(f"Start page must be >= 1, got {start_page}")
    if end_page > total_pages:
        raise ValueError(f"End page {end_page} exceeds total pages {total_pages}")
    if start_page > end_page:
        raise ValueError(f"Start page {start_page} > end page {end_page}")

    # Create new document with selected pages (PyMuPDF is 0-indexed)
    new_doc = fitz.open()
    new_doc.insert_pdf(doc, from_page=start_page - 1, to_page=end_page - 1)

    # Save
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    new_doc.save(output_pdf)

    print(f"Extracted pages {start_page}-{end_page} from {input_pdf}")
    print(f"Saved to: {output_pdf}")
    print(f"Total pages in output: {len(new_doc)}")

    new_doc.close()
    doc.close()


def main():
    if len(sys.argv) != 5:
        print("Usage: python extract_pages.py <input.pdf> <output.pdf> <start_page> <end_page>")
        print("")
        print("Example: python extract_pages.py textbook.pdf sample.pdf 10 15")
        print("         Extracts pages 10-15 (inclusive) from textbook.pdf")
        sys.exit(1)

    input_pdf = Path(sys.argv[1])
    output_pdf = Path(sys.argv[2])
    start_page = int(sys.argv[3])
    end_page = int(sys.argv[4])

    if not input_pdf.exists():
        print(f"Error: Input file not found: {input_pdf}")
        sys.exit(1)

    extract_pages(input_pdf, output_pdf, start_page, end_page)


if __name__ == "__main__":
    main()
