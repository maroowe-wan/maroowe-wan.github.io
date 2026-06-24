---
lecture_no: 1
title: "Hybrid Retrieval: Combining Dense Embeddings with Sparse BM25"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=r0Dciuq0knU
  - https://www.youtube.com/watch?v=lD3_VF5bmWg
  - https://www.youtube.com/watch?v=wp1ighuitNE
---

# Hybrid Retrieval: Combining Dense Embeddings with Sparse BM25

## Learning Objectives
- Compare the strengths and weaknesses of dense (embedding-based) and sparse (BM25/TF-IDF) retrieval and explain why production RAG almost always combines them.
- Build a hybrid retriever in LangChain using `EnsembleRetriever` (Dense + BM25) and tune the weights for your corpus.
- Implement Reciprocal Rank Fusion (RRF) to merge ranked lists from heterogeneous retrievers without relying on raw scores.

## Body

### Why a single retriever is never enough

In a basic RAG pipeline you do one thing: embed the user's question, find the nearest chunks in a vector index, and feed them to the LLM. That works for tidy demos. In real corpora it breaks in two specific ways, and the failure modes look opposite:

- **Dense retrieval misses exact terms.** Embeddings capture meaning, so a query for "COVID-19 treatment protocol for immunosuppressed patients" can drift to "general immunocompromised care" and surface documents that have nothing to do with COVID-19. The model captured the vibe of the sentence and ignored the keywords that actually mattered.
- **Sparse (keyword) retrieval misses synonyms.** A user searches for "tiny home"; the relevant document says "small house". BM25 sees no token overlap and ranks the right document near the bottom. It can match "puppy" to "puppy" but not to "young dog".

Both methods are correct most of the time and badly wrong in opposite cases. The fix is to run them in parallel and merge the results. This is **hybrid retrieval**, and it has become the default for serious RAG deployments precisely because the two error modes barely overlap - when one retriever fails, the other tends to catch the right document.

> Rule of thumb: dense retrieval gets you semantics, sparse retrieval gets you rare technical terms and identifiers. In legal, medical, and code-heavy domains the gap is large enough that pure dense search alone can drop accuracy by tens of percent.

### A short tour of BM25

BM25 ("Best Match 25") is a roughly 50-year-old keyword scoring function, and it is still the default sparse algorithm in Elasticsearch, Lucene, OpenSearch, and most vector databases that support hybrid search. The intuition is simple. A document scores higher when:

1. The query terms appear in it many times, but with diminishing returns - the tenth occurrence is worth far less than the second.
2. The query terms are **rare** across the corpus (inverse document frequency). A query token that appears in every document is essentially noise.
3. The document is not artificially long. BM25 applies a length normalization so a 50-page brochure that mentions "best" 100 times does not automatically beat a focused 2-page guide.

What BM25 cannot do is reason about meaning. Spelling errors, synonyms, paraphrases, and cross-lingual matches all defeat it. That is exactly where dense embeddings shine, which is why combining the two is so effective.

### Dense retrieval, in one paragraph

Dense retrieval converts the query and every chunk into high-dimensional vectors with an embedding model (OpenAI `text-embedding-3-small/large`, BGE, E5, multilingual SBERT, and so on) and ranks by cosine similarity. Approximate nearest-neighbor (ANN) indexes like HNSW make this fast at scale. The vectors capture meaning rather than tokens, so "young dog" finds "puppy" and "small house" finds "tiny home" - but as we saw, identifiers, product codes, and rare jargon often slip away.

### The hybrid recipe

A hybrid retriever runs both pipelines on every query and fuses the result lists:

1. Embed the query and pull the top-N chunks from the vector index.
2. Run the same query through BM25 and pull the top-N chunks.
3. Merge the two ranked lists into a single, deduplicated list, ordered by a combined score.

There are two common ways to merge - **weighted score fusion** and **Reciprocal Rank Fusion** - and they handle one specific problem in very different ways: the score scales of BM25 and cosine similarity are not comparable. A BM25 score might be 14.7, while a cosine similarity is 0.83. Just averaging them gives you nonsense. The two strategies handle this disagreement in opposite ways: weighted fusion *rescales* the scores, while RRF *throws the scores away* and uses only ranks.

