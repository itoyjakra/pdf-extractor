# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a PDF Q&A extraction pipeline that converts math-heavy textbook PDFs into structured LaTeX Q&A pairs suitable for LLM fine-tuning. The pipeline uses vision LLMs (OpenAI GPT-4o or Anthropic Claude) to extract questions and answers, then resolves cross-references to make each Q&A self-contained.

## Key Commands

### Development Setup
```bash
# Install dependencies (uses uv package manager)
uv sync

# Run the CLI tool
uv run pdf-extractor --help
```

### Common Operations
```bash
# Extract Q&A from a PDF (default: Anthropic Claude)
uv run pdf-extractor extract input.pdf

# Use OpenAI instead
uv run pdf-extractor extract input.pdf --provider openai

# Skip cross-reference resolution
uv run pdf-extractor extract input.pdf --no-resolve

# Compile LaTeX to PDF after extraction
uv run pdf-extractor extract input.pdf --compile

# Disable checkpointing (not recommended for large PDFs)
uv run pdf-extractor extract input.pdf --no-checkpoint

# Force restart from beginning (ignore existing checkpoint)
uv run pdf-extractor extract input.pdf --force-restart

# Extract figures only
uv run pdf-extractor figures input.pdf

# Evaluate extraction quality
uv run pdf-extractor evaluate ./output

# Interactive human review
uv run pdf-extractor review ./output --sample 0.05
```

### Configuration
- API keys are loaded from `.env` file
- Required: `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` depending on provider
- See `src/config.py` for all settings

## Architecture

The pipeline follows a **structured multi-stage design** (not agentic):

```
PDF Input → PDF Processing → LLM Extraction → Multi-page Stitching
  → Cross-reference Resolution → LaTeX Generation → Evaluation → Review
```

### Core Components

1. **`src/pipeline.py`** - Main orchestrator
   - Coordinates all stages
   - Handles multi-page context passing between pages
   - Performs Q&A stitching for solutions that span pages
   - Sorts Q&As (parent questions before sub-parts, e.g., 2.18 before 2.18a)

2. **`src/llm_extractor.py`** - Vision LLM extraction
   - Sends PDF page images to vision LLM
   - Extracts structured Q&A using prompt from `prompts/extraction.md`
   - Passes context between pages to handle multi-part questions correctly
   - Returns structured JSON with question ID, parts, LaTeX content, continuation flags

3. **`src/reference_resolver.py`** - Cross-reference resolution
   - Detects references to other questions (e.g., "using 2.7...", "previous question")
   - Uses LLM to inline relevant context from referenced Q&A
   - Makes each Q&A self-contained for LLM training
   - Tracks which Q&As were modified for evaluation

4. **`src/latex_generator.py`** - LaTeX output
   - Converts structured Q&A to compilable LaTeX document
   - Performs unicode-to-LaTeX conversion (90+ symbols)
   - Can compile LaTeX to PDF using pdflatex

5. **`src/evaluator.py`** - Quality assurance
   - Validates LaTeX compilation
   - Checks for remaining cross-references in resolved Q&As
   - Detects answer changes (should be rare - refs usually in questions only)
   - Generates evaluation report with pass/fail status

6. **`src/reviewer.py`** - Human review interface
   - CLI-based interactive review
   - Can filter by evaluation priority (failed, high, medium)
   - Saves review decisions to JSON

### Data Schemas

All schemas defined in `src/schemas/extraction.py`:
- `QuestionPart` - Single part of a question with continuation flags
- `Question` - Contains one or more parts, tracks page range
- `PageExtraction` - All questions extracted from a single page
- `ExtractionResult` - Flattened Q&A pair (final output format)
- `DocumentExtraction` - Complete extraction with metadata

### LLM Provider Abstraction

`src/models/` contains provider interfaces:
- `base.py` - Abstract `BaseLLM` class
- `openai.py` - OpenAI GPT-4o implementation
- `anthropic.py` - Anthropic Claude implementation

Both support vision (page images) and structured output (JSON responses).

## Critical Implementation Details

### Multi-page Context Passing
The pipeline passes context from one page to the next to correctly handle:
- Multi-part questions that start on one page and continue on the next
- Question parts like "(b)" at the top of a page belong to the last question ID from the previous page, NOT a new question on the current page

Context format:
```python
{
  "questions_summary": "2.17a, 2.17b, 2.18",  # All Q&As on previous page
  "last_question_id": "2.18",                  # Base question number
  "last_full_id": "2.18a"                      # Full ID including part
}
```

