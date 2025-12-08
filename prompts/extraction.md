# Q&A Extraction Prompt

You are extracting question and answer pairs from a math textbook PDF page. Your task is to identify all questions and their corresponding solutions, and convert them to LaTeX format.

## Instructions

1. **Identify Questions**: Look for numbered questions (e.g., "2.7", "2.8", "3.4")
2. **Multi-part Questions**: If a question has parts (a, b, c, d...), treat each part as a separate Q&A pair
3. **Extract Question Text**: Convert the complete question text to LaTeX format, preserving all math notation
4. **Extract Solution Text**: Convert the complete solution/answer to LaTeX format
5. **Note Continuations**: Flag if a question or answer appears to continue on the next page or is continued from a previous page
6. **Preserve Math**: Keep all mathematical notation in LaTeX format (equations, symbols, etc.)

## Output Format

Return your response as a JSON object with this exact structure:

```json
{
  "page_number": <page number>,
  "questions": [
    {
      "question_id": "<question number, e.g., '2.7'>",
      "parts": [
        {
          "part_id": null,
          "question_latex": "<full question in LaTeX>",
          "answer_latex": "<full solution in LaTeX>",
          "continues_next_page": false,
          "continued_from_previous": false
        }
      ]
    }
  ]
}
```

For multi-part questions, include each part separately:

```json
{
  "question_id": "2.8",
  "parts": [
    {"part_id": "a", "question_latex": "...", "answer_latex": "..."},
    {"part_id": "b", "question_latex": "...", "answer_latex": "..."},
    {"part_id": "c", "question_latex": "...", "answer_latex": "..."}
  ]
}
```

## Important Notes

- For multi-part questions, include the question stem (intro text) in EACH part's question_latex
- Mark `continues_next_page: true` if the solution is incomplete and continues on the next page
- Mark `continued_from_previous: true` if this appears to be a continuation from a previous page
- Preserve ALL LaTeX formatting: `\textbf{}`, `\mathbb{}`, `\sum`, `\int`, equations, etc.
- Include solution markers like "Solution." in the answer_latex
- If you see a figure/diagram, note it in the text as "[Figure: ...]" but don't try to recreate it

## CRITICAL: Handling Question Parts Across Pages

When you see lettered parts like (b), (c), (d) at the TOP of a page WITHOUT a preceding question number on that same page:
1. These are CONTINUATIONS of a multi-part question from the previous page
2. Look at the "Context from Previous Page" section (if provided) to find the correct question ID
3. Do NOT assign them to a different question number that appears later on this page
4. The question number for these parts should be the LAST question ID from the previous page

Example: If the previous page ended with question 2.17a, and this page starts with "(b) The hyperplane...", that is question 2.17b, NOT 2.18b.

## Example

For a page showing:
```
2.7 Let a and b be distinct points in R^n. Show that the set {x | ||x-a||₂ ≤ ||x-b||₂} is a halfspace.

Solution. Since a norm is always nonnegative, we have ||x-a||₂ ≤ ||x-b||₂ if and only if...
```

Return:
```json
{
  "page_number": 1,
  "questions": [
    {
      "question_id": "2.7",
      "parts": [
        {
          "part_id": null,
          "question_latex": "Let $a$ and $b$ be distinct points in $\\mathbb{R}^n$. Show that the set $\\{x \\mid \\|x-a\\|_2 \\leq \\|x-b\\|_2\\}$ is a halfspace.",
          "answer_latex": "\\textbf{Solution.} Since a norm is always nonnegative, we have $\\|x-a\\|_2 \\leq \\|x-b\\|_2$ if and only if...",
          "continues_next_page": false,
          "continued_from_previous": false
        }
      ]
    }
  ]
}
```

Now extract all Q&A pairs from the provided page image.
