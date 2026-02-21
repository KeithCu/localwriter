# LocalWriter

A LibreOffice extension (Python + UNO) that adds generative AI editing to Writer, Calc, and Draw.

Consider donating to support development: [ko-fi.com/johnbalis](https://ko-fi.com/johnbalis)



## Features

LocalWriter provides powerful AI-driven capabilities integrated directly into your LibreOffice suite:

### 1. Local-First & Flexible (The Major Differentiator)
Unlike proprietary office suites that lock you into a single cloud provider and **send all your data to their servers**, LocalWriter is **local-first**. You can run fast, private models locally (via Ollama, LM Studio, or local servers) ensuring your documents never leave your machine. If you choose to use cloud APIs, you can switch between them in less than 2 seconds, maintaining full control over where your data goes.

### 2. Chat with Document (Writer, Calc, and Draw)
The main way to interact with your document using natural language.

*   **Sidebar Panel**: A dedicated deck in the right sidebar for multi-turn chat. It supports tool-calling to read and edit the document directly.
*   **Menu Item**: A fallback option that opens an input dialog and appends responses to the document.
*   **Performance**: Features built-in connection management with persistent HTTPS connections for fast response times.
*   **Undo Integration**: AI edits are grouped so you can revert an entire AI turn with a single `Ctrl+Z`.

### 3. Expanded Writer Tool Set
The AI chat sidebar now exposes a rich set of Writer operations beyond basic content editing:

*   **Styles**: `list_styles` and `get_style_info` — the AI can discover the exact paragraph and character style names in your document (including localized names) before applying them, ensuring it uses styles that actually exist.
*   **Comments**: `list_comments`, `add_comment`, `delete_comment` — the AI can read, add, and remove inline comments, enabling full review workflows where the AI annotates a document for human review.
*   **Track Changes**: `set_track_changes`, `get_tracked_changes`, `accept_all_changes`, `reject_all_changes` — the AI can make edits in tracked-changes mode so every modification is visible and reversible before you accept. Ask it to "rewrite this section with track changes on" and review the diff yourself.
*   **Tables**: `list_tables`, `read_table`, `write_table_cell` — the AI can enumerate named tables, read their full contents as a 2D grid, and write individual cells using standard Excel-style references (A1, B2, etc.), enabling targeted table edits without rewriting the whole document.

Opus 4.6 one-shotted this Arch Linux resume:
![Opus 4.6 Resume](Opus46Resume.png)

![Chat Sidebar with Dashboard](Sonnet46Spreadsheet.png)

### 3. Edit & Extend Selection (Writer)
**Hotkey:** `Ctrl+Q`
The model continues the selected text. Ideal for drafting emails, stories, or generating lists.

### 3. Edit Selection
**Hotkey:** `Ctrl+E`
Prompt the model to rewrite your selection according to specific instructions (e.g., "make this more formal", "translate to Spanish").

### 4. Format preservation (Writer)
When you ask the AI to fix a typo or change a name, the result can keep the formatting you already had: highlights, bold, colors, font size, and so on. The AI does not need to—and typically cannot—describe LibreOffice’s full formatting model. In practice, the AI often sends back markup (e.g. bold like **Michael**) even for simple corrections. We auto-detect: when it sends **plain text**, we preserve your existing formatting; when it sends Markdown or HTML, we use the import path. So when the model does send plain text, you get full preservation without the AI needing to know LibreOffice’s capabilities.

*Example:* The document has “Micheal” (one-letter typo) with yellow highlight and bold. You ask the AI to correct the spelling. If the AI returns plain “Michael,” we preserve the yellow highlight and bold. If it returns “**Michael**,” we treat that as formatted content (import path) and the highlight can be lost—a model quirk. The feature is especially valuable when the AI sends plain text.

Replacing text in Writer normally inherits formatting from the insertion point, so per-character formatting on the original text would be lost. We use two strategies: for **plain-text replacements** (name corrections, typo fixes) we replace in a way that preserves existing per-character formatting; for **structured content** (Markdown/HTML) we use the import path to inject formatted content with native styles. The choice is automatic—we detect whether the new content is plain text or contains markup—so the AI does not have to choose. This applies to Chat with Document tool edits in Writer.

### 5. Image generation and AI Horde integration
Image generation and editing are integrated and complete. You can generate images from the chat (via tools or “Use Image model”) and edit selected images (Img2Img). Two backends are supported: **AI Horde** (Stable Diffusion, SDXL, etc., with its own API key and queue) and **same endpoint as chat** (uses your configured endpoint and a separate image model). Settings are in **LocalWriter > Settings** under the **Image Settings** tab, with shared options (size, insert behavior, prompt translation) and a clearly separated **AI Horde only** section.

### 6. Calc `=PROMPT()` function
A cell formula to call the model directly from within your spreadsheet:
`=PROMPT(message, [system_prompt], [model], [max_tokens])`

## LocalWriter Architecture

LocalWriter isn't just a wrapper; it's built for performance and deep integration with LibreOffice:

*   **Responsive Streaming Architecture**: Unlike simple extensions that freeze when waiting for an AI response, LocalWriter now uses a sophisticated background thread and queue system. This keeps the LibreOffice UI alive and responsive while text streams in or as tools are executed.
*   **Interleaved Streaming & Multi-Step Tools**: The engine natively supports interleaved reasoning tokens, content streaming, and complex multi-turn tool calling. This allows for sophisticated AI behavior that handles multi-step tasks while keeping the user informed in real-time.
*   **High-Throughput Performance (200+ tps)**: Optimized for speed, the system can easily handle 200 tokens per second with zero UI stutter.
*   **Native Formatting Persistence**: For structured content (Markdown/HTML), LocalWriter injects AI-generated text using the import path, preserving native LibreOffice styles. For plain-text replacements (e.g. typo fixes), we preserve your existing per-character formatting so highlights, bold, and colors stay intact.
*   **Isolated Task Contexts**: Each open document in LibreOffice gets its own independent AI sidebar. The AI stays aware of the specific document it's attached to, preventing "cross-talk" when working on multiple projects.
*   **HiDPI Compatible UI**: All dialogs and sidebar panels are defined via XDL and optimized for modern high-resolution displays using device-independent units.

## Credits & Collaboration

LocalWriter stands on the shoulders of giants. We'd like to give massive credit to:

**[LibreCalc AI Assistant](https://extensions.libreoffice.org/en/extensions/show/99509)**

Their pioneering work on AI support for LibreOffice provided the foundation and inspiration for our enhanced Calc integration. We've built upon their excellent tools to create more ambitious and performance-oriented spreadsheet features. We encourage everyone to check out their extension and join the effort to improve free, local AI for everyone!

**[LibreOffice MCP Extension](https://github.com/quazardous/mcp-libre)**

Their work on an embedded MCP (Model Context Protocol) server for LibreOffice was an invaluable reference for expanding LocalWriter's Writer tool set. From their project we adapted production-quality UNO implementations for style inspection, comment management, track-changes control, and table editing — resulting in 12 new Writer tools now available to LocalWriter's embedded AI. Their extension also introduced us to useful patterns for server lifecycle management, dynamic menu state, and health-check probing that inform our roadmap for exposing LocalWriter's tools to external AI clients. We're grateful for the high-quality open work and encourage everyone to check it out.

## Performance & Batch Optimizations

To handle complex spreadsheet tasks, LocalWriter is optimized for high-throughput "batch" operations:

*   **Batch Tool-Calling**: Instead of making one-by-one changes, tools like `write_formula_range` and `set_cell_style` operate on entire ranges in a single call.
*   **High-Volume Insertion**: The `import_csv_from_string` tool allows the AI to generate and inject large datasets instantly. This is orders of magnitude faster than inserting data cell-by-cell; we found that providing these batch tools encourages the AI to perform far more ambitious spreadsheet automation and data analysis.
*   **Optimized Ranges**: Formatting and number formats are applied at the range level, minimizing UNO calls and ensuring the UI remains fluid even during heavy document analysis.

## Roadmap

We are moving towards a native "AI co-pilot" experience:

*   **Richer Document Awareness**: Adding deep metadata awareness (paragraph styles, word counts, formula dependencies) so the AI understands document structure as well as text.
*   **Safer Workflows**: Implementing "Propose-First" paths where the AI generates a visual preview (diff) for user approval before touching the document.
*   **Predictive "Ghost Text"**: Real-time suggestions as you type, driven by local trigram models trained on your current document context.
*   **Reliability Foundations**: Strengthening timeout management, clear error recovery, and universal rollback-friendly behavior for professional stability.
*   **Suite-Wide Completeness**: Finalizing deep integration for **LibreOffice Draw and Impress**, ensuring every application in the suite is AI-powered.
*   **Offline First**: Continued focus on performance with the fastest local models (Ollama, etc.) to ensure privacy and speed without cloud dependencies.
*   **MCP Server (External AI Access)**: A planned optional HTTP server that exposes LocalWriter's full tool set to external AI clients such as Claude Desktop and Cursor. When enabled, any MCP-compatible client would be able to read and edit your open LibreOffice documents using the same tools the built-in sidebar AI uses — with no second extension to install. In fact we plan to talk to the extension owner if he'd like to join our team. See [MCP_PROTOCOL.md](MCP_PROTOCOL.md) for the full design and implementation plan.

## Setup

### 1. Installation
1.  Download the latest `.oxt` file from the [releases page](https://github.com/balisujohn/localwriter/releases).
2.  In LibreOffice, go to `Tools > Extension Manager`.
3.  Click `Add` and select the downloaded file.
4.  Restart LibreOffice.

### 2. Backend Setup
LocalWriter requires an OpenAI-compatible backend. Recommended options:
*   **Ollama**: [ollama.com](https://ollama.com/) (easiest for local usage)
*   **text-generation-webui**: [github.com/oobabooga/text-generation-webui](https://github.com/oobabooga/text-generation-webui)
*   **OpenRouter / OpenAI**: Cloud-based providers.

## Settings

Configure your endpoint, model, and behavior in **LocalWriter > Settings**.

*   **Endpoint URL**: e.g., `http://localhost:11434` for Ollama.
*   **Additional Instructions**: A shared system prompt for all features with history support.
*   **API Key**: Required for cloud providers.
*   **Connection Keep-Alive**: Automatically enabled to reduce latency.

For detailed configuration examples, see [CONFIG_EXAMPLES.md](CONFIG_EXAMPLES.md).

## Contributing

### Local Development
```bash
# Clone the repository
git clone https://github.com/balisujohn/localwriter.git
cd localwriter

# Build the extension package
bash build.sh

# Register the extension
unopkg add localwriter.oxt
```

## License
LocalWriter is primarily released under the **MPL 2.0** license. See `License.txt` for details.
Copyright (c) 2024 John Balis

*Architecture diagram created by Sonnet 4.6.*

![Architecture](Sonnet46ArchDiagram.jpg)
