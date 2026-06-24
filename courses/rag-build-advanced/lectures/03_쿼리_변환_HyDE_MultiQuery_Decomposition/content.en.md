---
lecture_no: 3
title: "Query Transformation: HyDE, Multi-Query, and Decomposition"
lecture_type: practical
sources:
  - https://www.youtube.com/watch?v=JChPi0CRnDY
  - https://www.youtube.com/watch?v=sGvXO7CVwc0
  - https://www.youtube.com/watch?v=I_l91kdNE4w
---

# Query Transformation: HyDE, Multi-Query, and Decomposition

## Learning Objectives
- Explain why a user's raw question is often a poor input to a semantic retriever and how rewriting it improves recall.
- Implement HyDE (Hypothetical Document Embeddings) to bridge the gap between question-shaped queries and answer-shaped documents.
- Use LangChain's `MultiQueryRetriever` to fan a single question into several variants and merge the results.
- Decompose a complex question into sub-questions, solve each one, and synthesize the final answer.

## Body

### The problem: user questions and documents do not speak the same language

A user types: *"How do I cancel auto-renew on my plan?"* The relevant document says: *"To stop automatic billing, navigate to Account > Subscription and toggle off Renewal."* No tokens overlap. The phrasings live in different parts of embedding space. A dense retriever may return five unrelated billing FAQs before the right one.

This is the **query-document asymmetry problem**, and it shows up everywhere:

- Users write *questions*; documentation is written as *statements* and *instructions*.
- Users use casual vocabulary ("cancel auto-renew"); docs use formal terminology ("disable recurring payment").
- Users ask one big thing ("compare the v1 and v2 specs and tell me what changed in security"); docs answer one small thing at a time.

The fix is not to retrain the embedding model. It is to **transform the query** before retrieval so it looks more like the documents you are searching against. This lecture covers the three workhorse techniques: HyDE, Multi-Query, and Decomposition.

### Technique 1 - HyDE: hallucinate the answer, then search for it

HyDE (Hypothetical Document Embeddings) is the simplest of the three and often the most effective. The idea is counterintuitive: ask the LLM to *make up* an answer to the user's question, embed that hallucinated answer, and use it as the query.

Why does this work? Because the hallucinated answer is shaped like a document, not a question. Even if its facts are wrong, its *vocabulary*, *phrasing*, and *structure* will land much closer in embedding space to the real document that actually contains the answer.

The sequence of calls is short but it is worth seeing in order, because the embedded vector that hits the vector store is the *hypothetical answer*, never the user's literal question.

```mermaid HyDE call sequence: the LLM hallucinates an answer, that answer (not the question) becomes the query vector
sequenceDiagram
    participant U as User
    participant App as RAG App
    participant LLM as LLM (hallucinator)
    participant Emb as Embedding Model
    participant VS as Vector Store
    U->>App: "How do I cancel auto-renew?"
    App->>LLM: Draft a factual answer to this question
    LLM-->>App: Hypothetical answer paragraph
    App->>Emb: Embed the hypothetical answer
    Emb-->>App: Query vector
    App->>VS: similarity_search_by_vector(vec, k=5)
    VS-->>App: Top-K real document chunks
    App-->>U: Grounded answer (built from real chunks)
```

```python
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

hyde_prompt = ChatPromptTemplate.from_template(
    "Write a short, factual paragraph that directly answers this question. "
    "Do not say 'I don't know' - guess if you must. Question: {question}"
)
hyde_chain = hyde_prompt | llm | StrOutputParser()

question = "How do I cancel auto-renew on my plan?"
hypothetical = hyde_chain.invoke({"question": question})
# hypothetical ~ "To cancel auto-renewal, sign in to your account, go to
#                 the Subscription page, and turn off Automatic Renewal..."

# Now embed the hypothetical answer (not the question) and search:
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
hypo_vec = embeddings.embed_query(hypothetical)
docs = vectorstore.similarity_search_by_vector(hypo_vec, k=5)
```

In practice many teams retrieve with **both** the original question and the HyDE answer, then merge the results with RRF (Lecture 1).

> HyDE shines on short, vague questions where the user's phrasing differs from documentation style. It is less useful when the question is already detailed and technical - in that case the question already looks like a document.

A caveat: HyDE adds one LLM call per query. If your latency budget is tight, run HyDE only when the base retriever returns weak top scores, or use a small, fast model just for the hallucination step.

### Technique 2 - Multi-Query: ask the same thing several ways

The Multi-Query approach attacks a different problem. A single phrasing may sit in an unlucky neighborhood of embedding space and miss the right document by a small margin. Generating 3-5 alternative phrasings - each capturing a different angle - turns retrieval into a kind of shotgun: more queries fired in parallel, more chances of hitting the right chunk.

LangChain ships `MultiQueryRetriever` for exactly this:

```python
from langchain.retrievers.multi_query import MultiQueryRetriever

multi_query = MultiQueryRetriever.from_llm(
    retriever=vectorstore.as_retriever(search_kwargs={"k": 5}),
    llm=ChatOpenAI(model="gpt-4o-mini", temperature=0),
)

docs = multi_query.invoke("How do I cancel auto-renew on my plan?")
# Under the hood:
#   1. LLM generates ~3 variants:
#      - "How can I disable automatic renewal of my subscription?"
#      - "Steps to stop recurring billing on my account"
#      - "Where do I turn off auto-renew in account settings?"
#   2. Each variant is run through the retriever (k=5 each).
#   3. The unique union of returned documents is returned.
```

Two practical tips:

- **Watch the union size.** Three variants times `k=5` can yield 15 chunks. If you are sending them straight to the LLM, you need a reranker (Lecture 2) downstream.
- **Customize the variant prompt** when the default English-only generator produces poor variants for non-English queries. You can pass `prompt=` with a multilingual template.

A close relative is **RAG-Fusion**, which is Multi-Query followed by Reciprocal Rank Fusion across the result lists - same idea, slightly more rigorous merge.

### Technique 3 - Query Decomposition: split big questions into small ones

Some questions are not retrieval problems at all - they are *several* retrieval problems stitched together. Examples:

- *"Compare our 2023 and 2024 incident postmortem trends, and tell me which root causes regressed."*
- *"Which security requirements appear in the v1 spec but not in the v2 release notes?"*
- *"What did each of the three quarterly board updates say about hiring?"*

You cannot answer these by retrieving five chunks and hoping the LLM stitches them together. The retriever has no way to know it needs to fetch chunks from two distinct documents (2023 vs 2024, v1 vs v2, Q1/Q2/Q3 updates) in equal measure. Multi-Query helps a little but still treats the whole thing as one search.

**Decomposition** breaks the question into atomic sub-questions, retrieves and answers each independently, then synthesizes the final answer:

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser

# 1. Decompose
decompose_prompt = ChatPromptTemplate.from_template("""
Break the following complex question into 2-5 simpler sub-questions
that can each be answered independently from documents.
Return JSON: {{"sub_questions": [string, ...]}}

Question: {question}
""")
decompose = decompose_prompt | llm | JsonOutputParser()

# 2. For each sub-question, retrieve and answer
answer_prompt = ChatPromptTemplate.from_template(
    "Answer the question using ONLY the context. If unknown, say so.\n"
    "Context: {context}\nQuestion: {question}\nAnswer:"
)
answer_chain = answer_prompt | llm | StrOutputParser()

# 3. Synthesize
synth_prompt = ChatPromptTemplate.from_template("""
Combine the answers to the sub-questions into a single, coherent answer
to the original question. Preserve any citations.

Original question: {question}
Sub-question answers:
{partial_answers}
""")
synthesize = synth_prompt | llm | StrOutputParser()

def decomposed_rag(question, retriever):
    plan = decompose.invoke({"question": question})
    partials = []
    for sub in plan["sub_questions"]:
        ctx = "\n\n".join(d.page_content for d in retriever.invoke(sub))
        ans = answer_chain.invoke({"context": ctx, "question": sub})
        partials.append(f"Q: {sub}\nA: {ans}")
    return synthesize.invoke({
        "question": question,
        "partial_answers": "\n\n".join(partials),
    })
```

Decomposition is more expensive (one decomposition call + N retrievals + N answer calls + one synthesis call) but it is the only technique that reliably handles compositional questions.

### Choosing the right technique

The three techniques attack different failure modes, so the choice is driven by how the base retriever fails.

```mermaid Choosing a query transformation technique based on the failure mode
flowchart TD
    START[Base retriever returned the wrong chunks]
    Q1{Why did it miss?}
    Q2{"Question is question-shaped<br/>but docs are statement-shaped?"}
    Q3{"Single intent but phrasing<br/>sat in an unlucky spot?"}
    Q4{"Question is actually several<br/>questions in one?"}
    HYDE["HyDE - hallucinate the answer,<br/>embed that, search"]
    MQ["Multi-Query / RAG-Fusion -<br/>fan out 3-5 variants"]
    DECOMP["Decomposition - split into<br/>sub-questions, then synthesize"]

    START --> Q1
    Q1 --> Q2
    Q2 -- Yes --> HYDE
    Q2 -- No --> Q3
    Q3 -- Yes --> MQ
    Q3 -- No --> Q4
    Q4 -- Yes --> DECOMP
```

In practice you mix them. A robust production retriever often runs HyDE *and* Multi-Query in parallel, fuses the results with RRF, and only falls back to decomposition when the LLM detects a multi-part question. The cost is roughly 2-4x the embedding/LLM calls of plain RAG, which is usually a fair trade for the recall lift.

### Practical guardrails

- **Cache aggressively.** HyDE outputs and Multi-Query variants are deterministic (`temperature=0`) and depend only on the user's question. Cache them keyed on the question to avoid paying twice for repeat queries.
- **Watch for drift.** A hallucinated HyDE answer that is wildly off-topic can pull retrieval in a worse direction than the original query. Compare HyDE results against base-query results and keep the better top-K (or merge with RRF).
- **Limit decomposition depth.** Two to four sub-questions is the sweet spot. More than five usually means your decomposition prompt was too permissive, and you will pay for it in latency and cost.
- **Always pair with a reranker.** Query transformation increases the size of your candidate set. Without a downstream reranker (Lecture 2) the LLM sees too many marginally relevant chunks.

## Key Takeaways
- The biggest cause of bad retrieval is not the embedding model - it is the gap between how users phrase questions and how documents are written. Query transformation closes that gap.
- **HyDE** asks the LLM to write a hypothetical answer, then embeds that answer. The hallucinated text is shaped like a document and lands closer to the real one in embedding space.
- **Multi-Query** (and its sibling **RAG-Fusion**) generates 3-5 paraphrases of the same question and merges the result sets, raising recall on a single-intent question.
- **Decomposition** splits a compositional question into sub-questions, answers each independently, and synthesizes the final answer - the only reliable way to handle "compare X and Y" style queries.
- Combine techniques in production: HyDE + Multi-Query fused with RRF for most queries, decomposition only when the question is multi-part. Always cache, and always rerank downstream.
