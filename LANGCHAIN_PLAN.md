# Langchain Integration Plan for LocalWriter

This document outlines a phased development plan to integrate `langchain-core` into LocalWriter, starting with basic conversation history and progressively adding more advanced memory and agentic features.

## Goal Description
Enhance LocalWriter's AI capabilities by replacing manual prompt construction with `langchain-core`'s robust memory and agent abstractions. This will allow the AI to "remember" past interactions, provide a seamless chat experience, and eventually perform complex multi-step document operations.

## Proposed Changes

### Phase 1: Foundation & Short-Term Memory
**Objective**: Introduce `langchain-core` and implement basic `ConversationBufferMemory` for the current session's chat.

- **Dependency Management**: 
  - Add `langchain-core` (and potentially `langchain` or specific provider packages) to the project requirements.
  - Ensure compatibility with LibreOffice's bundled Python environment.
- **Refactor [core/api.py](file:///home/keithcu/Desktop/Python/localwriter/core/api.py)**:
  - Implement a custom LangChain `BaseChatModel` wrapper (`LocalWriterLangChainModel`) around the existing `LlmClient`. This avoids the bloat of native provider packages (like `langchain-openai` which brings heavy dependencies like `httpx`) and retains our LibreOffice-optimized streaming loop, connection pooling, and error mapping.
  - Introduce `ConversationBufferMemory` to automatically manage the message history.
- **Update `chat_panel.py`**:
  - Instead of rebuilding the context string manually via `get_document_context_for_chat` with every message, inject the document state as a dynamic system prompt or context variable within a LangChain `Runnable` or `Chain`.

### Phase 2: Persistent Conversation History
**Objective**: Allow chats to persist across LibreOffice restarts.

- **Storage Mechanism**:
  - Implement a local storage solution (e.g., a simple JSON file per document URL under `~/.config/libreoffice/4/user/config/localwriter_chat_history/` or an SQLite database).
  - Use LangChain's `BaseChatMessageHistory` interface (e.g., `FileChatMessageHistory` or a custom implementation) to load and save messages.
- **Session Management**:
  - Tie conversation histories to document URLs (`doc.getURL()`).
  - Add a "Clear History" button to the chat sidebar.

### Phase 3: Token Management & Summarization Memory
**Objective**: Prevent the conversation history from exceeding the LLM's context window during long sessions.

- **Summarization**:
  - Replace `ConversationBufferMemory` with `ConversationSummaryBufferMemory`.
  - Configure a background LLM call to summarize older messages when the token count reaches a configured threshold (e.g., 80% of `chat_context_length`).
- **Config Updates**:
  - Add settings for `memory_strategy` (Buffer vs. Summary) and `max_memory_tokens`.

### Phase 4: Long-Term Document Memory (RAG)
**Objective**: Enable the AI to recall specific edits, user preferences, or distant sections of a very large document.

- **Vector Store — No NumPy, stdlib only**:
  - Do **not** depend on NumPy (not in system Python, large). Do **not** add Chroma, FAISS, or sqlite-vector. Implement or vendor a **pure-Python** vector store with **stdlib only**.
  - **What to use**: (1) **Cosine similarity**: Pure Python — dot product and L2 norm in a loop (`sum(a*b for a,b in zip(x,y))`, `math.sqrt(sum(x*x for x in vec))`). No NumPy. (2) **Store**: In-memory dict `id → {vector: list[float], text, metadata}`. (3) **Source**: Copy the *logic* from `langchain_core.vectorstores.in_memory` (add_documents, similarity_search, delete, etc.) and the base `VectorStore` interface into the LocalWriter tree (e.g. `core/vectorstore/`), then **replace** any NumPy usage with the pure-Python cosine above; drop `maximal_marginal_relevance` or reimplement with list operations if MMR is needed. Result: **zero** extra dependencies for the store.
  - **Optional — more efficient index**: For faster search when the working set is in memory (e.g. “recent 30 days” loaded into RAM), we can **vendor a small HNSW** and strip NumPy. For example **hnsw-lite** (pure Python HNSW, cosine/euclidean) lists NumPy as a dependency but the algorithm uses vectors as lists; we could copy the HNSW graph logic (insert, knn_search) and replace distance calculations with the same pure-Python cosine. That gives O(log n) approximate search instead of O(n) linear scan, at the cost of maintaining a vendored copy. Use this only for the in-memory index path (loading a subset into RAM).
- **Embeddings**:
  - Generate embeddings for paragraphs, sections, or previous AI edits (via existing API or a small local embedder). The vendored store accepts an embedding callable and stores vectors in memory.
- **Retrieval Augmented Generation**:
  - Build a retriever on top of the vendored store (same interface as LangChain’s `as_retriever()`: take a query, return top-k documents). Inject retrieved snippets into the chat prompt so the AI can answer about distant document parts.

#### Persistence for the Vector Store

**Persistence options (stdlib only, no NumPy):**

- **JSON only**: Simple and human-readable; good for small stores (hundreds of chunks). For large stores, file size and load/save time grow quickly. **Use for**: MVP or when document chunks are limited.
- **Binary vectors + JSON (recommended, stdlib only)**: **Vectors**: one file, e.g. header `[n, dim]` (2 × uint32), then `n` × `dim` × 4 bytes (float32 via `struct.pack('<f', x)`). **Text/metadata**: separate JSON keyed by id. Allows **streaming search**: read the vector file sequentially, unpack with `struct.unpack`, compute cosine in pure Python, maintain top-k heap — no need to load the full dataset into RAM. Optional **offset index** (id → byte offset) for "get by id".

**Index vs full load**: With an **in-memory** store we load the whole dataset (or subset) into RAM and build the index at load time. For a **year of conversations** we avoid that by **streaming search**: store vectors in a binary file; on query, read sequentially, compute similarity in pure Python, keep a running top-k heap — memory O(k), never load all data. Optional offset index (id → byte offset) for random access. Support **two modes**: (1) **Streaming** for large stores (binary file + JSON text/metadata); (2) **In-memory** for "recent only" (load subset into dict or vendored HNSW).

**Libraries/code to grab**: (1) **langchain_core.vectorstores.in_memory**: dump/load pattern; replace body with our binary+JSON and optional streaming. (2) **hnsw-lite**: copy HNSW graph logic, replace distance with pure-Python cosine for optional in-memory ANN without NumPy. (3) **langchain_community.vectorstores.sklearn**: serializer pattern `save(data)` / `load()` / `extension()`; implement `BinaryVectorSerializer` (struct + JSON).


### Phase 5: Agentic Workflows & Multi-Step Reasoning
**Objective**: Transition from a simple "Chat + Tools" model to autonomous problem solving.

- **Agent Orchestration**:
  - Use LangChain's `create_tool_calling_agent` and `AgentExecutor` to replace the custom tool execution loop in `chat_panel.py`.
  - Allow the agent to plan multi-step tasks (e.g., "Analyze this table, find errors, and format the erroneous cells red").
- **Human-in-the-Loop**:
  - Implement LangChain callbacks to pause execution and ask the user for confirmation before applying destructive changes to the document.

## Architecture Decision: Custom Wrapper vs. Provider Packages
We will proceed with writing a custom LangChain wrapper (`LocalWriterLangChainModel`) around our existing `LlmClient` rather than importing heavy provider packages like `langchain-openai` or `langchain-ollama`. LocalWriter runs in LibreOffice's constrained Python environment; keeping dependencies minimal (just `langchain-core`) is critical to avoid bloat and cross-platform installation issues, while allowing us to keep our custom UI streaming loops and connection management.

For Phase 4 (RAG), the **vector store is vendored and stdlib-only (no NumPy)**: we copy the logic from LangChain's in-memory store and use pure-Python cosine similarity; persistence is binary vectors (`struct`) + JSON. For large data (e.g. a year of conversations), support **streaming search** so we never load the full dataset into RAM. Optional: vendor HNSW (e.g. hnsw-lite with NumPy stripped) for an in-memory approximate index when loading a subset. No Chroma, FAISS, sqlite-vector, or NumPy.

## Verification Plan
### Automated & Manual Verification
- **Phase 1**: Verify that multi-turn conversations maintain context without manually re-reading the entire chat history in the prompt.
- **Phase 2**: Close a document, reopen it, and verify the chat sidebar restores previous context.
- **Phase 3**: Conduct a very long chat session and verify that older messages are summarized and the LLM does not return context limit errors.
