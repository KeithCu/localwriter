---
name: Hermes Planning Integration
overview: Copy the hermes-agent TodoStore and planning skill patterns, adapt them as a WriterAgent ToolBase tool and system prompt guidance, so the built-in chat LLM can decompose complex document tasks into tracked steps.
todos:
  - id: copy-todostore
    content: "Create plugin/modules/chatbot/todo_store.py: copy TodoStore class and todo_tool() from hermes-agent, add GPL header and attribution"
    status: pending
  - id: create-todotool
    content: "Create plugin/modules/chatbot/tools/todo.py: ToolBase subclass wrapping TodoStore with hermes schema"
    status: pending
  - id: wire-discovery
    content: Ensure chatbot tools/ directory is discovered by tool registry (add __init__.py, verify manifest)
    status: pending
  - id: pass-store
    content: Modify tool_loop.py execute_fn to attach TodoStore instance to ToolContext services
    status: pending
  - id: system-prompt
    content: Add planning guidance section to DEFAULT_CHAT_SYSTEM_PROMPT in constants.py
    status: pending
  - id: clear-reset
    content: Reset TodoStore on Clear button press in panel
    status: pending
isProject: false
---

# Hermes Planning Integration into WriterAgent

## Context: What Hermes Actually Has

The hermes-agent planning system is **not** a code-level plan executor. It is a set of cooperating pieces:

- `**TodoStore`** (`~/.hermes/hermes-agent/tools/todo_tool.py`): An in-memory task list with items `{id, content, status}` (pending/in_progress/completed/cancelled). The LLM calls a `todo` tool to create, update, and read the list. This is the only piece that is actual reusable code.
- **Plan skill** (`skills/software-development/plan/SKILL.md`): A prompt that tells the LLM to plan only (no execution), writing a markdown plan to disk.
- **Writing-plans skill** (`skills/software-development/writing-plans/SKILL.md`): A prompt teaching the LLM how to write granular, actionable implementation plans.
- **Subagent-driven-development skill** (`skills/software-development/subagent-driven-development/SKILL.md`): A prompt teaching the LLM to execute plans by dispatching `delegate_task` sub-agents per task step with two-stage review. This relies on Hermes's `AIAgent` child-spawning which WriterAgent does not have.
- `**delegate_tool`** (`tools/delegate_tool.py`): Spawns child `AIAgent` instances. This is Hermes-specific and not directly portable -- WriterAgent's built-in LLM path runs a single tool-calling loop, not nested agent sessions.

## What to Port

The valuable, directly portable pieces are:

1. `**TodoStore` class** -- the in-memory task list with merge/replace modes
2. `**todo` tool schema** -- the OpenAI function-calling schema with behavioral guidance baked in
3. **Planning prompt fragments** -- adapted from the plan/writing-plans skills, injected into the chat system prompt so the LLM knows to use the todo tool for complex requests

The `delegate_tool` and `subagent-driven-development` skill are **not** a good fit for the initial integration. WriterAgent's built-in chat path is a single LLM + tool loop; adding nested agent sessions would be a much larger effort. Instead, the single LLM will plan, track progress via todos, and execute document tools itself.

## Implementation

### 1. Create `plugin/modules/chatbot/todo_store.py`

Copy the `TodoStore` class from `~/.hermes/hermes-agent/tools/todo_tool.py` (lines 25-144). This is ~120 lines of clean, dependency-free Python. Changes:

- Remove the hermes `tools.registry` import at the bottom
- Keep `TodoStore`, `VALID_STATUSES`, and `todo_tool()` function as-is
- Add GPL license header
- Credit hermes-agent in the file docstring

### 2. Create `plugin/modules/chatbot/tools/todo.py` (ToolBase subclass)

Create a new `ToolBase` subclass that wraps `TodoStore`:

- `name = "todo"`, `doc_types = None` (available for all doc types)
- `is_mutation = False` (does not modify the document)
- `tier = "core"` (always included in tool schemas)
- `parameters` from hermes `TODO_SCHEMA["parameters"]`
- `description` from hermes `TODO_SCHEMA["description"]`
- `execute(ctx, **kwargs)` calls `todo_tool(todos=..., merge=..., store=...)` where the store comes from the session

