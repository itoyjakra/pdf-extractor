We need to build an accurate extractor that is capable of extracting questions and answers from
PDF documents. Here are the specs and requirements:

1. The document is math heavy, the 'test_sample.pdf' shows a few pages of the PDF.
2. Accuracy of extraction is number one priority - these QnA pairs will be used to
   fine tune an LLM
3. The input to the pipeline is a PDF document
4. The output from the pipeline is a latex document that contains all the question and answer
   pairs from the PDF
5. The PDF contains figures for some questions - the pipeline needs to handle it properly
6. Some QnA spans across multiple pages
7. Some questions have multiple parts - these should appear as separate QnA pairs, while preserving
   the numbers. For example, if question 3.4 has three parts a,b and c, the final output should
   have three QnA pairs - 3.4a, 3.4b and 3.4c
8. Built-in evaluation should be part of the pipeline - it should have a component that will
   be able to run the generated latex and compare the output against the original PDF
9. The pipeline should be fully automated but should have an option for random human spot checks
10. Think about all possible solutions, including LLM based agentic workflows, fully engineered
    workflows or a mix of both.
11. **Cross-reference resolution**: Some questions/answers reference other questions (e.g., "Using
    the result from 2.7..." or "As in the previous question..."). Since the extracted QnA pairs
    will be used for LLM fine-tuning, each Q&A must be self-contained. The pipeline should:
    - Automatically detect cross-references
    - Resolve them by inlining only the relevant context from referenced questions
    - Make each Q&A pair independent and usable for training
    - This should happen before evaluation
