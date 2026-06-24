---
lecture_no: 2
title: "Embedding Models and Vector Representations: Turning Meaning into Numbers"
lecture_type: theory
sources:
  - https://www.youtube.com/watch?v=wgfSDrqYMJ4
  - https://www.youtube.com/watch?v=vlcQV4j2kTo
  - https://www.youtube.com/watch?v=my5wFNQpFO0
---

# Embedding Models and Vector Representations: Turning Meaning into Numbers

## Learning Objectives
- Explain what an embedding is and how cosine similarity makes semantic search possible.
- Compare the characteristics, dimensions, and cost trade-offs of major embedding models such as OpenAI `text-embedding-3`, BGE, and SBERT.
- Decide which embedding model to use in a multilingual setting that includes Korean.

## Body

### Why embeddings sit at the heart of RAG

In the previous lecture we saw that Retrieval-Augmented Generation works by fetching the *right* passages from a knowledge base and feeding them into a language model. The obvious question is: how does the retriever know which passage is "right"? Old-school search would match keywords. If the user asks "How do I cancel my subscription?" and the document literally contains "cancel subscription", a keyword index finds it. But if the document says "terminate your membership" instead, classical keyword search misses it entirely — even though the meaning is the same.

This is the gap that embeddings close. An embedding model reads a piece of text and outputs a long list of numbers — a vector — designed so that texts with similar *meaning* end up close together in that numeric space, regardless of which exact words they used. RAG retrieval is built directly on top of this idea: you embed the user's question, embed every chunk of your documents, and return the chunks whose vectors live nearest to the question's vector. Choose the wrong embedding model and the rest of the pipeline — vector database, chunking, prompt — cannot rescue you. So this lecture is about the layer that decides whether your RAG system *understands* the query or just matches strings.

### From words to vectors: the core intuition

The simplest way to picture an embedding is to imagine plotting words on a graph. Suppose, for a moment, that an embedding has only two dimensions, so we can draw it on paper. A model trained on a large corpus of text might place the word `cat` near the word `dog`, place `house` far from both, and place `apple` near `orange` but well away from `airplane`. The position of each word encodes its meaning. Words used in similar contexts — "the cat purred", "the dog barked" — land near each other because the training process pushes them together; words used in unrelated contexts drift apart.

Two dimensions are not enough to capture real language. Production embedding models output vectors with hundreds or even thousands of dimensions. OpenAI's `text-embedding-3-small` produces 1,536-dimensional vectors by default, and `text-embedding-3-large` produces 3,072. You cannot visualize a 3,072-dimensional space, but the principle is the same: each dimension captures some latent property that the model learned during training (perhaps "animacy" or "formality" or "is-this-about-finance"), and the combination of all those numbers fixes the position of the text in a vast *semantic space*.

A useful mental model from one of today's source videos: an embedding for a cat might activate dimensions like "has fur" and "has legs"; an embedding for a house would activate "has a roof" but not "has fur"; an embedding for a dog would activate many of the same dimensions as the cat. Real models do not give us tidy labels like this — the dimensions are learned, not designed — but the analogy explains why similar things cluster.

> An embedding is deterministic. Feed the same text to the same model and you always get the same vector back. This is unlike a chat model such as GPT-4 or Gemini, where the same prompt can yield different answers. Embeddings behave more like a hash function: stable, repeatable, and meant for indexing.

### Three properties of embeddings you must remember

Three properties matter for everything that follows.

First, **embeddings are dense, not sparse.** Older techniques such as TF-IDF or bag-of-words produce vectors with one slot per vocabulary word, mostly filled with zeros. Modern neural embeddings produce vectors where every dimension carries a small real number. That density is what lets them encode subtle distinctions like the difference between "I went to the bank to deposit money" and "I sat on the bank of the river" — and it is also why we need specialized vector databases (next lecture) to search them efficiently.

Second, **embeddings are model-specific.** A vector produced by OpenAI's model has no meaningful relationship to a vector produced by Cohere's model or BGE's model, even if both have 1,024 dimensions. They live in different semantic spaces. This means you cannot mix and match: every chunk in your vector database must be embedded with the same model you use to embed the query at search time. If you ever switch embedding models, you must re-embed your entire corpus.

