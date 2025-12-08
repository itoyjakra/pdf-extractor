# PDF Q&A Extractor - Implementation Plan

## Overview

Build an accurate extraction pipeline that converts math-heavy PDF documents containing exercises and solutions into structured LaTeX Q&A pairs suitable for LLM fine-tuning.

## Architecture Decision

After analyzing the requirements, I recommend a **Hybrid LLM Vision + Structured Processing** approach.

### Why Structured Pipeline Over Agentic Workflow?

We considered two approaches:

1. **Agentic Workflow**: LLM agent makes decisions, uses tools, iterates and self-corrects
2. **Structured Pipeline**: Predefined stages with LLM used for specific extraction tasks

| Factor | Agentic | Structured Pipeline |
|--------|---------|---------------------|
| **Cost** | Higher (reasoning overhead) | Lower (direct extraction) |
| **Speed** | Slower (sequential decisions) | Faster (parallelizable) |
| **Predictability** | Variable | Consistent |
| **Debugging** | Harder (opaque reasoning) | Easier (clear steps) |
| **Adaptability** | Excellent | Moderate |
| **Edge case handling** | Self-correcting | Needs engineering |

**Decision: Structured Pipeline**

Rationale:
1. **Document format is consistent** - Clear patterns (numbered questions, "Solution." markers) mean an agent would repeat the same actions anyway
2. **Scale matters** - At 200+ pages, agent reasoning overhead adds significant cost
3. **Checkpointing is cleaner** - Saving/resuming state is straightforward with defined stages
4. **Evaluation requires consistency** - Comparing outputs is easier with deterministic extraction
5. **Debugging production issues** - Structured logs are easier to trace than agent reasoning chains

If edge cases prove problematic in practice, we can add targeted agent interventions later (e.g., a "repair agent" for low-confidence extractions).

---

### Why This Approach?

| Approach | Accuracy | Cost | Complexity | Math Support |
|----------|----------|------|------------|--------------|
| Pure OCR + Rules | Low | Low | Medium | Poor |
| Pure LLM Vision | High | High | Low | Excellent |
| **Hybrid (Recommended)** | High | Medium | Medium | Excellent |
| Specialized OCR (Nougat) | Medium | Low | Medium | Good |

The hybrid approach:
1. Uses LLM vision for accurate math/LaTeX extraction
2. Implements smart batching to reduce API costs
3. Adds structured processing for reliability and evaluation

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        EXTRACTION PIPELINE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐   │
│  │   PDF    │───▶│  Image   │───▶│  Figure  │───▶│   LLM    │   │
│  │  Loader  │    │Converter │    │Extractor │    │ Vision   │   │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘   │
│                                                        │          │
│                                                        ▼          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐   │
│  │  LaTeX   │◀───│   Q&A    │◀───│  Multi-  │◀───│  JSON    │   │
│  │ Document │    │ Splitter │    │Page Merge│    │ Parser   │   │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘   │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│                        EVALUATION PIPELINE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐   │
│  │  LaTeX   │───▶│   PDF    │───▶│  Image   │───▶│ Compare  │   │
│  │ Compiler │    │ Renderer │    │ Differ   │    │ & Score  │   │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘   │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│                        REVIEW INTERFACE                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                   │
│  │  Random  │───▶│  Side-by │───▶│  Accept/ │                   │
│  │ Sampler  │    │   Side   │    │  Reject  │                   │
│  └──────────┘    └──────────┘    └──────────┘                   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. PDF Processor (`src/pdf_processor.py`)

**Responsibilities:**
- Load PDF documents
- Convert pages to high-resolution images (300 DPI)
- Extract embedded images/figures
- Detect page boundaries and headers/footers

**Key Libraries:**
- `PyMuPDF` (fitz) - Fast PDF parsing, image extraction
- `pdf2image` - High-quality page rendering
- `Pillow` - Image processing

**Implementation Notes:**
- Cache converted images to avoid reprocessing
- Support incremental processing for large documents
- Extract page metadata (page numbers, headers)

---