### Building a hybrid retriever with LangChain `EnsembleRetriever`

LangChain's `EnsembleRetriever` is the easiest way to plug two retrievers together. It normalizes scores internally and applies the weights you supply:

```python
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.retrievers import EnsembleRetriever

# 1. Dense retriever (vector search)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma.from_documents(docs, embedding=embeddings,
                                    persist_directory="./chroma_db")
dense_retriever = vectorstore.as_retriever(search_kwargs={"k": 10})

# 2. Sparse retriever (BM25, in-memory)
bm25_retriever = BM25Retriever.from_documents(docs)
bm25_retriever.k = 10

# 3. Combine the two with weights
hybrid = EnsembleRetriever(
    retrievers=[bm25_retriever, dense_retriever],
    weights=[0.3, 0.7],      # 30% BM25, 70% dense
)

results = hybrid.invoke("COVID-19 treatment protocol for immunosuppressed patients")
for doc in results[:5]:
    print(doc.page_content[:120], "...")
```

Two practical notes:

- `BM25Retriever.from_documents` builds an in-memory index, which is fine up to maybe a hundred thousand chunks. For larger corpora wire it to Elasticsearch, OpenSearch, or a vector DB with built-in BM25 (Weaviate, Milvus, Qdrant, pgvector + VectorChord-BM25).
- The same `docs` list feeds both retrievers, so your chunks should be tokenizable by BM25 *and* embeddable. Strip noisy boilerplate before indexing - it hurts both methods equally.

### Tuning the weights

The `weights=[0.3, 0.7]` line is the single most important knob you have. It tells the retriever how much to trust BM25 versus the embeddings. There is no universal correct value - it depends on your corpus:

- **Code, legal clauses, product IDs, drug names, error codes** -> push BM25 up. Try `[0.5, 0.5]` or even `[0.6, 0.4]`. Exact tokens carry real signal.
- **Long natural-language documentation, customer-support tickets, FAQs** -> push dense up. Try `[0.2, 0.8]`. Users paraphrase questions; embeddings handle that.
- **Mixed corpora (which is most real systems)** -> start at `[0.3, 0.7]`, then evaluate.

How do you actually pick? You need an evaluation set - a few dozen real queries with the documents you expect each one to retrieve. Sweep the weights (`0.1` through `0.9`), compute recall at top-k on the eval set, and plot. We cover this evaluation loop in Lecture 4.

### Reciprocal Rank Fusion (RRF)

Weighted fusion still depends on calibrated scores. If your dense scores live in `[0.4, 0.95]` and BM25 scores live in `[2, 30]`, naive weighting privileges whichever side has a wider range. **Reciprocal Rank Fusion** sidesteps the problem entirely: it discards scores and uses only the *rank position* each retriever assigned to each document.

The RRF score for document `d` is:

```
RRF(d) = sum over retrievers r of  1 / (k + rank_r(d))
```

`k` is a small constant (typically `60`, from the original Cormack et al. paper) that softens the curve so the very top items do not dominate too aggressively. A document ranked 1st by both retrievers gets the highest score; a document ranked 1st by dense and not retrieved at all by BM25 still does well.

A concrete worked example makes the mechanic clearer. Suppose two retrievers return overlapping but differently ordered lists; RRF reads only the ranks and adds the reciprocals.

```mermaid Worked RRF example: two retrievers vote on three documents, scores depend only on rank positions
flowchart LR
    subgraph BM25R["BM25 ranking"]
        B1["rank 1: Doc A"]
        B2["rank 2: Doc B"]
        B3["rank 3: Doc C"]
    end
    subgraph DENSER["Dense ranking"]
        D1["rank 1: Doc B"]
        D2["rank 2: Doc A"]
        D3["rank 3: Doc D"]
    end
    subgraph FUSED["RRF merged (k=60)"]
        FA["Doc A: 1/61 + 1/62 = 0.0325"]
        FB["Doc B: 1/62 + 1/61 = 0.0325"]
        FC["Doc C: 1/63 = 0.0159"]
        FD["Doc D: 1/63 = 0.0159"]
    end
    BM25R --> FUSED
    DENSER --> FUSED
```