Third, **modern embeddings are contextual.** Early techniques such as word2vec and GloVe assigned one fixed vector per word, so `bank` always got the same vector whether the sentence was about finance or rivers. Transformer-based embedding models — which is what we use today — read the whole sentence (or paragraph, or document) and produce a vector that already reflects the surrounding context. That is why you embed *chunks*, not individual words, in a RAG pipeline.

### Cosine similarity: how we measure "close"

If embeddings live in a high-dimensional space, we need a way to ask "how close are these two vectors?" The standard answer in RAG is **cosine similarity**.

Cosine similarity ignores the *length* of each vector and only looks at the *angle* between them. Two vectors pointing in exactly the same direction have cosine similarity 1.0 (perfectly aligned). Two vectors at right angles have cosine similarity 0 (completely unrelated). Two vectors pointing in opposite directions have cosine similarity -1.0 (opposite meaning). For text embeddings in practice, almost all scores you see fall between 0 and 1; truly opposite meanings are rarer than you might expect, because almost any two pieces of natural-language text share *some* general "this is human language" direction.

The formula, for the curious, is the dot product of the two vectors divided by the product of their magnitudes:

`cos(A, B) = (A · B) / (||A|| × ||B||)`

But the *intuition* matters more than the formula. Cosine similarity asks: ignoring how long these arrows are, do they point in the same direction? "How do I cancel my subscription?" and "I want to terminate my membership" will point in nearly the same direction because both are aimed at the same semantic target. "How do I cancel my subscription?" and "What is the speed of light?" point in totally different directions.

Two practical notes. First, many embedding models — including OpenAI's `text-embedding-3` family — return vectors that are already **L2-normalized**, meaning their length is 1. When all vectors have length 1, cosine similarity is mathematically equivalent to a simple dot product, which is faster to compute. This is why some libraries report "dot product" and "cosine similarity" interchangeably; for normalized vectors they really are the same thing.

Second, cosine similarity is not the *only* distance metric. Euclidean distance and dot product are also common. For most RAG use cases with normalized embeddings, all three give very similar rankings, so cosine is the safe default. Just be consistent: use the same metric at indexing time and at query time, and use the metric your vector database is configured for.

### A typical RAG retrieval flow

Here is what happens when a user asks a question, in slow motion. The flow proceeds in four steps, as shown in the diagram below.

1. The user types a question such as "How do I reset my password?"
2. The application calls the embedding model with that question and receives a vector — say, 1,536 floating-point numbers.
3. The vector database compares that query vector to every chunk vector it stored at indexing time, computing cosine similarity for each, and returns the top-k most similar chunks (typically k = 3 to 10).
4. Those chunks are concatenated into a prompt — "Answer the question using only the context below: ..." — and sent to the LLM, which generates the final answer.

```mermaid From a user question to an LLM answer through embedding-based retrieval
flowchart LR
    U["User question<br/>How do I reset my password?"] --> E["Embedding model<br/>e.g. text-embedding-3-small"]
    E --> Q["Query vector<br/>1,536 dims"]
    Q --> V["Vector database<br/>cosine similarity vs. all chunk vectors"]
    C[("Indexed chunk vectors<br/>embedded with the SAME model")] --> V
    V --> K["Top-k chunks<br/>k = 3 to 10"]
    K --> P["Prompt assembly<br/>question + retrieved context"]
    P --> L["LLM"]
    L --> A["Final answer"]
```

Notice how much of the system's quality hinges on step 2 and step 3. If the embedding model captures meaning poorly, the most relevant chunk might rank tenth instead of first, and the LLM never sees it.

### A tour of major embedding models

There are dozens of embedding models on the market. We will focus on the three families you are most likely to encounter when you build your first RAG system: OpenAI's `text-embedding-3`, BGE from BAAI, and SBERT.

**OpenAI `text-embedding-3`** is the easy default. You call an API, send your text, and get back a vector. There are two variants: `text-embedding-3-small` produces 1,536-dimensional vectors at roughly $0.02 per million input tokens, and `text-embedding-3-large` produces 3,072-dimensional vectors at roughly $0.13 per million tokens. The `large` variant scores higher on the MTEB (Massive Text Embedding Benchmark) leaderboard than the `small` one, but `small` is already strong enough for most production RAG systems. Both support multiple languages reasonably well, including Korean.

