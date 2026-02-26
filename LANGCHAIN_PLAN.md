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

- **Vector Store — Simplest Approach (no extra dependency)**:
  - Do **not** add Chroma, FAISS, or sqlite-vector as dependencies. Instead, **copy a small set of files from LangChain** into the LocalWriter tree (e.g. under `core/vectorstore/` or similar) so the vector store is self-contained.
  - **What to copy**: From `langchain_core.vectorstores`: (1) `in_memory.py` — the `InMemoryVectorStore` implementation (dict + cosine search, add_documents, similarity_search, etc.); (2) the base `VectorStore` class and any minimal abstractions it depends on; (3) from `langchain_core.vectorstores.utils`: `_cosine_similarity` and `maximal_marginal_relevance`, using **only the NumPy path** (drop the optional `simsimd` dependency so we stay pure Python + NumPy). Optionally trim async methods if we only need sync. Dependencies of this vendored code: **stdlib + NumPy** (and whatever we already use for `Document` / embeddings). No `langchain-core` import required for the vector store itself.
  - This gives a minimal, cross-platform vector store with zero new package installs; we implement persistence ourselves (see below).
- **Embeddings**:
  - Generate embeddings for paragraphs, sections, or previous AI edits (via existing API or a small local embedder). The vendored store accepts an embedding callable and stores vectors in memory.
- **Retrieval Augmented Generation**:
  - Build a retriever on top of the vendored store (same interface as LangChain’s `as_retriever()`: take a query, return top-k documents). Inject retrieved snippets into the chat prompt so the AI can answer about distant document parts.

#### Persistence for the Vector Store

We need to save and load the in-memory store (ids, vectors, text, metadata) to disk. LangChain’s `InMemoryVectorStore` already has `dump(path)` / `load(path)` that use `dumpd(self.store)` and JSON; that works but is **inefficient for larger data** because vectors are serialized as lists of floats in JSON (large file size, slow encode/decode).

**Persistence options (by efficiency and complexity):**

- **JSON only** (what LangChain does now): Simple and human-readable; good for small stores (hundreds of chunks). For large stores, file size and load/save time grow quickly. **Use for**: MVP or when document chunks are limited.
- **NumPy binary (`.npy` / `.npz`)**: Store the vector matrix and optionally text/metadata in a second file. Use `np.save()` / `np.load()` for a single array or `np.savez_compressed()` for multiple arrays (e.g. `vectors`, `ids`, `lengths` for variable-length text). **Pros**: Fast, compact, no extra dependency. **Cons**: Need a consistent layout (e.g. fixed-order ids + one big matrix + one JSON for text/metadata). **Use for**: Efficient persistence with only stdlib + NumPy.
- **Hybrid (recommended for “larger amounts of data”)**: Keep **vectors** in a single `.npz` (e.g. `np.savez_compressed(path_npz, vectors=matrix, ids=id_array)`) and **text + metadata** in a small JSON keyed by id. On load: read the npz, read the JSON, reconstruct the store dict. This keeps the bulk of the data (vectors) in binary and the rest editable/debuggable. **Efficient** for 10k–100k+ chunks without new dependencies.
- **Msgpack**: More compact than JSON, binary, fast. Would require a small dependency (`msgpack`) or vendoring a minimal encoder. Use if we want smaller files than JSON without going to NumPy.
- **Parquet** (e.g. via PyArrow): Columnar format, good compression and column-wise reads. **LangChain** uses this in `langchain_community.vectorstores.sklearn` via a `ParquetSerializer` (save/load interface). We could **grab the serializer pattern** (abstract `save(data)` / `load()` / `extension()`) and implement our own backend (e.g. NpzSerializer) so that adding Parquet later is a second serializer. Parquet adds a dependency (`pyarrow`); only add if we need very large scale or interoperability.

**Libraries/code to reuse or mimic:**

- **`langchain_core.vectorstores.in_memory`**: Already implements `dump(path)` and `load(path)` with JSON + `dumpd`/`load`. After vendoring, we can **replace** the body of `dump`/`load` with a hybrid or npz implementation so the public API stays the same.
- **`langchain_core.vectorstores.utils`**: `_cosine_similarity` and `maximal_marginal_relevance` — copy the NumPy-only branch (no simsimd).
- **`langchain_community.vectorstores.sklearn`** (JsonSerializer, ParquetSerializer, BaseSerializer): The **pattern** of a serializer with `save(data)`, `load()`, `extension()` is useful; we can implement a local `NpzSerializer` or hybrid serializer that writes vectors to `.npz` and text/metadata to JSON, without depending on langchain_community.
- **SimpleVectorStore** (e.g. patw/SimpleVectorStore): Uses a single JSON file for the whole store (vector dim, items with vector, text, metadata). Good reference for a minimal JSON schema; we can adopt a similar layout for the “small JSON” side of a hybrid format.

### Phase 5: Agentic Workflows & Multi-Step Reasoning
**Objective**: Transition from a simple "Chat + Tools" model to autonomous problem solving.

- **Agent Orchestration**:
  - Use LangChain's `create_tool_calling_agent` and `AgentExecutor` to replace the custom tool execution loop in `chat_panel.py`.
  - Allow the agent to plan multi-step tasks (e.g., "Analyze this table, find errors, and format the erroneous cells red").
- **Human-in-the-Loop**:
  - Implement LangChain callbacks to pause execution and ask the user for confirmation before applying destructive changes to the document.

## Architecture Decision: Custom Wrapper vs. Provider Packages
We will proceed with writing a custom LangChain wrapper (`LocalWriterLangChainModel`) around our existing `LlmClient` rather than importing heavy provider packages like `langchain-openai` or `langchain-ollama`. LocalWriter runs in LibreOffice's constrained Python environment; keeping dependencies minimal (just `langchain-core`) is critical to avoid bloat and cross-platform installation issues, while allowing us to keep our custom UI streaming loops and connection management.

For Phase 4 (RAG), the **vector store is vendored**: we copy a few files from LangChain (in-memory store + cosine/MMR utils, NumPy-only) into the project and add our own persistence (e.g. hybrid JSON + `.npz`). No Chroma, FAISS, or sqlite-vector dependency; the only requirement for the store is stdlib + NumPy.

## Verification Plan
### Automated & Manual Verification
- **Phase 1**: Verify that multi-turn conversations maintain context without manually re-reading the entire chat history in the prompt.
- **Phase 2**: Close a document, reopen it, and verify the chat sidebar restores previous context.
- **Phase 3**: Conduct a very long chat session and verify that older messages are summarized and the LLM does not return context limit errors.
