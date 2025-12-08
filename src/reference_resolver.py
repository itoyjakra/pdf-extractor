"""Cross-reference resolver - makes Q&A pairs self-contained for LLM fine-tuning."""

import json
from pydantic import BaseModel, Field
from .models import BaseLLM
from .schemas import ExtractionResult


class DetectedReference(BaseModel):
    """A cross-reference detected by LLM."""

    reference_text: str = Field(description="The exact text containing the reference")
    reference_type: str = Field(description="Type: theorem, remark, question, definition, etc.")
    reference_id: str | None = Field(description="ID if identifiable (e.g., '2.2', '3.4a')")
    is_essential: bool = Field(description="Whether this reference is essential to understand the Q&A")
    context_needed: str = Field(description="What information from the reference is needed")


class DetectionResult(BaseModel):
    """Result of LLM-based reference detection."""

    has_references: bool = Field(description="Whether any cross-references were found")
    references: list[DetectedReference] = Field(default_factory=list)
    is_self_contained: bool = Field(description="Whether the Q&A can stand alone without the references")


class ResolutionResult(BaseModel):
    """Result of resolving cross-references for a Q&A."""

    original: ExtractionResult = Field(description="Original Q&A before resolution")
    resolved: ExtractionResult = Field(description="Resolved Q&A (may be same as original)")
    had_references: bool = Field(description="Whether any references were detected")
    references_found: list[str] = Field(default_factory=list, description="List of references found")
    context_inlined: str | None = Field(default=None, description="Context that was inlined")
    answer_changed: bool = Field(default=False, description="Whether the answer was modified")
    could_not_resolve: bool = Field(default=False, description="True if reference found but couldn't be resolved")


DETECTION_PROMPT = """Analyze this math Q&A pair and identify ANY cross-references to external content.

## Q&A to Analyze (ID: {qa_id})

**Question:**
{question_latex}

**Answer:**
{answer_latex}

## Your Task

Identify ALL references to external content, including:
- References to theorems, lemmas, corollaries, propositions
- References to remarks, definitions, examples
- References to other questions or exercises (e.g., "from 2.7", "in problem 3.4")
- References to sections, chapters, pages
- References to equations by number
- Implicit references like "as shown earlier", "by the previous result", "using the above"
- Any mention that requires knowledge from elsewhere to fully understand

## Return Format

Return ONLY a JSON object (no markdown code blocks):
{{
  "has_references": true/false,
  "references": [
    {{
      "reference_text": "the exact phrase containing the reference",
      "reference_type": "remark|theorem|question|definition|equation|section|implicit|other",
      "reference_id": "2.2" or null if not identifiable,
      "is_essential": true/false (is this needed to understand the Q&A?),
      "context_needed": "brief description of what information is needed from the reference"
    }}
  ],
  "is_self_contained": true/false (can someone understand this Q&A without the referenced content?)
}}

If no references found:
{{
  "has_references": false,
  "references": [],
  "is_self_contained": true
}}
"""


RESOLUTION_PROMPT = """You are making a math Q&A pair self-contained for LLM fine-tuning.

## Current Q&A (ID: {current_id})

**Question:**
{question_latex}

**Answer:**
{answer_latex}

## Detected Reference

The following reference was detected:
- **Reference:** {reference_text}
- **Type:** {reference_type}
- **Context needed:** {context_needed}

## Referenced Content (ID: {ref_id})

**Question:**
{ref_question_latex}

**Answer:**
{ref_answer_latex}

## Your Task

1. Extract ONLY the relevant information from the referenced content
2. Rewrite the current Q&A to be completely self-contained
3. The rewritten Q&A should make sense to someone who hasn't seen the referenced content
4. Keep the inlined context concise - only what's necessary
5. Maintain all LaTeX mathematical notation and correctness
6. IMPORTANT: The ANSWER should remain as unchanged as possible. Only modify it if absolutely necessary.

## Return Format

Return ONLY a JSON object (no markdown code blocks):
{{
  "relevant_context": "the specific information extracted from the reference",
  "rewritten_question": "the self-contained question with context naturally incorporated",
  "rewritten_answer": "the answer (should be nearly identical to original unless changes are essential)",
  "answer_was_modified": true/false
}}
"""


