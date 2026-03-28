# Nelson-MCP Feature Backlog

This document tracks features and improvements identified in the `nelson-mcp` project for potential integration into `WriterAgent`.

| Feature | Date Identified | Source | Status | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Job Manager** | 2026-03-11 | base | [BACKLOG] | Generic background task system for long-running tools. |
| **Tool Broker** | 2026-03-11 | base | [BACKLOG] | Multi-tier tool discovery to keep prompts small for local LLMs. |
| **Sidebar Theme Fix** | 2026-03-11 | base | [DONE] | Dynamic background color matching for LibreOffice themes. |
| **Chat Input History** | 2026-03-11 | base | [BACKLOG] | Navigate previous queries with Up/Down arrows. |
| **Slide Placeholders** | 2026-03-11 | `bedd584` | [BACKLOG] | Read and write text into Impress slide placeholders. |
| **Hyperlink Tools** | 2026-03-11 | `bedd584` | [BACKLOG] | Add, edit, and remove hyperlinks in Writer/Impress. |
| **Writer Tables (Rich)** | 2026-03-11 | `6587c2f` | [BACKLOG] | Comprehensive table management (styles, headers, resizing). |
| **Calc Charts** | 2026-03-11 | `6587c2f` | [DONE] | Create and modify charts in Calc spreadsheets. |
| **Conditional Formatting** | 2026-03-11 | `6587c2f` | [DONE] | Apply color scales and data bars to Calc ranges. |
| **Master Slides** | 2026-03-11 | `6587c2f` | [BACKLOG] | Manage Impress master layouts and document-wide styles. |
| **Slide Transitions** | 2026-03-11 | `6f867a0` | [BACKLOG] | Set transition types and timings for Impress slides. |
| **Unified Image Tools** | 2026-03-11 | `b0aa04f` | [BACKLOG] | Cross-document image management and graphic query tools. |
| **Cell Range Write** | 2026-03-11 | `bedd584` | [BACKLOG] | Batch writing of cell data for improved Calc performance. |

---

## Notes
- **Status Definitions**:
    - `[BACKLOG]`: Identified but not yet planned for immediate integration.
    - `[IMPLEMENTING]`: Currently in the [implementation_plan.md](file:///home/keithcu/.gemini/antigravity/brain/eb776a8a-9643-4563-815b-c1d6854faf67/implementation_plan.md) for the current cycle.
    - `[DONE]`: Fully integrated and verified.
- **Next Steps**: Periodically run `git pull` in `nelson-mcp` and check `git log` to find new features.