### 2. Figure Extractor (`src/figure_extractor.py`)

**Responsibilities:**
- Detect figure regions in page images
- Extract figures as separate image files
- Generate unique figure IDs for LaTeX references
- Handle inline vs. block figures

**Approach:**
1. Use LLM vision to identify figure bounding boxes
2. Extract and save figures with naming convention: `fig_{question_id}_{index}.png`
3. Create figure manifest for LaTeX generation

**Fallback Strategy:**
- Use contour detection for simple diagrams
- Extract all embedded PDF images as candidates

---

### 3. LLM Vision Extractor (`src/llm_extractor.py`)

**Responsibilities:**
- Send page images to vision LLM (GPT-4o / Claude)
- Extract structured Q&A data
- Handle multi-page context windows
- Manage API rate limits and retries

**Prompt Strategy:**
```
You are extracting Q&A pairs from a math textbook. For each page:
1. Identify all questions (numbered like 2.7, 2.8, etc.)
2. For multi-part questions (a, b, c...), extract each as separate Q&A
3. Extract the full question text in LaTeX format
4. Extract the complete solution in LaTeX format
5. Note any figure references with bounding box coordinates
6. Flag if question/answer continues to next page
```

**Output Schema:**
```json
{
  "page_number": 1,
  "questions": [
    {
      "id": "2.7",
      "parts": [
        {
          "part_id": null,
          "question_latex": "...",
          "answer_latex": "...",
          "figures": [{"bbox": [x1,y1,x2,y2], "type": "diagram"}],
          "continues_next_page": false,
          "continued_from_previous": false
        }
      ]
    },
    {
      "id": "2.8",
      "parts": [
        {"part_id": "a", "question_latex": "...", "answer_latex": "..."},
        {"part_id": "b", "question_latex": "...", "answer_latex": "..."}
      ]
    }
  ]
}
```

**Multi-Page Handling:**
- Send 2-3 consecutive pages together for context
- Use sliding window approach
- Merge partial Q&As based on continuation flags

**Cost Optimization:**
- Batch multiple pages where possible
- Use lower resolution for initial pass, high-res for verification
- Cache results to avoid re-extraction

---

### 4. Multi-Page Merger (`src/merger.py`)

**Responsibilities:**
- Combine Q&A fragments across page boundaries
- Validate question numbering continuity
- Handle nested question structures

**Algorithm:**
1. Scan all extracted Q&As for continuation flags
2. Build a graph of connected fragments
3. Merge fragments maintaining order
4. Validate final structure

---

### 5. Q&A Splitter (`src/splitter.py`)

**Responsibilities:**
- Split multi-part questions into separate Q&A pairs
- Preserve context (question stem for each part)
- Generate proper IDs (3.4a, 3.4b, 3.4c)

**Example Transformation:**
```
Input:
  Question 3.4: Consider the set S...
    (a) Show that S is convex
    (b) Find the dimension of S

Output:
  Q&A 1: {id: "3.4a", question: "Consider S... (a) Show that S is convex", answer: "..."}
  Q&A 2: {id: "3.4b", question: "Consider S... (b) Find the dimension of S", answer: "..."}
```

---

### 6. Cross-Reference Resolver (`src/reference_resolver.py`)

**Responsibilities:**
- Detect cross-references to other questions/answers
- Resolve references by inlining relevant context
- Make each Q&A self-contained for LLM fine-tuning

**Cross-Reference Patterns to Detect:**
```python
REFERENCE_PATTERNS = [
    r"exercise\s+(\d+\.?\d*[a-z]*)",           # "exercise 2.7"
    r"problem\s+(\d+\.?\d*[a-z]*)",            # "problem 2.7"
    r"question\s+(\d+\.?\d*[a-z]*)",           # "question 2.7"
    r"part\s+\(([a-z])\)",                      # "part (a)"
    r"from\s+(\d+\.?\d*[a-z]*)",               # "from 2.7"
    r"using\s+(\d+\.?\d*[a-z]*)",              # "using 2.7"
    r"\((\d+\.?\d*[a-z]*)\)",                   # "(2.7)"
    r"previous\s+(question|exercise|problem)",  # "previous question"
    r"above\s+(result|proof|solution)",         # "above result"
]
```