Here is a minimal RRF implementation that works with any two LangChain retrievers:

```python
from collections import defaultdict

def reciprocal_rank_fusion(result_lists, k: int = 60):
    """result_lists: list of ranked lists of Documents. Returns merged list."""
    scores = defaultdict(float)
    doc_lookup = {}
    for results in result_lists:
        for rank, doc in enumerate(results, start=1):
            key = doc.page_content        # or a stable doc_id from metadata
            scores[key] += 1.0 / (k + rank)
            doc_lookup[key] = doc
    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [doc_lookup[key] for key, _ in fused]

dense_hits = dense_retriever.invoke(query)
sparse_hits = bm25_retriever.invoke(query)
merged = reciprocal_rank_fusion([dense_hits, sparse_hits])[:5]
```

The flow when a query arrives is straightforward: the same query fans out to both retrievers in parallel, each returns its own top-N list, and the fuser merges them into the final top-K.

```mermaid Hybrid retrieval flow: query fans out to BM25 and dense retrievers in parallel, then RRF or weighted fusion merges the ranked lists
flowchart LR
    Q[User Query]
    BM25[BM25 / Sparse Retriever]
    DENSE[Dense / Vector Retriever]
    FUSE[Fusion: weighted score or RRF]
    TOPK[Top-K Merged Chunks]
    Q --> BM25
    Q --> DENSE
    BM25 -- ranked list --> FUSE
    DENSE -- ranked list --> FUSE
    FUSE --> TOPK
```

**Weighted fusion vs RRF - which to use?**

- Use **weighted fusion** (`EnsembleRetriever`) when you have time to tune weights against an eval set and you want fine control over the dense/sparse balance.
- Use **RRF** when you are combining more than two retrievers, when score scales are wildly different, or when you do not yet have evaluation data to calibrate weights. It is the safer default in early-stage systems.

Most production setups end up running RRF over three to five retrievers - dense, BM25, sometimes a multi-vector index, sometimes a graph or metadata filter.

### Common pitfalls

- **Forgetting to filter by metadata first.** Hybrid retrieval should run *after* permission filters and tenant scopes, not before. Otherwise you leak documents.
- **Tokenization mismatch.** BM25 is sensitive to tokenization. If your dense index keeps `"GPT-4o"` as one token but BM25 splits it into `gpt`, `4o`, your sparse recall on model names will collapse. Use a tokenizer that respects hyphens, identifiers, and code symbols.
- **Mixing per-document and per-chunk indexes.** Both retrievers must agree on the unit of retrieval. If BM25 returns documents and dense returns chunks, fusion produces nonsense.
- **Reranking comes later.** Hybrid retrieval gives you a strong top-N candidate set. A reranker still needs to choose the top 3-5 for the final prompt. That is Lecture 2.

## Key Takeaways
- Dense retrieval captures meaning but misses rare tokens; BM25 captures rare tokens but misses meaning. Hybrid retrieval consistently beats either one alone because their failure modes barely overlap.
- LangChain's `EnsembleRetriever` makes Dense + BM25 hybrid retrieval a one-line setup. The `weights` parameter is the main tuning knob - lean toward BM25 for jargon-heavy corpora, toward dense for natural-language docs.
- Raw scores from BM25 and cosine similarity are not directly comparable. Either rescale them (weighted fusion) or discard them and use ranks (Reciprocal Rank Fusion).
- RRF with `k=60` is a strong, score-free default for merging two or more retrievers, and is the safer choice when you do not yet have an evaluation set.
- Hybrid retrieval is a recall mechanism, not a precision mechanism. You still need a reranker (Lecture 2) to pick the final top-K chunks the LLM actually sees.