### Q&A Stitching Algorithm
`stitch_multi_page_qas()` in `pipeline.py`:
- Finds Q&As with `continues_next_page=True` on page N
- Matches them with `continued_from_previous=True` entries on page N+1 by question ID and part ID
- Merges question text and answer text
- Updates page range to span both pages
- Removes the continuation fragment from the next page

### Cross-reference Resolution
Resolution happens AFTER stitching but BEFORE final output:
- LLM analyzes each Q&A for references (more accurate than regex)
- If references found, LLM extracts only relevant context from referenced Q&A
- LLM rewrites the question to be self-contained
- Answers should NOT change (references typically only in questions)
- All changes tracked in `resolution_results.json` for evaluation

### Q&A Sorting
Questions are sorted using `parse_qa_id()` to ensure proper ordering:
- Parent question before sub-parts: 2.18 comes before 2.18a, 2.18b
- Numeric sorting: 2.9 before 2.10 (not lexicographic)
- Handles IDs like "2.18", "2.18a", "10.15c"

## Checkpointing System

The pipeline automatically saves progress after each page to enable resumption after interruptions.

### How It Works
- Checkpoint file saved to `output/.checkpoint.json` after each page
- Contains complete extraction state: page extractions, context, settings
- On restart, pipeline detects checkpoint and prompts user to resume
- Checkpoint deleted automatically on successful completion

### Checkpoint Structure
```json
{
  "pdf_path": "/path/to/input.pdf",
  "total_pages": 250,
  "last_processed_page": 47,
  "timestamp": "2025-12-09T10:30:00Z",
  "resolve_references": true,
  "previous_page_context": {...},
  "all_extractions": [...]
}
```

### Usage
- **Automatic**: No action needed, checkpointing is enabled by default
- **Resume**: When restarting, answer "Y" to the resume prompt
- **Fresh start**: Answer "n" to resume prompt, or use `--force-restart` flag
- **Disable**: Use `--no-checkpoint` flag (not recommended for large PDFs)

### Implementation Details
- Checkpoint saving/loading in `src/checkpoint.py`
- Integrated into `ExtractionPipeline.process_pdf()` in `src/pipeline.py`
- Atomically written using temp file to prevent corruption
- Validates PDF path matches before resuming

## Important Conventions

### LaTeX Math Mode
The extraction prompt (`prompts/extraction.md`) enforces strict LaTeX rules:
- ALL math must be in math mode: `$x$`, `$f(x)$`, `$$...$$`
- NO unicode math symbols (≤, ≥, ∈, ≠) - use LaTeX commands (`\leq`, `\geq`, `\in`, `\neq`)
- Set notation: `$\{x \mid f(x) \leq 0\}$` (use `\mid` not `|`)
- Function names: `$\text{dom } f$` not `dom f`

### Error Handling
Answers are expected to remain unchanged during cross-reference resolution:
- If `answer_changed=True` in resolution results, this is flagged for review
- Evaluation checks answer similarity and warns if < 95% match

### Output Structure
```
output/
├── extracted_qas.json        # Final Q&A pairs
├── extracted_qas.tex          # Compilable LaTeX document
├── resolution_results.json    # Cross-reference resolution tracking
├── evaluation_report.json     # Quality metrics
└── reviews.json               # Human review decisions
```

## Development Notes

### Phase Status (from plan.md)
- ✅ Phase 1: Core extraction (MVP)
- ✅ Phase 1.5: Cross-reference resolution
- ✅ Phase 1.6: LaTeX improvements
- ✅ Phase 2: Multi-page stitching & figure extraction
- ✅ Phase 3: Evaluation & human review
- ⏳ Phase 4: Optimization
  - ✅ Checkpointing and resumption
  - ⏳ Batching (processing 2-3 pages together)
  - ⏳ Caching (image conversion, API responses)

### Known Design Decisions
- **Structured pipeline** over agentic workflow (cost, speed, predictability)
- **Vision LLM** over OCR (accuracy for math notation)
- **CLI review** interface (web UI planned for Phase 4)
- **JSON + LaTeX** dual output format
- **Single PDF** processing at a time (no batch mode yet)

### Testing
No automated test suite exists yet. Manual testing workflow:
1. Run extraction on `test_sample.pdf` or `test_crossref.pdf`
2. Check output in `./output/`
3. Compile LaTeX: `pdflatex output/extracted_qas.tex`
4. Run evaluation: `uv run pdf-extractor evaluate ./output`
5. Spot-check with review: `uv run pdf-extractor review ./output --sample 0.1`