**Resolution Strategy:**

1. **Detect**: Scan question_latex and answer_latex for reference patterns
2. **Analyze**: Use LLM to:
   - Identify what specific information from the reference is needed
   - Extract only the relevant portion (not the entire Q&A)
   - Determine where to inline it
3. **Rewrite**: Use LLM to rewrite the Q&A to be self-contained
4. **Validate**: Ensure the rewritten version maintains mathematical correctness

**LLM Prompt for Resolution:**
```
You are resolving cross-references in math Q&A pairs for LLM fine-tuning.

Current Q&A:
Question: {question_latex}
Answer: {answer_latex}

Referenced Q&A (ID: {ref_id}):
Question: {ref_question_latex}
Answer: {ref_answer_latex}

Task:
1. Identify what specific information from the referenced Q&A is needed
2. Extract ONLY the relevant portion (definition, result, formula, etc.)
3. Rewrite the current Q&A to be self-contained by inlining this information
4. Maintain all mathematical notation and correctness

Return JSON:
{
  "needs_resolution": true/false,
  "relevant_context": "extracted context from reference",
  "rewritten_question": "self-contained question",
  "rewritten_answer": "self-contained answer"
}
```

**Implementation:**
```python
class CrossReferenceResolver:
    def __init__(self, llm: BaseLLM):
        self.llm = llm

    def detect_references(self, qa: ExtractionResult) -> list[str]:
        """Find question IDs referenced in Q&A text"""

    def resolve(
        self,
        qa: ExtractionResult,
        all_qas: dict[str, ExtractionResult]
    ) -> ExtractionResult:
        """Make Q&A self-contained by resolving references"""

    def resolve_all(
        self,
        qas: list[ExtractionResult]
    ) -> list[ExtractionResult]:
        """Resolve all cross-references in a document"""
```

**Example:**

*Before:*
```
Q 2.9: Using the Voronoi description from 2.7, prove that...
A: From 2.7, we know the halfspace is c^T x ≤ d. Therefore...
```

*After:*
```
Q 2.9: The Voronoi description shows that points closer to a than b
       form a halfspace c^T x ≤ d where c = 2(b-a). Using this, prove that...
A: Since the halfspace is defined by c^T x ≤ d where c = 2(b-a), we have...
```

---

### 7. LaTeX Generator (`src/latex_generator.py`)

**Responsibilities:**
- Convert structured Q&A data to LaTeX document
- Include proper math packages (amsmath, amssymb, etc.)
- Handle figure references
- Generate compilable document

**Note:** LaTeX generator now receives Q&As after cross-reference resolution, so all Q&As are self-contained.

**Output Structure:**
```latex
\documentclass{article}
\usepackage{amsmath,amssymb,graphicx,amsthm}

\begin{document}

% Question 2.7
\subsection*{Question 2.7}
\textbf{Question:} ...

\textbf{Answer:} ...

% Question 2.8a
\subsection*{Question 2.8a}
\textbf{Question:} ...
\begin{figure}[h]
  \includegraphics[width=0.5\textwidth]{figures/fig_2.8a_1.png}
\end{figure}

\textbf{Answer:} ...

\end{document}
```

---

### 8. Evaluator (`src/evaluator.py`)

**Responsibilities:**
- Compile generated LaTeX to PDF
- Render both original and generated PDFs to images
- Compare using image similarity metrics
- Generate quality scores and reports
- Verify cross-reference resolution quality

**Metrics:**
1. **Structural Similarity Index (SSIM)** - Overall visual similarity
2. **Character-level accuracy** - For text regions
3. **Math expression accuracy** - Compare rendered equations
4. **Figure placement accuracy** - Bounding box overlap
5. **Cross-reference resolution** - Specialized evaluation (see below)