RESOLUTION_PROMPT_NO_SOURCE = """You are making a math Q&A pair self-contained for LLM fine-tuning.

## Current Q&A (ID: {current_id})

**Question:**
{question_latex}

**Answer:**
{answer_latex}

## Detected Reference (SOURCE NOT AVAILABLE)

The following reference was detected but its source content is not available:
- **Reference:** {reference_text}
- **Type:** {reference_type}
- **Context needed:** {context_needed}

## Your Task

Since the referenced content is not available, you need to:
1. Infer what the reference likely contains based on context
2. Rewrite the Q&A to be self-contained by either:
   - Adding a brief explanation of what the referenced result likely states
   - Rephrasing to remove dependency on the reference while preserving meaning
3. If you cannot reasonably infer the content, note this in the response
4. IMPORTANT: The ANSWER should remain as unchanged as possible.

## Return Format

Return ONLY a JSON object (no markdown code blocks):
{{
  "could_infer": true/false,
  "inferred_context": "what you inferred the reference contains (or null if couldn't infer)",
  "rewritten_question": "the self-contained question",
  "rewritten_answer": "the answer (minimally modified)",
  "answer_was_modified": true/false,
  "confidence": "high|medium|low"
}}
"""


class CrossReferenceResolver:
    """Resolves cross-references in Q&A pairs to make them self-contained."""

    def __init__(self, llm: BaseLLM):
        """Initialize resolver.

        Args:
            llm: LLM provider for detection and resolution
        """
        self.llm = llm

    def _call_llm_text(self, prompt: str) -> str:
        """Call LLM with text-only prompt.

        Args:
            prompt: The text prompt

        Returns:
            LLM response string
        """
        from PIL import Image

        # Create a minimal placeholder image
        placeholder = Image.new('RGB', (100, 100), color='white')

        full_prompt = f"""Ignore the image. Process this text request:

{prompt}"""

        return self.llm.extract_from_image(placeholder, full_prompt)

    def _parse_json_response(self, response: str) -> dict | None:
        """Parse JSON from LLM response.

        Args:
            response: Raw LLM response

        Returns:
            Parsed dict or None if parsing failed
        """
        try:
            # Try to extract JSON from response
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            else:
                json_str = response.strip()

            return json.loads(json_str)
        except json.JSONDecodeError:
            return None

    def detect_references(self, qa: ExtractionResult) -> DetectionResult:
        """Detect cross-references in a Q&A using LLM.

        Args:
            qa: The Q&A to analyze

        Returns:
            DetectionResult with found references
        """
        prompt = DETECTION_PROMPT.format(
            qa_id=qa.id,
            question_latex=qa.question_latex,
            answer_latex=qa.answer_latex
        )

        response = self._call_llm_text(prompt)
        data = self._parse_json_response(response)

        if data is None:
            print(f"  [WARN] Failed to parse detection response for {qa.id}")
            return DetectionResult(
                has_references=False,
                references=[],
                is_self_contained=True
            )

        try:
            references = []
            for ref_data in data.get("references", []):
                references.append(DetectedReference(
                    reference_text=ref_data.get("reference_text", ""),
                    reference_type=ref_data.get("reference_type", "other"),
                    reference_id=ref_data.get("reference_id"),
                    is_essential=ref_data.get("is_essential", False),
                    context_needed=ref_data.get("context_needed", "")
                ))

            return DetectionResult(
                has_references=data.get("has_references", False),
                references=references,
                is_self_contained=data.get("is_self_contained", True)
            )
        except Exception as e:
            print(f"  [WARN] Error processing detection result for {qa.id}: {e}")
            return DetectionResult(
                has_references=False,
                references=[],
                is_self_contained=True
            )

    def resolve(
        self,
        qa: ExtractionResult,
        detection: DetectionResult,
        all_qas: dict[str, ExtractionResult],
    ) -> ResolutionResult:
        """Resolve cross-references in a single Q&A.

        Args:
            qa: The Q&A to resolve
            detection: Detection result with found references
            all_qas: Dictionary of all Q&As by ID

        Returns:
            ResolutionResult with resolved Q&A
        """
        if not detection.has_references or detection.is_self_contained:
            return ResolutionResult(
                original=qa,
                resolved=qa,
                had_references=detection.has_references,
                references_found=[r.reference_text for r in detection.references],
                context_inlined=None,
                answer_changed=False
            )

        # Find essential references that need resolution
        essential_refs = [r for r in detection.references if r.is_essential]

        if not essential_refs:
            return ResolutionResult(
                original=qa,
                resolved=qa,
                had_references=True,
                references_found=[r.reference_text for r in detection.references],
                context_inlined=None,
                answer_changed=False
            )

        # Try to resolve the first essential reference
        ref = essential_refs[0]
        ref_qa = all_qas.get(ref.reference_id) if ref.reference_id else None

        if ref_qa:
            # We have the referenced content - use full resolution
            prompt = RESOLUTION_PROMPT.format(
                current_id=qa.id,
                question_latex=qa.question_latex,
                answer_latex=qa.answer_latex,
                reference_text=ref.reference_text,
                reference_type=ref.reference_type,
                context_needed=ref.context_needed,
                ref_id=ref_qa.id,
                ref_question_latex=ref_qa.question_latex,
                ref_answer_latex=ref_qa.answer_latex
            )
        else:
            # Referenced content not available - try to infer
            prompt = RESOLUTION_PROMPT_NO_SOURCE.format(
                current_id=qa.id,
                question_latex=qa.question_latex,
                answer_latex=qa.answer_latex,
                reference_text=ref.reference_text,
                reference_type=ref.reference_type,
                context_needed=ref.context_needed
            )

        response = self._call_llm_text(prompt)
        data = self._parse_json_response(response)

        if data is None:
            print(f"  [WARN] Failed to parse resolution response for {qa.id}")
            return ResolutionResult(
                original=qa,
                resolved=qa,
                had_references=True,
                references_found=[r.reference_text for r in detection.references],
                context_inlined=None,
                answer_changed=False,
                could_not_resolve=True
            )

        # Handle response based on whether source was available
        if ref_qa:
            context = data.get("relevant_context")
            rewritten_q = data.get("rewritten_question", qa.question_latex)
            rewritten_a = data.get("rewritten_answer", qa.answer_latex)
            answer_modified = data.get("answer_was_modified", False)
        else:
            if not data.get("could_infer", False):
                return ResolutionResult(
                    original=qa,
                    resolved=qa,
                    had_references=True,
                    references_found=[r.reference_text for r in detection.references],
                    context_inlined=None,
                    answer_changed=False,
                    could_not_resolve=True
                )
            context = data.get("inferred_context")
            rewritten_q = data.get("rewritten_question", qa.question_latex)
            rewritten_a = data.get("rewritten_answer", qa.answer_latex)
            answer_modified = data.get("answer_was_modified", False)

        resolved_qa = ExtractionResult(
            id=qa.id,
            question_latex=rewritten_q,
            answer_latex=rewritten_a,
            figures=qa.figures,
            page_range=qa.page_range
        )

        return ResolutionResult(
            original=qa,
            resolved=resolved_qa,
            had_references=True,
            references_found=[r.reference_text for r in detection.references],
            context_inlined=context,
            answer_changed=answer_modified
        )

    def resolve_all(
        self,
        qas: list[ExtractionResult]
    ) -> tuple[list[ExtractionResult], list[ResolutionResult]]:
        """Resolve all cross-references in a list of Q&As.

        Args:
            qas: List of Q&A pairs in document order

        Returns:
            Tuple of (resolved Q&As, resolution results for tracking)
        """
        # Build lookup dictionary
        all_qas = {qa.id: qa for qa in qas}

        resolved_qas = []
        resolution_results = []

        for i, qa in enumerate(qas):
            print(f"  Analyzing {qa.id} ({i+1}/{len(qas)})...", end=" ")

            # Step 1: Detect references using LLM
            detection = self.detect_references(qa)

            if not detection.has_references:
                print("no references")
                resolved_qas.append(qa)
                resolution_results.append(ResolutionResult(
                    original=qa,
                    resolved=qa,
                    had_references=False,
                    references_found=[],
                    context_inlined=None,
                    answer_changed=False
                ))
                continue

            essential_count = sum(1 for r in detection.references if r.is_essential)
            print(f"found {len(detection.references)} refs ({essential_count} essential)")

            # Step 2: Resolve if needed
            if detection.is_self_contained:
                resolved_qas.append(qa)
                resolution_results.append(ResolutionResult(
                    original=qa,
                    resolved=qa,
                    had_references=True,
                    references_found=[r.reference_text for r in detection.references],
                    context_inlined=None,
                    answer_changed=False
                ))
            else:
                result = self.resolve(qa, detection, all_qas)
                resolved_qas.append(result.resolved)
                resolution_results.append(result)

                # Update lookup with resolved version for chained references
                all_qas[qa.id] = result.resolved

                if result.context_inlined:
                    print(f"    -> Resolved: inlined context from reference")
                elif result.could_not_resolve:
                    print(f"    -> Could not resolve (source not available)")

        return resolved_qas, resolution_results