A nice feature of `text-embedding-3` is **Matryoshka representation learning**, which lets you truncate the vector to a shorter length (say, 512 or 256 dimensions) and still keep most of the quality. Shorter vectors mean smaller storage and faster search — a useful lever when your corpus grows. The trade-off is obvious: you are paying per API call and your data leaves your network, which may be a deal-breaker for some enterprises.

**BGE (BAAI General Embedding)** is an open-source family from the Beijing Academy of Artificial Intelligence. Popular versions include `bge-small-en`, `bge-base-en`, `bge-large-en`, and the multilingual `bge-m3`. BGE models consistently rank near the top of the MTEB leaderboard, often beating commercial APIs on benchmark scores. Because they are open weights, you can download them from Hugging Face and run them on your own GPU (or even CPU for the smaller variants).

The `bge-m3` model is especially interesting for our purposes: it supports more than 100 languages — Korean included — and offers dense, sparse, and multi-vector retrieval in a single model. Dimensions for BGE models typically range from 384 (small) to 1,024 (large). The upside is no API cost and full data control; the downside is that you operate the inference yourself, which means a GPU server or careful CPU batching.

**SBERT (Sentence-BERT)** is less a single model and more a *technique*: take a pre-trained BERT (or similar transformer), fine-tune it with a siamese architecture so that whole sentences produce meaningful pooled embeddings, and publish the result. The `sentence-transformers` Python library hosts hundreds of these models, including `all-MiniLM-L6-v2` (only 384 dimensions, extremely fast), `paraphrase-multilingual-mpnet-base-v2` (multilingual, 768 dimensions), and many domain-specific variants. SBERT models are mature, well-documented, and small enough to run on a laptop. They tend to score below the newest BGE or OpenAI models on benchmarks, but for prototypes and modest-sized corpora they are an excellent starting point — especially `all-MiniLM-L6-v2`, which is probably the single most widely deployed embedding model in the world.

### Trade-offs: dimensions, cost, and quality

When you compare embedding models, four levers dominate the decision.

**Dimensions** affect both storage and search speed. A vector database storing 10 million chunks at 1,536 dimensions uses roughly 60 GB just for the vectors (10M × 1,536 × 4 bytes). The same corpus at 384 dimensions uses 15 GB. Search time scales similarly. So smaller is better — until you lose too much quality.

**Cost** comes in two flavors: API cost (pay per token, no hardware to manage) or infrastructure cost (free model weights, but you need GPUs to serve them at scale). For a small RAG system processing thousands of queries a day, OpenAI's API is usually cheaper end-to-end than running your own GPU. Past tens of millions of queries, self-hosting BGE or SBERT often wins.

**Quality** is best judged on benchmarks like MTEB, but be careful: MTEB averages across many tasks and many languages, and your specific use case may behave differently. The only reliable measure is to build a small evaluation set from your *own* documents and questions, embed both with each candidate model, and measure whether the right chunks rank high. Even a hand-built set of 30 to 50 query–answer pairs is enough to spot large quality gaps.

**Data privacy** can outrank everything else. If your corpus contains personal data, medical records, or trade secrets, sending it to a third-party API may be impossible. In that case self-hosted BGE or SBERT is not a preference but a requirement.

### Choosing an embedding model for Korean and other non-English data

If your RAG system needs to handle Korean — or any non-English language — you cannot just pick the top model on the English MTEB leaderboard. English-only models often perform poorly on Korean text because they were trained on corpora that were 95 percent English or more. There are three practical paths, summarized in the decision tree below.

```mermaid Decision tree for choosing an embedding model for Korean or multilingual data
flowchart TD
    Start["Need embeddings for<br/>Korean or multilingual text"] --> Privacy{"Can data leave<br/>your network?"}
    Privacy -->|"No - privacy or<br/>compliance constraint"| SelfHost{"Queries are<br/>100% Korean?"}
    Privacy -->|"Yes - API is OK"| Speed{"First MVP, want<br/>lowest friction?"}
    Speed -->|"Yes"| API["Path 1: Multilingual API<br/>text-embedding-3-small<br/>or Cohere embed-multilingual-v3"]
    Speed -->|"No - want to optimize"| Eval["Build a 30 to 50 pair<br/>evaluation set<br/>from your own data"]
    SelfHost -->|"Yes, Korean only"| KoSpec["Path 3: Korean-specialized<br/>ko-sroberta / ko-sbert<br/>best on pure-Korean tasks"]
    SelfHost -->|"No, mixes English<br/>technical terms"| OSS["Path 2: Open-source multilingual<br/>bge-m3 recommended<br/>or paraphrase-multilingual-mpnet"]
    Eval --> Compare["A/B test candidates<br/>API vs bge-m3 vs Korean-specialized"]
    Compare --> Pick["Pick the model with<br/>a clear, measurable win"]
```