**Standard Q&A Evaluation:**
```python
class Evaluator:
    def compile_latex(self, latex_path: Path) -> Path:
        """Compile LaTeX to PDF using pdflatex"""

    def render_to_images(self, pdf_path: Path) -> List[Image]:
        """Convert PDF pages to images"""

    def compare_pages(self, original: Image, generated: Image) -> Score:
        """Calculate similarity metrics"""

    def generate_report(self, scores: List[Score]) -> Report:
        """Generate evaluation report with visualizations"""
```

**Cross-Reference Resolution Evaluation:**

Cross-references typically appear in questions, not answers. Therefore:
- **Answers**: Should remain unchanged - use exact/near-exact comparison
- **Questions**: Intentionally modified - use semantic validation

```python
class CrossReferenceEvaluator:
    def normalize_latex(self, latex: str) -> str:
        """Normalize whitespace and LaTeX formatting for comparison"""

    def compare_answers(
        self,
        original: ExtractionResult,
        resolved: ExtractionResult
    ) -> AnswerComparison:
        """Compare answers - should be nearly identical"""
        orig_normalized = self.normalize_latex(original.answer_latex)
        resolved_normalized = self.normalize_latex(resolved.answer_latex)

        exact_match = orig_normalized == resolved_normalized
        similarity = compute_similarity(orig_normalized, resolved_normalized)

        return AnswerComparison(
            exact_match=exact_match,
            similarity_score=similarity,
            flag_for_review=(similarity < 0.95)
        )

    def verify_self_contained(self, resolved: ExtractionResult) -> bool:
        """Ensure no cross-references remain in resolved Q&A"""

    def validate_question_semantics(
        self,
        original: ExtractionResult,
        referenced: ExtractionResult,
        resolved: ExtractionResult
    ) -> SemanticValidation:
        """Use LLM to verify question was correctly augmented"""
```

**Evaluation Rules for Resolved Q&As:**

| Answer Similarity | Result | Action |
|-------------------|--------|--------|
| ≥ 99% | Pass | Minor normalization differences acceptable |
| 95-99% | Warning | Review recommended |
| < 95% | Fail | Resolution error - requires manual review |

**Evaluation Flow:**
```
For each Q&A:
├── If NOT resolved:
│   └── Visual SSIM comparison with original PDF
│
├── If resolved:
│   ├── Answer Evaluation:
│   │   ├── Normalize both original and resolved answers
│   │   ├── Compute similarity score
│   │   └── Flag if similarity < 95%
│   │
│   ├── Question Evaluation:
│   │   ├── Verify all cross-references resolved
│   │   ├── Self-containment check (no remaining refs)
│   │   └── LLM semantic validation (context correctly inlined)
│   │
│   └── Report:
│       ├── Answer match score
│       ├── References resolved
│       └── Review priority
│
└── Both:
    └── LaTeX compilation check (must compile without errors)
```

---

### 9. Human Review Interface (`src/reviewer.py`)

**Responsibilities:**
- Select random samples for review
- Display side-by-side comparison
- Collect accept/reject decisions
- Log corrections for improvement
- Flag Q&As with resolved cross-references for special attention

**Interface Options:**

**Option A: CLI Interface (Simpler)**
```
$ python -m pdf_extractor review --sample-rate 0.05

Reviewing Q&A 2.8a (1/10)
────────────────────────────
[Original PDF region shown]
[Extracted LaTeX rendered]
────────────────────────────
[A]ccept | [R]eject | [E]dit | [S]kip >
```

**Option B: Web Interface (Better UX)**
- Flask/FastAPI backend
- React/HTML frontend
- Side-by-side view with zoom
- Batch review mode

**Recommendation:** Start with CLI, add web interface later.

---

## Data Flow

