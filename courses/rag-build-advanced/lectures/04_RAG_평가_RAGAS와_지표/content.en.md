---
lecture_no: 4
title: "Evaluating RAG: RAGAS and the Four Metrics That Matter"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=7_LTU0LA374
  - https://www.youtube.com/watch?v=5fp6e5nhJRk
  - https://www.youtube.com/watch?v=cRz0BWkuwHg
---

# Evaluating RAG: RAGAS and the Four Metrics That Matter

## Learning Objectives
- Define the four core RAG metrics - **Faithfulness**, **Answer Relevancy**, **Context Precision**, **Context Recall** - and understand exactly what each one diagnoses.
- Build a small **golden set** (question + reference answer + expected sources) that you can re-run on every code change.
- Use the **RAGAS** framework to compute these metrics with one function call, and read the results to decide whether the retriever or the generator is the bottleneck.
- Track regressions across versions so a "small prompt tweak" never silently drops accuracy by 10%.

## Body

### Why "vibe checking" stops working around demo day

Every team building RAG starts by clicking around the demo and saying "looks good". That works for the first week. Then someone changes the chunk size, someone else swaps the embedding model, the prompt gets reworded - and nobody can tell whether the answers are getting better or worse. By the time a customer complains, three changes have shipped on top of each other and you cannot bisect.

A RAG system has **two moving parts**: a *retriever* (does it pull the right chunks?) and a *generator* (does the LLM actually use those chunks correctly?). When the answer is wrong, you need to know which side failed. That diagnostic question is exactly what RAG-specific metrics are designed to answer.

Traditional NLP metrics like BLEU and ROUGE measure n-gram overlap with a reference text. They are fine for translation and summarization, where there is one "right answer" worded one specific way. They are useless for RAG, because a good RAG answer can be phrased many ways and still be correct. You need metrics that ask: *is this answer grounded in the retrieved evidence? Did the retriever bring the right evidence in the first place?*

### The four metrics, plainly

RAGAS, the de facto open-source evaluation framework for RAG, organizes its scores along the two axes of the system - retrieval and generation. Four metrics do most of the work.

**1. Context Precision** - *How much of what the retriever returned was actually useful?*

If the retriever pulled 5 chunks and only 2 were relevant to the question, precision is 2/5 = 0.40. High precision means low noise in the prompt. Low precision wastes context window and dilutes the LLM's attention.

**2. Context Recall** - *Did the retriever find everything it needed?*

Out of all the chunks that *should* have been retrieved (the ones needed to answer the question), what fraction did the retriever actually return? If three chunks in the corpus contain founding facts about Tesla and the retriever returned two, recall is 2/3 = 0.67. Low recall is the silent killer of RAG: the missing chunk simply never reaches the LLM, and the answer is incomplete with no warning.

**3. Faithfulness** - *Is the answer actually supported by the retrieved chunks?*

Take each claim in the generated answer; check whether the retrieved context contains evidence for it. Claims that are not in the context count as hallucinations. Faithfulness drops every time the LLM "embellishes" with facts it pulled from its training data instead of from your documents. For regulated use cases this is the single most important metric.

**4. Answer Relevancy** - *Does the answer actually address the question that was asked?*

Even a perfectly faithful, accurate answer can miss the point. If a user asks *"how do I cancel?"* and the system replies with a (correct) description of the *pricing tiers*, relevancy is low. RAGAS measures this by asking an LLM to generate questions that the answer would naturally respond to, then comparing those back to the original question.

| Metric | Diagnoses | Low value means |
|---|---|---|
| Context Precision | Retriever (noise) | Too many irrelevant chunks in top-K |
| Context Recall | Retriever (gap) | Right chunks not making it into top-K |
| Faithfulness | Generator | LLM is hallucinating beyond the context |
| Answer Relevancy | Generator | LLM answering a different question |

Reading them together is the whole point. If recall is low and faithfulness is low, fix the retriever first - the LLM cannot ground itself in evidence it never saw. If recall and precision are both high but faithfulness is low, the LLM is the problem; tighten the prompt or switch models.

### Building a golden set

You cannot compute any of these without an evaluation dataset. The minimum viable form is a small spreadsheet, often called the **golden set**, with four columns per row:

- `question` - what a real user might ask.
- `ground_truth` - the answer you (a human expert) consider correct.
- `expected_contexts` - the document chunks or IDs that *should* be retrieved.
- `notes` - edge cases, intentional ambiguity, expected refusals.

Aim for 30-100 questions to start. Cover:

- The five or ten most common real user queries (pull from logs).
- Questions where the answer is *not* in your corpus (you want the system to refuse, not hallucinate).
- Compositional questions ("compare X and Y") to stress-test decomposition.
- Multi-language questions if your audience is bilingual.

> A tiny, focused golden set beats a giant one you never run. 50 well-chosen questions you can evaluate in 2 minutes after every change will catch more regressions than 5,000 you run once a quarter.

RAGAS can also **synthesize a golden set** for you from your corpus. It uses an LLM to read your documents and generate plausible questions plus reference answers - useful for cold-starting evaluation when you have no real query logs yet.