**Path 1: Use a strong multilingual API.** OpenAI's `text-embedding-3-small` and `text-embedding-3-large` both handle Korean acceptably out of the box, as do Cohere's `embed-multilingual-v3.0` and Google's Vertex AI multilingual embeddings. This is the lowest-friction option: no model selection, no GPU, no fine-tuning. It is the right choice for most teams building a first RAG MVP.

**Path 2: Use an open-source multilingual model.** `bge-m3` is the current strongest open-source multilingual embedding model and performs very well on Korean. Older but still useful options include `paraphrase-multilingual-mpnet-base-v2` and `LaBSE`. Run these on your own infrastructure when data privacy or cost matter.

**Path 3: Use a Korean-specialized model.** Several Korean-focused embedding models have appeared on Hugging Face (search for `ko-sroberta`, `ko-sbert`, or similar). They often outperform general multilingual models on pure-Korean tasks because they were trained on Korean corpora and use a tokenizer that handles Korean morphology well. The trade-off: they may handle English-mixed queries poorly. If your documents are 100 percent Korean and your users will query in Korean only, a specialized model is a strong choice. If your queries mix Korean with English technical terms — which is common in IT and business contexts — a multilingual model is usually safer.

Two practical Korean-specific pitfalls deserve mention. First, watch the **tokenizer**. Some English-trained models tokenize Korean character by character, which inflates token counts (and API costs) and degrades quality. Models trained on Korean text use a tokenizer that recognizes Korean syllables and subwords. Second, watch the **chunk size in tokens, not characters**. Korean is information-dense per character; a 500-character Korean chunk often contains far more meaning than a 500-character English chunk. We will come back to this in the chunking lecture.

> Rule of thumb: if you are building your first Korean RAG and just want something that works, start with OpenAI `text-embedding-3-small`. Once you have a working baseline, A/B test `bge-m3` and a Korean-specialized model against your own evaluation set. Switch only if you see a clear, measurable improvement.

### Putting it together

An embedding model is the bridge between human language and the vector math that makes retrieval possible. It turns a sentence into a list of numbers so that "cancel my subscription" lands near "terminate my membership" but far from "speed of light". Cosine similarity gives us a way to measure that closeness as an angle between vectors. The model you pick determines the *geometry* of your semantic space — and therefore the ceiling of your RAG system's quality.

In the next lecture we will look at where those vectors actually live: vector databases, and the indexing algorithms (HNSW, IVF) that make searching millions of high-dimensional vectors in milliseconds possible.

## Key Takeaways
- An embedding maps text to a high-dimensional numeric vector so that semantically similar texts land close together; this is what lets RAG retrieve by meaning rather than by exact keywords.
- Cosine similarity measures the angle between two vectors (1.0 = same direction, 0 = unrelated) and is the standard "closeness" metric for RAG retrieval; for L2-normalized embeddings it is equivalent to the dot product.
- Embeddings are model-specific and deterministic. Use the same model for indexing and querying, and re-embed the whole corpus if you ever switch models.
- OpenAI `text-embedding-3` is the easy API default; BGE (especially `bge-m3`) is the strongest open-source family; SBERT models are mature, small, and ideal for prototypes — pick based on dimensions, cost, quality, and data-privacy needs.
- For Korean or other multilingual corpora, start with a strong multilingual model (`text-embedding-3-small` or `bge-m3`), and only move to a Korean-specialized model if you can show a measurable win on your own evaluation set.

## Sources
- IBM Technology, *What are Word Embeddings?* — https://www.youtube.com/watch?v=wgfSDrqYMJ4
- Google Cloud Tech, *What are text embeddings?* — https://www.youtube.com/watch?v=vlcQV4j2kTo
- Google for Developers, *Machine Learning Crash Course: Embeddings* — https://www.youtube.com/watch?v=my5wFNQpFO0
