---
lecture_no: 1
title: "RAG Overview and Architecture: Why Attach Retrieval to an LLM?"
lecture_type: theory
sources:
  - https://www.youtube.com/watch?v=UabBYexBD4k
  - https://www.youtube.com/watch?v=zYGDpG-pTho
  - https://www.youtube.com/watch?v=ucH_N3jPQ0E
---

# RAG Overview and Architecture: Why Attach Retrieval to an LLM?

## Learning Objectives
- Explain the inherent limits of a pure LLM (hallucination, stale knowledge, missing domain expertise) and describe how RAG addresses each one.
- Identify the three building blocks of a RAG system - Retriever, Augmenter, and Generator - and trace the data flow from a user question to a grounded answer.
- Compare RAG against fine-tuning (and prompt engineering) and decide which approach fits a given problem.

## Body

### Why we need more than just an LLM

Large language models are remarkable, but they share one stubborn property: they are frozen in time. Once a model finishes training, it stops learning. It knows the world up to its training cutoff and nothing after that. It also knows nothing about *your* world - your company's internal wiki, your customer contracts, your proprietary codebase, the new policy that was published this morning.

That gap leads to the three failure modes that drive almost every practical AI project today:

1. **Hallucination.** When asked about something it does not actually know, a well-trained LLM rarely says "I'm not sure." It produces a smooth, confident-sounding answer that is wrong. A simple example: imagine asking a model in early 2024 for a low-interest government home loan in Korea. The model might recommend a product called Special Bogeumjari Loan because it was widely covered in 2023 articles. The problem is that this specific product was discontinued in January 2024 and replaced by a renamed program. The model is not lying on purpose - it simply has no way of knowing the data has changed.
2. **Stale knowledge.** Anything that happened after the cutoff is invisible. New regulations, the latest API release, last week's incident postmortem - none of it exists for the model.
3. **Missing domain context.** Even within its training period, a general-purpose model has never seen your internal documents, so it cannot reason about them.

A second symptom of these gaps is that the model cannot cite a source. When you ask "where did you get that?", a bare LLM has no honest answer. For an enterprise use case - legal, medical, financial, customer support - an unverifiable answer is often worse than no answer at all.

This is where **Retrieval-Augmented Generation (RAG)** comes in. The idea is deceptively simple: instead of expecting the model to *remember* everything, give it the option to *look things up* at answer time, then ask it to write the response while staying faithful to what it just read.

> RAG does not make the LLM smarter. It changes the question the LLM is being asked. Instead of "what do you remember about X?" it becomes "given these specific passages, what is the best answer to X?" That reframing is the whole point.

### The three building blocks of RAG

The name itself is the architecture. **Retrieval-Augmented Generation** decomposes into three stages, and almost every RAG system - simple or sophisticated - is a variation on these three.

**1. Retrieval.** When a user asks a question, the system does not send it straight to the LLM. It first searches an external knowledge store - typically a *vector database* - to find passages that are likely to contain the answer. Unlike a keyword search engine that matches exact words, retrieval in RAG is **semantic**: the question and every document chunk have been converted into numerical vectors (embeddings) that capture meaning. A query about "revenue growth last quarter" can match a document that talks about "fourth-quarter sales performance" even though the words do not overlap. We will study embeddings and vector databases in detail in lectures 2 and 3.

**2. Augmentation.** The top-ranked passages are not the final answer. They are *raw evidence*. The system stitches them into the prompt that goes to the LLM, usually under a template like: *"Use only the following sources to answer the user's question. If the sources do not contain the answer, say you do not know. Sources: \[passage 1] \[passage 2] ... Question: ..."* This is the step that takes a generic prompt and grounds it in real, retrieved facts.

**3. Generation.** Now the LLM does what it is best at: writing a fluent, well-structured answer. But because the relevant facts are now sitting inside its context window, it does not have to guess from memory. And because each passage carries metadata - document name, page number, URL - the system can hand back citations along with the answer.

A useful way to visualize the system is to picture two flows that meet at the LLM. There is an **offline indexing flow**: documents are loaded, split into chunks, embedded into vectors, and stored in the vector database. This happens once per document and is reused for every query. And there is an **online query flow**: a user question is embedded, matched against the index, the top chunks are pulled, the prompt is built, and the LLM produces the response. The architect's job is to make these two flows fit together cleanly, as shown in the diagram below.

```mermaid RAG architecture: offline indexing flow and online query flow meeting at the vector database
flowchart LR
    subgraph OFFLINE["Offline Indexing (once per document)"]
        direction TB
        D[Source Documents]
        L[Document Loader]
        C[Chunking]
        E1[Embedding Model]
        D --> L --> C --> E1
    end

    subgraph ONLINE["Online Query (every user request)"]
        direction TB
        Q[User Question]
        E2[Embedding Model]
        R[Retriever: top-k search]
        A[Augmenter: prompt builder]
        G[LLM Generator]
        ANS[Grounded Answer + Citations]
        Q --> E2 --> R
        R --> A --> G --> ANS
    end

    VDB[(Vector Database)]
    E1 -- write vectors --> VDB
    VDB -- nearest chunks --> R
```