> **Important distinction: what RAGAS actually uses.** Of the four golden-set columns above, RAGAS only consumes `question` and `ground_truth` (plus your system's `answer` and the `contexts` it retrieved at run time). It does **not** read your `expected_contexts` list. Instead, RAGAS `context_recall` works by asking an LLM judge to take each sentence of the `ground_truth` answer and check whether the retrieved contexts contain the evidence for it - using the reference *answer* as a proxy for "what should have been retrieved." That makes RAGAS recall an **LLM-judged approximation**, not a true document-level recall. If you need the strict version - "did the retriever return chunks X, Y, Z from my corpus?" - you have to compute it yourself by comparing the retriever's chunk IDs against your hand-curated `expected_contexts`. Keep the `expected_contexts` column in your golden set anyway: it is invaluable for human debugging and for that stricter recall calculation, even though RAGAS itself will ignore it.

### Running RAGAS in practice

The setup is straightforward. You need: your questions, your system's answers, the contexts your system retrieved, and the ground-truth answers.

```python
# pip install ragas datasets

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness, answer_relevancy,
    context_precision, context_recall,
)

# Build the eval dataset from your own RAG outputs.
# Note the RAGAS schema:
#   - key is `ground_truths` (plural)
#   - value is a list-of-lists: one inner list of reference answers per question
samples = {
    "question": [
        "When was Einstein born?",
        "Who won the most Super Bowls?",
    ],
    "answer": [                # what your RAG system produced
        "Albert Einstein was born on March 14, 1879.",
        "The New England Patriots have won the most Super Bowls.",
    ],
    "contexts": [              # the chunks your retriever returned
        ["Einstein was born on 14 March 1879 in Ulm, Germany ..."],
        ["The Super Bowl is the annual championship game of the NFL ..."],
    ],
    "ground_truths": [         # list of lists - one or more reference answers per question
        ["Albert Einstein was born on 14 March 1879."],
        ["The Pittsburgh Steelers and the New England Patriots are tied with 6 wins each."],
    ],
}
eval_ds = Dataset.from_dict(samples)

results = evaluate(
    eval_ds,
    metrics=[faithfulness, answer_relevancy,
             context_precision, context_recall],
)
print(results)
# {'faithfulness': 0.50, 'answer_relevancy': 0.83,
#  'context_precision': 0.50, 'context_recall': 0.50}
```

Interpret the result row by row. In the Einstein example, all four metrics are high - retrieval found the right chunk and the LLM stayed grounded. In the Super Bowl example, the retrieved context did not actually mention the Patriots, so **faithfulness dropped to zero** (the answer is correct by general knowledge but not supported by the retrieved context). That is the diagnostic signal: the LLM bypassed the retrieval evidence and pulled from its own memory - dangerous behavior in production.

### The evaluation loop fits into the pipeline like a unit test

A clean integration looks like the following: every commit (or at least every release) runs the golden set through the current RAG configuration and reports the four scores side-by-side with the previous run.

```mermaid RAG evaluation loop: golden set drives the system, RAGAS scores the outputs, regressions are caught before deploy
flowchart LR
    GS[Golden Set<br/>questions + ground truth]
    RAG[RAG System under test]
    OUT[Generated answer<br/>+ retrieved contexts]
    RAGAS[RAGAS<br/>faithfulness, relevancy,<br/>precision, recall]
    SCORES[Score report<br/>vs previous run]
    DECIDE{Regression?}
    SHIP[Ship change]
    DIAG[Diagnose:<br/>retriever or generator?]
    GS --> RAG --> OUT --> RAGAS --> SCORES --> DECIDE
    DECIDE -- No --> SHIP
    DECIDE -- Yes --> DIAG --> RAG
```

Treat RAGAS output the same way you treat unit-test output. A 3% drop in faithfulness on a 50-question set is a clear signal that something regressed - investigate before merging.

### What the metrics will *not* tell you

RAG metrics are powerful but not complete. A few gaps to be aware of:

- **LLM-as-judge bias.** Most RAGAS metrics use an LLM (typically GPT-4-class) as a judge under the hood. That judge has its own biases - favoring longer answers, favoring its own writing style. Pair RAGAS with periodic human review.
- **They cannot measure tone, brand voice, or formatting.** Add lightweight separate checks for those.
- **They evaluate the answer that *was* produced, not the one users wanted.** Log real user feedback (thumbs up/down, follow-up rephrasings) and feed common failures back into the golden set.
- **Cost.** Every RAGAS evaluation makes one or more LLM calls per metric per example. A 100-question set across four metrics is ~400-1,000 LLM calls. Run it on commits but cap the budget.

### A simple optimization workflow

Once the metrics are in place, improving RAG becomes systematic instead of guesswork:

1. **Baseline.** Run RAGAS on the current system. Record the four scores.
2. **Find the worst metric.** If Context Recall is the lowest, the retriever is missing chunks. Try hybrid search (Lecture 1), query transformation (Lecture 3), or better chunking.
3. **Change one thing.** Swap embedding model, raise top-K, add HyDE - one variable at a time.
4. **Re-run.** Compare the four scores against baseline. Keep the change only if the targeted metric rose without others falling.
5. **Promote.** Update the baseline, log the experiment, repeat on the next worst metric.

This loop, run weekly, is what turns a fragile demo into a system that actually gets better over time.

## Key Takeaways
- RAG has two failure surfaces - **retrieval** and **generation** - and you need separate metrics for each. The four-metric RAGAS suite covers both: **Context Precision/Recall** for retrieval, **Faithfulness/Answer Relevancy** for generation.
- A **golden set** of 30-100 hand-curated question/answer/expected-context rows is the minimum viable evaluation harness. Re-run it on every change.
- **RAGAS `context_recall` is an LLM-judged approximation** that uses the reference *answer* (`ground_truths`) as a proxy for what should have been retrieved - it does not read your `expected_contexts` list. For true document-level recall, compare retrieved chunk IDs against your hand-curated expected chunks yourself.
- **Faithfulness** is the metric to watch in regulated or high-stakes use cases - it catches the LLM "filling in" facts that the retrieved evidence does not support.
- RAGAS uses LLM-as-judge under the hood. Pair it with periodic human review and with cost limits, since each evaluation costs LLM calls.
- Improvement is an iterative loop: baseline -> identify the weakest metric -> change one variable -> re-measure -> promote. Vibe checks alone do not survive contact with production.
