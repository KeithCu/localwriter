# Hermes Agent Integration for WriterAgent

This directory provides the skill definitions and assistant tools needed to connect [Hermes Agent](https://github.com/NousResearch/hermes-agent) to the WriterAgent LibreOffice extension.

## 1. How to Install in Hermes

Since this skill is hosted directly inside the main `writeragent` repository, users have a few options to install it:

### Option A: Direct Installation via GitHub URI
Hermes supports installing skills from GitHub. Try running:
```bash
hermes skills install https://github.com/KeithCu/writeragent/tree/main/contrib/hermes-skill
```

### Option B: Local Setup using the Helper Script
If you've already downloaded or cloned the `writeragent` repository:
1. Open your terminal in this directory (`contrib/hermes-skill/`).
2. Run the helper script: `python3 setup.py`.
3. Follow the prompts to either create a dedicated Hermes `--profile office` or get the copy-paste configuration snippet.

### Option C: Manual Drop-in
You can simply copy `SKILL.md` directly into your Hermes `skills/` directory and rename it to something recognizable like `writeragent.md`.

## 2. Profile Management: Default vs. Dedicated

When setting up Hermes, you can either add the WriterAgent MCP server to your **Default Profile** or create a **Dedicated Profile** (e.g., `--profile office`). Here is a breakdown of the benefits:

### Benefits of a Dedicated Profile (`--profile office`)
- **Prevents Tool Clutter:** Hermes ships with dozens of built-in tools. Sending 50+ LibreOffice tools to the LLM on every turn eats up context window and causes confusion. Isolation keeps the AI sharper.
- **Memory Isolation:** A dedicated profile builds specific procedural memories and context about your documents and writing style over time, without polluting your default coding or chat agent.
- **Safety:** Limits the "blast radius." Your autonomous web-research agent won't accidentally have open access to modify your active spreadsheets unless you explicitly use the office profile.

### Benefits of Using the Default Profile
- **"God Mode" Agent:** You can execute complex, cross-domain workflows in one prompt (e.g., *"SSH into my server, summarize the database logs, and chart them in LibreOffice"*).
- **Convenience:** No need to append `--profile office` to your terminal commands; it's always ready.

## 3. How to Test the Setup

Once you've configured Hermes:

1. **Prepare LibreOffice:**
   - Open LibreOffice.
   - Open the WriterAgent Settings (via the menu).
   - Ensure the **MCP Server** is explicitly checked.
   - **Crucial:** Enable the local HTTP server. *(Remember: HTTP must be enabled every time LibreOffice restarts for security reasons).*
   
2. **Launch Hermes:**
   - Run `hermes` in your terminal (or `hermes --profile office` if you used the helper).
   
3. **Execute a Test Prompt:**
   Ask Hermes a question that forces it to interact with the document:
   > "Please review the currently active Writer document and tell me how many paragraphs it has."
   
4. **Verify:**
   You should see Hermes trigger the `get_document_info` tool from the `writeragent` MCP server and return a successful response!

## 4. Other Places to Publish the Skill

If you want to make this skill even more discoverable for users who might not be browsing the `writeragent` codebase, consider these distribution venues:

- **AgentSkills.io:** You can submit standard `SKILL.md` files to open ecosystem registries like [AgentSkills.io](https://agentskills.io). Doing this allows Hermes users to find it natively via commands like `hermes skills search writeragent`.
- **A Dedicated Mirror Repository:** If you find pointing users to a subfolder (`/tree/main/contrib/...`) is causing friction, you could spin up a lightweight, automated mirror repo (e.g., `KeithCu/hermes-writeragent-skill`) containing just this folder's contents.
- **Community Forums / Subreddits:** The `SKILL.md` format is just Markdown. You can easily publish this file as a **GitHub Gist** and share the raw link in tutorials across AI tool communities (e.g., on Reddit `/r/LocalLLaMA` or the Nous Research discord).