### Walking through a concrete example

Let us follow a single question end to end so the pieces click into place.

A user types: *"Which security requirements were dropped between the v1 spec and the v1.2 release notes?"* In a bare-LLM setup, this question is hopeless - the model has never seen either of those internal documents. In a RAG setup, the system does this:

- The user's question is converted into a query vector.
- The vector database returns, say, the top eight chunks ranked by semantic similarity: a few from the requirements doc that mention "authentication" and "encryption", a few from the release notes that mention shipped features and known gaps.
- These chunks are inserted into the prompt along with an instruction such as *"Compare the listed requirements with the listed release notes. List requirements that appear in the spec but not in the release. Cite the source for each."*
- The LLM produces an answer grounded in those specific chunks, with citations.

Notice two things. First, the LLM never needed to be retrained - we just changed what it was looking at. Second, retrieval quality is the entire ball game. If the relevant chunk does not make it into the top-k results, the model will not see it, and the answer will be wrong or incomplete in a way that is hard to detect. The community has a name for this: **silent failure**. The right information exists in the database, but the retriever did not surface it, so the model produces a confident but incomplete answer with no warning that something was missed. Most of the engineering effort in a production RAG system goes into making retrieval not fail silently - through better chunking, better embedding models, reranking, hybrid keyword-plus-vector search, and so on. We will revisit these knobs in lectures 4 and 5.

### Why not just dump everything into the context window?

A fair objection at this point is: "Modern LLMs have million-token context windows. Why bother with vector databases at all? Just paste the entire knowledge base into the prompt."

This is called the **long-context approach**, and it really is attractive for some problems. If your data set is small and bounded - a single contract, one product manual, one research paper - feeding the whole thing in often produces better reasoning than RAG, because the model sees the entire picture and can spot cross-document relationships and missing pieces. RAG, by design, only shows the model a handful of isolated snippets.

But long context is not a universal replacement for RAG, for three concrete reasons:

- **Compute cost on every query.** With RAG, you pay the embedding cost once at indexing time. With long context, the model re-processes the same documents on every request. A 500-page manual is roughly 250,000 tokens; pushing that through the model for every user turn gets expensive fast. Prompt caching helps for static content, but not for data that changes often.
- **The needle-in-a-haystack problem.** Research consistently shows that as the context grows into the hundreds of thousands of tokens, the model's attention gets diluted. A single critical sentence buried in the middle of a 2,000-page dump is often ignored, or the model hallucinates details from surrounding text. RAG sidesteps this by handing the model only the five or ten passages most likely to matter - more signal, less noise.
- **Enterprise scale.** A million tokens sounds enormous until you compare it to a real corporate data lake measured in terabytes or petabytes. You cannot fit "everything" into any context window that exists today or will exist for the foreseeable future. Some form of retrieval layer is mandatory simply to filter the corpus down to a size the model can read.

A practical rule of thumb: **bounded data, deep reasoning → long context. Unbounded data, fact lookup → RAG.** Many real systems use both - long context for the working passage, RAG to choose which passage to load.

### RAG vs. fine-tuning vs. prompt engineering

RAG is one of three common ways to improve LLM output. The other two are fine-tuning and prompt engineering. They solve overlapping but different problems, and the most common beginner mistake is to reach for fine-tuning when RAG would be cheaper and better.

**Prompt engineering** is the lightest intervention. You change the wording of the prompt - adding examples, asking the model to "think step by step", clarifying constraints - without touching the model or adding any data. It is free, immediate, and surprisingly powerful. But it cannot add knowledge the model does not have. No amount of clever phrasing will teach the model what your internal API looks like.

**Fine-tuning** goes the other direction. You take an existing pre-trained model and continue training it on a curated dataset of input-output pairs that demonstrate the behavior you want. The model's weights are updated, so the new knowledge or style is *baked in*. This shines when you need deep domain expertise, a specific tone of voice, or structured output formats. Inference is fast because there is no retrieval step. But fine-tuning has real costs: you need thousands of high-quality examples, GPU budget for training, and a maintenance plan. Every time the knowledge changes, you have to retrain. And there is a real risk of **catastrophic forgetting**, where the model loses general capabilities while specializing.

**RAG** sits in between. It does not modify the model at all - it changes what the model can see. New documents can be added to the vector store in minutes instead of days. Updating yesterday's policy is as simple as re-embedding the changed file. The model can cite where each fact came from. The trade-off is operational complexity: a chunking strategy, an embedding model, a vector database, possibly a reranker, and the latency overhead of retrieving on every query.

