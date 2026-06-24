---
lecture_no: 2
title: "Reranking and Context Filtering: Squeezing Precision out of Top-K"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=sGvXO7CVwc0
  - https://www.youtube.com/watch?v=aVgZE746OXw
  - https://www.youtube.com/watch?v=Pla_2NUk3Ug
---

# Reranking and Context Filtering: Squeezing Precision out of Top-K

## Learning Objectives
- Explain the 2-stage retrieval pattern: a fast bi-encoder for recall, followed by a slower but more precise cross-encoder for precision.
- Wire a reranking model (Cohere Rerank, BGE Reranker, or a local cross-encoder) into a LangChain RAG pipeline using `ContextualCompressionRetriever`.
- Use Maximal Marginal Relevance (MMR) to reduce duplicate chunks and balance relevance with diversity in the final context.

## Body

### Why one retriever is not the end of the story

Even with hybrid retrieval (Lecture 1) producing a great top-20 list, that is still too many chunks - and too noisy a set - to send straight to the LLM. There are three reasons:

- **Cost and latency.** Every chunk in the prompt is paid for, and longer prompts are slower to generate.
- **Attention dilution.** The more chunks you cram in, the more the model's attention spreads. A single critical sentence buried under 19 mediocre ones can be ignored.
- **Near-duplicates.** Real corpora repeat themselves. Five chunks that all paraphrase the same paragraph waste 80% of your context window without adding any new information.

The fix is to add a **second stage**: take the top 20-50 candidates from your fast retriever and re-score them with a slower, more accurate model that looks at each `(query, chunk)` pair individually. Then keep only the best 3-5. This 2-stage pattern is now the default architecture for high-quality RAG.

### Bi-encoders vs cross-encoders

To see why a second stage helps, compare how the two encoder families work.

A **bi-encoder** (what your vector database uses) embeds the query and every chunk into a single vector each, independently, and then ranks by cosine similarity. Because the chunks were embedded at indexing time, the query side only needs one new embedding to search millions of documents. This is what makes vector search fast - but the trade-off is that the query and the chunk never actually "see" each other. Their match is decided by how close two pre-computed vectors land in space.

A **cross-encoder** does the opposite. It takes a `(query, chunk)` pair, glues them together with a separator token, and feeds the whole thing through a transformer (typically BERT-based). Inside the model, every token of the query can attend to every token of the chunk and vice versa. This *late interaction* makes the relevance judgment far more accurate - but it also means the model has to be run *once per candidate at query time*. You cannot precompute it. So cross-encoders are too slow to rank millions of documents, but they are perfect for re-scoring a top-20 list in tens of milliseconds.

The 2-stage retrieval architecture turns each model's weakness into the other's strength: the bi-encoder narrows millions of chunks to dozens fast, and the cross-encoder rescores those dozens with high precision.

```mermaid 2-stage retrieval: bi-encoder narrows the corpus, cross-encoder rescores the shortlist
flowchart LR
    Q[User Query]
    BI["Bi-Encoder Retriever<br/>fast, cosine similarity"]
    INDEX[(Vector + BM25 Index)]
    TOPN["Top-N candidates<br/>e.g. N = 20-50"]
    CROSS["Cross-Encoder Reranker<br/>slow, per-pair attention"]
    TOPK["Top-K reranked<br/>e.g. K = 3-5"]
    LLM[LLM Generator]
    Q --> BI
    INDEX --> BI
    BI --> TOPN --> CROSS --> TOPK --> LLM
```

### Plugging a reranker into LangChain

LangChain wraps reranking inside `ContextualCompressionRetriever`: you pass it a base retriever (your hybrid retriever from Lecture 1) and a "compressor" that filters or reorders the documents the base retriever returns. Two compressors matter for us: `CohereRerank` (hosted) and `CrossEncoderReranker` (local).

**Option A - Cohere Rerank (managed, fastest to set up):**

```python
import os
from langchain_cohere import CohereRerank
from langchain.retrievers import ContextualCompressionRetriever

os.environ["COHERE_API_KEY"] = "..."

compressor = CohereRerank(model="rerank-multilingual-v3.0", top_n=3)
reranked_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=hybrid,           # from Lecture 1
)

docs = reranked_retriever.invoke("How do I configure SSO with our payroll vendor?")
```

`base_retriever` returns ~20 candidates. `CohereRerank` rescores them and keeps the top 3. Cohere charges per search (roughly $1 per 1,000 reranks at the time of writing) - cheap by RAG standards, and very fast.

**Option B - Local cross-encoder (no API calls, free, slightly slower):**

```python
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder

model = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base")
compressor = CrossEncoderReranker(model=model, top_n=3)

reranked_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=hybrid,
)
```

`BAAI/bge-reranker-base` is a strong, free, multilingual cross-encoder. For Korean/English mixed corpora `BAAI/bge-reranker-v2-m3` is a common pick. On a single CPU it adds 50-200ms per query for ~20 candidates; on a small GPU it disappears into the noise.

> Always retrieve *more* than you plan to send to the LLM. If you want 3 chunks in the prompt, ask the base retriever for at least 20. The reranker can only re-order what the first stage gave it - if the right chunk is not in the top 20, no reranker can save you.

### When a cross-encoder is not enough: LLM-as-reranker

Cross-encoders have one fundamental limitation. They take exactly `(query, chunk)` as input. You cannot inject extra instructions like *"prefer documents about Samsung Electronics specifically, ignore politically sensitive content, deduplicate near-identical chunks"*. The model just scores pairs - and it scores them according to what the *training* data thought was relevant, which is usually a generic, English-centric notion of relevance.