Key design decision: **Where does the `TodoStore` instance live?**

The store must be per-chat-session so todos persist across multi-turn conversation. The natural place is on the `ChatSession` object (in [plugin/modules/chatbot/session.py](plugin/modules/chatbot/session.py) or equivalent). The `ToolContext` already carries `ctx` and `caller`; we can attach the store to the session and retrieve it via `ctx` or a lightweight service lookup.

Simplest approach: Store the `TodoStore` instance on the `SendButtonListener` (which already holds the `session`), and pass it to the tool via the `ToolContext.services` dict or a dedicated attribute. When the panel is cleared or a new document is opened, the store resets.

### 3. Wire the todo tool into tool discovery

The tool registry auto-discovers `ToolBase` subclasses from `plugin/modules/chatbot/tools/`. Currently there is no `tools/` subdirectory under `chatbot/` -- create it with an `__init__.py`. The manifest/bootstrap in [plugin/main.py](plugin/main.py) already discovers tools from each module's `tools/` subdirectory, so adding the directory should be sufficient.

Verify in `plugin/_manifest.py` that `chatbot` is in the module list. If tool discovery only runs for modules listed there, no extra wiring is needed beyond adding the file.

### 4. Pass the TodoStore into tool execution

In [plugin/modules/chatbot/tool_loop.py](plugin/modules/chatbot/tool_loop.py), the `execute_fn` closure creates a `ToolContext`. Add the `TodoStore` to it:

```python
# In _do_send_chat_with_tools, before the execute_fn definition:
if not hasattr(self, '_todo_store'):
    from plugin.modules.chatbot.todo_store import TodoStore
    self._todo_store = TodoStore()

# In execute_fn, add to ToolContext or pass via services:
tctx = ToolContext(
    ...
    services={**_get_tools()._services, 'todo_store': self._todo_store},
    ...
)
```

Then in the `TodoTool.execute()`, retrieve it:

```python
def execute(self, ctx, **kwargs):
    store = ctx.services.get('todo_store')
    ...
```

### 5. Add planning guidance to the system prompt

In [plugin/framework/constants.py](plugin/framework/constants.py), append a section to `DEFAULT_CHAT_SYSTEM_PROMPT` (and the Calc variant) with condensed planning guidance adapted from the hermes skills:

```
## Task Planning

For complex requests (3+ steps), use the `todo` tool to plan before acting:
1. Break the task into small, specific steps
2. Create the todo list (each item: id, content, status)
3. Mark each item in_progress before starting, completed when done
4. Only one item in_progress at a time

For simple requests, skip planning and act directly.
```

This is a minimal addition (~5-8 lines) that teaches the LLM when and how to use the todo tool, mirroring the behavioral guidance hermes bakes into the tool schema description.

### 6. Clear todos on Clear button

In the panel's Clear button handler, reset `self._todo_store = TodoStore()` so a fresh conversation starts with an empty task list.

## Files Changed

- **New**: `plugin/modules/chatbot/todo_store.py` -- TodoStore + todo_tool function (copied from hermes)
- **New**: `plugin/modules/chatbot/tools/__init__.py` -- empty
- **New**: `plugin/modules/chatbot/tools/todo.py` -- TodoTool ToolBase subclass
- **Modified**: `plugin/modules/chatbot/tool_loop.py` -- attach TodoStore to ToolContext services
- **Modified**: `plugin/framework/constants.py` -- add planning guidance to system prompt
- **Modified**: `plugin/modules/chatbot/panel.py` or `panel_factory.py` -- reset TodoStore on Clear

## What This Does NOT Include (Future Work)

- **Subagent delegation**: Hermes's `delegate_task` spawns child `AIAgent` instances. WriterAgent would need a way to run nested LLM sessions, which is a larger architectural change. The existing external agent backends (Hermes/Claude via ACP) already provide this if the user wants it.
- **Plan files on disk**: Hermes saves plans as `.hermes/plans/*.md`. This could be added later as a `write_plan` tool, but the in-memory todo list is more natural for document editing sessions.
- **Todo persistence across sessions**: The hermes TodoStore is in-memory only. Persisting todos to the SQLite history DB could be a follow-up.