The decision often boils down to the nature of the knowledge, and the following decision tree captures the most common reasoning path:

```mermaid Decision tree for choosing between RAG, fine-tuning, and prompt engineering
flowchart TD
    START[New LLM use case]
    Q1{Does the model<br/>already know enough<br/>to answer?}
    Q2{Does knowledge<br/>change often or<br/>need citations?}
    Q3{Need a specific<br/>style, tone, or<br/>output format?}
    PE[Prompt Engineering<br/>format, role, CoT]
    RAG[RAG<br/>private docs, news,<br/>policies, KB]
    FT[Fine-tuning<br/>stable expertise,<br/>style, schemas]
    COMBO[Combine: RAG for facts<br/>+ FT for style<br/>+ PE for format]

    START --> Q1
    Q1 -- Yes, just steer it --> Q3
    Q1 -- No, missing knowledge --> Q2
    Q2 -- Yes --> RAG
    Q2 -- No, stable expertise --> FT
    Q3 -- Yes --> FT
    Q3 -- No --> PE
    RAG --> COMBO
    FT --> COMBO
```

- **Knowledge that changes often or must be cited?** RAG. Examples: company knowledge bases, product documentation, news, regulations, customer records.
- **Stable, deep expertise or a specific behavior/style?** Fine-tuning. Examples: legal writing style, medical coding conventions, a customer-service tone, structured JSON output schemas.
- **The model already knows but needs to be steered?** Prompt engineering. Examples: format control, role framing, chain-of-thought reasoning.

In practice they compose well. A real legal-AI assistant might use RAG to pull recent case law, fine-tuning to enforce the firm's writing style, and prompt engineering to follow a specific document template. The question is rarely "which one?" but "in what proportion?"

### What RAG gives you, summarized

Step back from the mechanics for a moment. What does adding a retrieval step actually buy you, in plain terms?

- **Freshness without retraining.** New documents go into the vector store, not into the model weights. You can update knowledge daily without touching the LLM.
- **Domain knowledge from private data.** Your internal documents never need to leave your control to influence the answer.
- **Source attribution.** Every retrieved chunk carries metadata, so answers can be cited. This is often the single feature that makes RAG acceptable in regulated environments.
- **A controllable failure mode.** With a good instruction like "if the sources do not contain the answer, say you do not know", the system can be tuned to refuse gracefully instead of hallucinating - reducing the trust problem dramatically.
- **Lower long-term cost than fine-tuning** for knowledge that changes, because re-indexing is cheap compared with retraining.

What RAG does *not* do is make a weak model smart. The generation step is still the LLM. If the model cannot reason about the passages it was given, retrieving better passages will not save you. RAG is a knowledge layer, not an intelligence layer.

### Where this course goes from here

We have laid out the *why* and a high-level *how*. The rest of the course unpacks each component you will need to build a real RAG system:

- **Lecture 2 - Embeddings.** How text becomes vectors, and why cosine similarity gives us semantic search. We will compare OpenAI's text-embedding-3 family, BGE, SBERT, and Korean-friendly multilingual models.
- **Lecture 3 - Vector databases.** Chroma, FAISS, Pinecone, pgvector, Weaviate - what each is good for, and how ANN algorithms like HNSW and IVF trade speed for accuracy.
- **Lecture 4 - Document loading and chunking.** The unglamorous step that decides whether your retrieval works at all. Fixed, sentence, recursive, and semantic chunking; chunk size and overlap; metadata for citations.
- **Lecture 5 - Building the end-to-end MVP.** Putting it all together in LangChain: load, chunk, embed, store, retrieve, prompt, and respond.

By the end you will have built a working RAG pipeline you can adapt to your own documents. For now, take with you the mental model: an LLM is a brilliant but forgetful colleague, and RAG is the act of handing them the right pages of the right book just before they answer.

## Key Takeaways
- A pure LLM is frozen in time, prone to hallucination, and unaware of your private domain. RAG addresses all three by retrieving relevant passages at query time and asking the LLM to answer based on them.
- RAG has three stages: **Retrieval** (semantic search over a vector database), **Augmentation** (injecting retrieved passages into the prompt), and **Generation** (the LLM produces the final answer, ideally with citations).
- Retrieval quality is the whole game. If the right chunk is not in the top-k results, the model never sees it - a "silent failure" that is hard to detect from the output alone.
- Long context windows do not kill RAG. They win for small, bounded data with deep reasoning, but RAG is still required at enterprise scale, for cost control, and to avoid attention dilution.
- Choose RAG when knowledge changes often, must be cited, or comes from private data. Choose fine-tuning when you need deep, stable expertise or a specific behavior. Use prompt engineering to steer what the model already knows. The three are complementary, not exclusive.