```
Input PDF
    │
    ▼
┌─────────────────────────────────────────────┐
│ 1. PDF Processing                            │
│    - Convert to images (300 DPI)             │
│    - Extract embedded images                  │
│    - Output: page_images/, figures/          │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ 2. LLM Extraction (batched, with context)    │
│    - Send 2-3 pages at a time                │
│    - Extract structured Q&A JSON             │
│    - Identify figure regions                 │
│    - Output: raw_extractions/                │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ 3. Post-Processing                           │
│    - Merge multi-page Q&As                   │
│    - Split multi-part questions              │
│    - Validate structure                      │
│    - Output: processed_qas.json              │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ 4. Cross-Reference Resolution                │
│    - Detect cross-references                 │
│    - Use LLM to inline relevant context      │
│    - Make each Q&A self-contained            │
│    - Output: resolved_qas.json               │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ 5. LaTeX Generation                          │
│    - Generate LaTeX document                 │
│    - Include figure references               │
│    - Output: output.tex, figures/            │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ 6. Evaluation                                │
│    - Compile LaTeX                           │
│    - Compare with original                   │
│    - Generate quality scores                 │
│    - Verify cross-reference resolution       │
│    - Output: evaluation_report.html          │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ 7. Human Review (optional)                   │
│    - Random sampling                         │
│    - Side-by-side comparison                 │
│    - Accept/Reject/Edit                      │
│    - Output: review_log.json                 │
└─────────────────────────────────────────────┘
    │
    ▼
Final Output: output.tex + figures/
```

---

## Project Structure

```
pdf-extractor/
├── pyproject.toml
├── README.md
├── src/
│   ├── __init__.py
│   ├── pipeline.py          # Main orchestrator
│   ├── pdf_processor.py     # PDF to images
│   ├── figure_extractor.py  # Figure detection
│   ├── llm_extractor.py     # LLM vision extraction
│   ├── merger.py            # Multi-page merging
│   ├── splitter.py          # Multi-part splitting
│   ├── reference_resolver.py # Cross-reference resolution
│   ├── latex_generator.py   # LaTeX output
│   ├── evaluator.py         # Quality evaluation
│   ├── reviewer.py          # Human review interface
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py          # Base LLM interface
│   │   ├── openai.py        # OpenAI GPT-4o
│   │   └── anthropic.py     # Claude
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── extraction.py    # Pydantic models
│   └── utils/
│       ├── __init__.py
│       ├── image.py         # Image utilities
│       └── latex.py         # LaTeX utilities
├── tests/
│   ├── __init__.py
│   ├── test_pdf_processor.py
│   ├── test_llm_extractor.py
│   └── test_evaluator.py
├── prompts/
│   ├── extraction.md        # Main extraction prompt
│   └── figure_detection.md  # Figure detection prompt
└── output/                   # Generated outputs
```

---

## Implementation Phases

### Phase 1: Core Extraction (MVP) ✅ COMPLETED
1. ✅ PDF processor - page to image conversion
2. ✅ Basic LLM extractor (both providers)
3. ✅ Simple LaTeX generator
4. ✅ Basic CLI interface

**Deliverable:** Can extract Q&A from simple pages

### Phase 1.5: Cross-Reference Resolution ✅ COMPLETED
1. ✅ Implement reference detection with LLM (more accurate than regex)
2. ✅ Create LLM-based resolution prompt
3. ✅ Build CrossReferenceResolver class
4. ✅ Integrate into pipeline between extraction and output
5. ✅ Add resolution tracking for evaluation
6. ✅ Fix multi-page question part detection (pass context between pages)
7. ✅ Add Q&A sorting (parent questions before sub-parts)

**Deliverable:** Self-contained Q&A pairs suitable for LLM fine-tuning

### Phase 1.6: LaTeX Output Improvements ✅ COMPLETED
1. ✅ Add unicode-to-LaTeX conversion (90+ symbols)
2. ✅ Validate LaTeX compilation with --compile CLI flag
3. ✅ Improve extraction prompt for consistent math mode

**Deliverable:** Clean, compilable LaTeX output

### Phase 2: Robustness ✅ COMPLETED
1. ✅ Multi-page Q&A stitching (merge solutions that span pages)
2. ✅ Multi-part question splitting (already working in MVP)
3. ✅ Figure extraction (embedded images + vector drawings)

**Deliverable:** Handles complex documents

