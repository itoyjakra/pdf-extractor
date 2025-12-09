# PDF Q&A Extractor

Extract question-answer pairs from math-heavy PDF textbooks into structured LaTeX format, ready for LLM fine-tuning.

## Features

- **Vision LLM Extraction**: Uses GPT-4o or Claude to accurately extract mathematical notation
- **Cross-Reference Resolution**: Makes each Q&A self-contained by inlining referenced content
- **Multi-Page Handling**: Stitches Q&As that span multiple pages
- **Automatic Checkpointing**: Resume extraction after interruptions
- **Quality Evaluation**: Validates LaTeX compilation and checks resolution quality
- **Human Review Interface**: CLI-based spot-checking with sampling

## Installation

```bash
# Requires Python 3.13+
uv sync
```

## Quick Start

```bash
# Set API key in .env file
echo "ANTHROPIC_API_KEY=your-key-here" > .env

# Extract Q&A pairs from PDF
uv run pdf-extractor extract input.pdf

# Output: extracted_qas.json and extracted_qas.tex in ./output/
```

## Usage

```bash
# Basic extraction (Anthropic Claude by default)
uv run pdf-extractor extract document.pdf

# Use OpenAI instead
uv run pdf-extractor extract document.pdf --provider openai

# Skip cross-reference resolution
uv run pdf-extractor extract document.pdf --no-resolve

# Compile LaTeX to PDF
uv run pdf-extractor extract document.pdf --compile

# Disable checkpointing (not recommended)
uv run pdf-extractor extract document.pdf --no-checkpoint

# Force restart from beginning
uv run pdf-extractor extract document.pdf --force-restart

# Evaluate extraction quality
uv run pdf-extractor evaluate ./output

# Human review (5% sample)
uv run pdf-extractor review ./output --sample 0.05
```

## Checkpointing

Extraction automatically saves progress after each page. If interrupted:

1. Restart the same command
2. When prompted "Resume from checkpoint? [Y/n]:", press Y
3. Extraction continues from where it stopped

## Output Format

### JSON (`output/extracted_qas.json`)
```json
{
  "metadata": {
    "source_pdf": "textbook.pdf",
    "total_questions": 150,
    "model_used": "anthropic:claude-sonnet-4-20250514"
  },
  "questions": [
    {
      "id": "2.7",
      "question_latex": "Show that...",
      "answer_latex": "We prove...",
      "page_range": [1, 1]
    }
  ]
}
```

### LaTeX (`output/extracted_qas.tex`)
Compilable LaTeX document with all Q&A pairs formatted for readability.

## Configuration

Create `.env` file:
```bash
# Required: one of these
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Optional
DEFAULT_PROVIDER=anthropic  # or "openai"
DPI=300                      # Image resolution
```

## Architecture

1. **PDF Processing** ’ Convert pages to images
2. **LLM Extraction** ’ Extract structured Q&A with vision LLM
3. **Multi-Page Stitching** ’ Merge Q&As spanning pages
4. **Cross-Reference Resolution** ’ Make Q&As self-contained
5. **LaTeX Generation** ’ Output compilable document
6. **Evaluation** ’ Validate quality
7. **Review** ’ Human spot-checking

## Requirements

- Python 3.13+
- OpenAI API key (for GPT-4o) OR Anthropic API key (for Claude)
- Optional: `pdflatex` (for PDF compilation)

## Testing

```bash
# Test with sample PDF (3 pages)
uv run pdf-extractor extract test_sample.pdf

# Simulate interruption and resume
./demo_checkpoint.sh
```

## Documentation

- **CLAUDE.md**: Comprehensive guide for developers
- **CHECKPOINT_IMPLEMENTATION.md**: Checkpointing system details
- **plan.md**: Full architecture and design decisions

## License

See LICENSE file.
