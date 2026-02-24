# LocalWriter

A LibreOffice extension that adds AI capabilities to Writer, Calc, and Draw — local-first, modular, and extensible.

## Features

- **Chat Sidebar** — multi-turn AI chat with tool-calling to read and edit your document
- **MCP Server** — expose tools to external AI clients (Cursor, Claude Desktop, scripts) via HTTP
- **Calc `=PROMPT()`** — call an LLM directly from a spreadsheet cell
- **Image Generation** — generate and edit images from chat (AI Horde, local backends)
- **Edit/Extend Selection** — hotkeys to rewrite or continue selected text (`Ctrl+E` / `Ctrl+Q`)
- **Tunnels** — expose MCP externally via ngrok, Cloudflare, bore, or Tailscale

## Backends

Any OpenAI-compatible API: Ollama, LM Studio, OpenRouter, OpenAI, text-generation-webui, etc.

## Install

1. Download the latest `.oxt` from the [releases page](https://github.com/quazardous/localwriter/releases)
2. In LibreOffice: **Tools > Extension Manager > Add**
3. Restart LibreOffice
4. Configure your endpoint in **LocalWriter > Settings**

## Architecture

LocalWriter uses a modular framework where each feature is a self-contained module with its own config, services, and tools. See [DEVEL.md](DEVEL.md) for the full developer guide.

### Modules

| Module | Description |
|--------|-------------|
| `core` | Document access, config, events, LLM, image, formatting |
| `writer` | Writer document editing tools (content, comments, styles, tables, tracking) |
| `writer.nav` | Heading tree, bookmarks, proximity navigation |
| `writer.index` | Full-text search with Snowball stemming |
| `calc` | Spreadsheet tools (cells, sheets, formulas, charts) |
| `draw` | Draw/Impress tools (shapes, pages/slides) |
| `common` | Cross-document tools (info, export) |
| `batch` | Multi-tool execution with variable chaining |
| `chatbot` | AI chat sidebar |
| `openai_compat` | OpenAI-compatible LLM backend |
| `ollama` | Ollama LLM backend |
| `horde` | AI Horde image generation |
| `http` | Shared HTTP server with optional SSL |
| `mcp` | MCP JSON-RPC protocol |
| `tunnel` | Tunnel manager (ngrok, cloudflare, bore, tailscale) |

## Development

```bash
./install.sh              # Set up dev environment
make cycle                # Build + install + restart LO + show log
make test                 # Run tests
```

See [DEVEL.md](DEVEL.md) for the complete developer guide.

## Credits

Built on the work of:
- [LibreCalc AI Assistant](https://extensions.libreoffice.org/en/extensions/show/99509) — Calc AI integration
- [LibreOffice MCP Extension](https://github.com/quazardous/mcp-libre) — MCP server and Writer tools

## License

MPL 2.0 — see `License.txt`.