### Phase 3: Quality Assurance ✅ COMPLETED
1. ✅ Evaluation pipeline (`src/evaluator.py`)
2. ✅ Cross-reference resolution validation (answer similarity, remaining refs check)
3. ✅ Human review interface (`src/reviewer.py`)
4. ✅ Quality metrics and reporting (JSON reports, CLI output)

**Deliverable:** Production-ready with quality guarantees

### Phase 4: Optimization
1. Batching and cost optimization
2. Caching and incremental processing
3. Performance tuning

**Deliverable:** Cost-effective at scale

---

## Dependencies

```toml
[project]
dependencies = [
    # PDF Processing
    "pymupdf>=1.23.0",
    "pdf2image>=1.16.0",
    "Pillow>=10.0.0",

    # LLM Clients
    "openai>=1.0.0",
    "anthropic>=0.18.0",

    # Data Handling
    "pydantic>=2.0.0",

    # Evaluation
    "scikit-image>=0.21.0",  # For SSIM
    "numpy>=1.24.0",

    # CLI
    "typer>=0.9.0",
    "rich>=13.0.0",

    # Testing
    "pytest>=7.0.0",
]
```

---

## Configuration

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LLM Configuration
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    default_provider: str = "openai"  # or "anthropic"

    # Processing
    dpi: int = 300
    batch_size: int = 3  # pages per LLM call
    max_retries: int = 3

    # Evaluation
    ssim_threshold: float = 0.85

    # Review
    sample_rate: float = 0.05  # 5% random sampling

    class Config:
        env_file = ".env"
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LLM hallucination | Multi-pass verification, evaluation pipeline |
| Complex math errors | Specialized prompts, LaTeX validation |
| Figure detection failure | Fallback to embedded image extraction |
| API cost overrun | Batching, caching, cost monitoring |
| Multi-page merge errors | Conservative merging, human review flag |

---

## Success Criteria

1. **Accuracy**: >95% of Q&A pairs correctly extracted (measured by human review)
2. **Completeness**: 100% of questions detected (no missing Q&As)
3. **LaTeX Validity**: 100% of output compiles without errors
4. **Visual Similarity**: SSIM > 0.85 between original and regenerated
5. **Part Splitting**: All multi-part questions correctly split with proper numbering

---

## Decisions Made

| Question | Decision |
|----------|----------|
| Resumption support | **Yes** - checkpoint after each page |
| Output formats | **Both JSON + LaTeX** |
| Batch processing | **Single PDF** at a time |

---

## Checkpointing Strategy

To support resumption:

```python
# Checkpoint structure saved after each page
checkpoint = {
    "pdf_path": "input.pdf",
    "total_pages": 250,
    "last_processed_page": 47,
    "extracted_qas": [...],  # All Q&As extracted so far
    "pending_merges": [...], # Partial Q&As awaiting next page
    "figure_manifest": {...},
    "timestamp": "2024-01-15T10:30:00Z"
}
```

Checkpoints saved to: `output/.checkpoint.json`

On restart:
1. Detect existing checkpoint
2. Prompt user: "Resume from page 47? [Y/n]"
3. Load state and continue

---

## Output Formats

### 1. JSON Output (`output/extracted_qas.json`)

```json
{
  "metadata": {
    "source_pdf": "textbook.pdf",
    "extraction_date": "2024-01-15",
    "total_questions": 150,
    "model_used": "gpt-4o"
  },
  "questions": [
    {
      "id": "2.7",
      "question_latex": "\\textbf{Voronoi description...}",
      "answer_latex": "Since a norm is always...",
      "figures": [],
      "page_range": [1, 1]
    },
    {
      "id": "2.8a",
      "question_latex": "Which of the following sets...",
      "answer_latex": "S is a polyhedron...",
      "figures": ["figures/fig_2.8a_1.png"],
      "page_range": [1, 2]
    }
  ]
}
```

### 2. LaTeX Output (`output/extracted_qas.tex`)

Full compilable document with all Q&A pairs and figure references.
