---
name: writeragent_integration
description: Connect Hermes to WriterAgent in LibreOffice so it can read/edit/save real documents (Writer, Calc, Draw).
---

# Connect Hermes Agent to WriterAgent

This skill connects Hermes to LibreOffice via the WriterAgent MCP server, giving Hermes the ability to natively read, edit, analyze, and save real documents (Writer documents, Calc spreadsheets, and Draw presentations).

## 1. Prerequisites & Setup

1. **Install LibreOffice** and the **WriterAgent** extension.
2. Open LibreOffice and ensure the **WriterAgent** sidebar is active.
3. Open **WriterAgent Settings** from the LibreOffice menu and check the box to **enable the MCP Server** (defaults to port 8765).
4. **Enable HTTP:** For security, local HTTP connections are not started automatically. **Every time you start LibreOffice**, you must manually enable the HTTP server from the WriterAgent menu so that Hermes can connect.

## 2. Hermes Profile (Recommended)

The cleanest way to use WriterAgent is to create a dedicated "Office" profile in Hermes. This bundles the WriterAgent MCP server without cluttering your default environment.

Run this command in your terminal:
```bash
hermes profile create office --with-mcp writeragent=http://localhost:8765
```

When you want to work on documents, just run:
```bash
hermes --profile office
```

## 3. Manual MCP Configuration

If you prefer modifying your configuration directly, add the following snippet to your Hermes `config.yaml` under `mcp_servers`:

```yaml
mcp_servers:
  writeragent:
    url: "http://localhost:8765"
```

## 4. Example Prompts & Workflows

Once connected, you can ask Hermes to perform powerful tasks directly within LibreOffice:

- **Calc Analysis:**
  > "Open my `Q1_budget.ods`, analyze the expenses by category, and create a new summary chart in a new sheet."

- **Writer Editing:**
  > "Take the current Writer document and rewrite the final three paragraphs into a professional executive summary."

- **Research & Data Entry:**
  > "Research the top 5 AI models for 2024 using your web search tools, then insert the results as a formatted table into my active Calc spreadsheet."

## 5. Best Practices & Troubleshooting

- **Approving Tool Calls (HITL):** It is highly recommended to leave Human-in-the-Loop (HITL) approval *on* for actions that modify your documents. This ensures Hermes asks for permission before writing changes or saving files.
- **Port Conflicts:** If `8765` is in use, change the port in the WriterAgent settings, then update your Hermes configuration to match.
- **Reloading the MCP:** If you restart LibreOffice or change WriterAgent settings, you may need to reload the MCP tools in Hermes. Use the `/reload-mcp` command.
- **Document Targeting:** Actions typically target the *active* foreground document in LibreOffice. 

## 6. Bonus: Agent Control Protocol (ACP) Mode

Want Hermes to be the full, autonomous backend for the LibreOffice UI itself? You can use WriterAgent as the primary chat interface for Hermes!

1. Open **WriterAgent Settings** from the LibreOffice menu.
2. Change your Model Selection to **Agent backends -> Hermes**.
3. Enable the **Agent Control Protocol** checkbox.

This allows Hermes to stream its thinking process and actions directly into the LibreOffice sidebar chat panel for the ultimate integrated experience!