For domain-heavy use cases this matters. You may need a reranker that:

- Understands your domain (your company's products, regional context, internal terminology).
- Deduplicates among candidates instead of scoring each in isolation.
- Follows policy ("exclude anything tagged confidential", "prefer the latest version of a document").

The pragmatic alternative is an **LLM-as-reranker**: dump all 20 candidates into a single prompt and ask the model to return the indices of the best 3, in order, with reasons. Because today's LLMs have 128K-token context windows, all 20 candidates fit comfortably, and you pay for just one call instead of 20 cross-encoder runs.

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

rerank_prompt = ChatPromptTemplate.from_template("""
You are reranking RAG search results. Given the user query and a list
of candidate documents, return the indices of the top 3 most relevant,
in descending order of relevance.

Rules:
- Prioritize documents that directly answer the query intent.
- If two documents say almost the same thing, keep only the better one.
- Exclude any document tagged "confidential" in its metadata.

Query: {query}

Candidates:
{candidates}

Return JSON: {{"top_indices": [int, int, int], "reasoning": "..."}}
""")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
chain = rerank_prompt | llm | JsonOutputParser()

# ... call chain with formatted candidates ...
```

Smaller open-source models (Gemma 3, Qwen with extended input context, etc.) can run this locally if cost matters. LLM-rerankers tend to outperform cross-encoders on messy enterprise data, at the cost of higher latency per call.

### Maximal Marginal Relevance (MMR)

Reranking by relevance alone has a subtle problem: the top-K can all be near-duplicates of each other. If the most relevant chunk is *"Order #1234 shipped on 2024-03-12"* and chunks 2-5 are slight reformulations of the same fact, you have wasted four slots.

**Maximal Marginal Relevance (MMR)** fixes this by jointly optimizing for relevance to the query *and* dissimilarity from already-selected results. At each step it picks the chunk with the highest score on:

```
MMR(d) = lambda * sim(q, d)  -  (1 - lambda) * max_{d' in selected} sim(d, d')
```

- `lambda = 1.0` -> pure relevance (same as the base retriever).
- `lambda = 0.0` -> pure diversity (probably useless on its own).
- `lambda = 0.5` -> balanced; a good starting point.

LangChain exposes MMR directly on most vector stores:

```python
mmr_retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={
        "k": 5,           # final number returned
        "fetch_k": 20,    # how many candidates to consider
        "lambda_mult": 0.5,
    },
)
```

`fetch_k` is the candidate pool size, `k` is what comes out. You typically use MMR *after* hybrid retrieval but *instead of* or *before* a cross-encoder, depending on how badly your corpus suffers from duplicates.

### Putting the layers together

A solid 2-stage pipeline looks like this:

1. **Stage 1 - recall.** Hybrid retriever (Dense + BM25) returns 20-30 candidates.
2. **Optional - dedupe.** MMR thins near-duplicates, leaving 10-15.
3. **Stage 2 - precision.** Cross-encoder or LLM reranker scores those and keeps the top 3-5.
4. **LLM generation.** The final 3-5 chunks go into the prompt.

Visually, the layered pipeline funnels a large candidate pool down to a tight, deduplicated, high-precision context for the LLM.

```mermaid Full layered retrieval pipeline: recall, optional dedupe, precision rerank, then LLM generation
flowchart TD
    Q[User Query]
    HY["Stage 1 - Recall<br/>Hybrid Dense + BM25<br/>top 20-30"]
    MMR["Optional - Dedupe<br/>MMR (lambda 0.5)<br/>top 10-15"]
    RR["Stage 2 - Precision<br/>Cross-encoder or LLM reranker<br/>top 3-5"]
    LLM["LLM Generation<br/>final answer"]
    Q --> HY --> MMR --> RR --> LLM
```

The order matters. Reranking before deduplication wastes cross-encoder calls on duplicates. Deduplicating before retrieving enough candidates throws away signal. The sweet spot is to retrieve generously, dedupe lightly, then rerank aggressively.

### Common pitfalls

- **Reranking too few candidates.** If you send the reranker only 5 candidates and your true answer was at rank 15, the reranker cannot help. Retrieve 20+ before reranking.
- **Forgetting metadata.** Cross-encoders see only text. If you need to enforce permissions, freshness, or source authority, do that as a separate metadata filter *before* reranking - not inside the reranker.
- **Stacking too many models.** Bi-encoder + cross-encoder + LLM reranker can stack latency to 2+ seconds per query. Measure each stage's added latency against its added recall/precision and drop anything that does not pay rent.
- **Ignoring multilingual mismatch.** A reranker trained on English will under-score Korean chunks even when they are correct. Use multilingual rerankers (`rerank-multilingual-v3.0`, `bge-reranker-v2-m3`) for non-English corpora.

## Key Takeaways
- High-quality RAG retrieval is a **2-stage pipeline**: a fast bi-encoder (or hybrid retriever) recalls many candidates, and a slow but precise cross-encoder reranks them down to the few that go in the prompt.
- LangChain's `ContextualCompressionRetriever` wraps any reranker. `CohereRerank` is the fastest to set up; `bge-reranker-base/v2-m3` is a strong free local option.
- Cross-encoders are accurate but cannot take instructions. When you need domain rules, deduplication across candidates, or policy enforcement, an **LLM-as-reranker** (one call over 20 candidates) is often a better fit.
- **MMR** trades a little relevance for diversity in the final top-K, which is essential when your corpus has near-duplicates. `lambda_mult = 0.5` is a balanced default.
- Always retrieve *more* than you send to the LLM, and place permission/freshness filters *before* the reranker, not after.
