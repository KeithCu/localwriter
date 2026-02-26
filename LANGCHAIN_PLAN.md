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

- **Embeddings & Vector Store**:
  - Integrate a lightweight, local-friendly vector store (e.g., `FAISS` with CPU or `Chroma`).
  - Generate embeddings for paragraphs, sections, or previous AI edits.
- **Retrieval Augmented Generation**:
  - Create a LangChain `Retriever` that fetches relevant document snippets based on the user's chat query.
  - Inject these retrieved snippets into the chat prompt dynamically, allowing the AI to answer questions about parts of the document it isn't currently looking at natively.

### Phase 5: Agentic Workflows & Multi-Step Reasoning
**Objective**: Transition from a simple "Chat + Tools" model to autonomous problem solving.

- **Agent Orchestration**:
  - Use LangChain's `create_tool_calling_agent` and `AgentExecutor` to replace the custom tool execution loop in `chat_panel.py`.
  - Allow the agent to plan multi-step tasks (e.g., "Analyze this table, find errors, and format the erroneous cells red").
- **Human-in-the-Loop**:
  - Implement LangChain callbacks to pause execution and ask the user for confirmation before applying destructive changes to the document.

## Architecture Decision: Custom Wrapper vs. Provider Packages
We will proceed with writing a custom LangChain wrapper (`LocalWriterLangChainModel`) around our existing `LlmClient` rather than importing heavy provider packages like `langchain-openai` or `langchain-ollama`. LocalWriter runs in LibreOffice's constrained Python environment; keeping dependencies minimal (just `langchain-core`) is critical to avoid bloat and cross-platform installation issues, while allowing us to keep our custom UI streaming loops and connection management.

## Verification Plan
### Automated & Manual Verification
- **Phase 1**: Verify that multi-turn conversations maintain context without manually re-reading the entire chat history in the prompt.
- **Phase 2**: Close a document, reopen it, and verify the chat sidebar restores previous context.
- **Phase 3**: Conduct a very long chat session and verify that older messages are summarized and the LLM does not return context limit errors.
