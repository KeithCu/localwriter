import dataclasses
import deal
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

@dataclasses.dataclass(frozen=True)
class ToolLoopState:
    round_num: int
    pending_tools: List[Dict[str, Any]]
    max_rounds: int
    status: str
    is_stopped: bool = False
    doc_type: str = ""
    async_tools: frozenset[str] = frozenset()

# --- Events ---
class ToolLoopEvent:
    pass

@dataclasses.dataclass(frozen=True)
class StreamDoneEvent(ToolLoopEvent):
    response: Dict[str, Any]

@dataclasses.dataclass(frozen=True)
class ToolResultEvent(ToolLoopEvent):
    call_id: str
    func_name: str
    func_args_str: str
    result: str
    mutates_document: bool = False

@dataclasses.dataclass(frozen=True)
class NextToolEvent(ToolLoopEvent):
    pass

@dataclasses.dataclass(frozen=True)
class FinalDoneEvent(ToolLoopEvent):
    content: str

@dataclasses.dataclass(frozen=True)
class StopRequestedEvent(ToolLoopEvent):
    pass

@dataclasses.dataclass(frozen=True)
class ErrorEvent(ToolLoopEvent):
    error: Any


# --- Effects ---
class ToolLoopEffect:
    pass

@dataclasses.dataclass(frozen=True)
class SpawnLLMWorkerEffect(ToolLoopEffect):
    round_num: int

@dataclasses.dataclass(frozen=True)
class SpawnFinalStreamEffect(ToolLoopEffect):
    pass

@dataclasses.dataclass(frozen=True)
class SpawnToolWorkerEffect(ToolLoopEffect):
    call_id: str
    func_name: str
    func_args_str: str
    func_args: Dict[str, Any]
    is_async: bool

@dataclasses.dataclass(frozen=True)
class UpdateUIEffect(ToolLoopEffect):
    text: str

@dataclasses.dataclass(frozen=True)
class UpdateStatusEffect(ToolLoopEffect):
    status: str

@dataclasses.dataclass(frozen=True)
class LogAgentEffect(ToolLoopEffect):
    location: str
    message: str
    data: Dict[str, Any]
    hypothesis_id: str

@dataclasses.dataclass(frozen=True)
class LogDebugEffect(ToolLoopEffect):
    message: str
    level: str = "debug"

@dataclasses.dataclass(frozen=True)
class AddAssistantMessageEffect(ToolLoopEffect):
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None

@dataclasses.dataclass(frozen=True)
class AddToolResultEffect(ToolLoopEffect):
    call_id: str
    result: str

@dataclasses.dataclass(frozen=True)
class UpdateDocumentContextEffect(ToolLoopEffect):
    pass

@dataclasses.dataclass(frozen=True)
class UpdateActivityStateEffect(ToolLoopEffect):
    action: str
    round_num: Optional[int] = None
    tool_name: Optional[str] = None

@dataclasses.dataclass(frozen=True)
class TriggerNextToolEffect(ToolLoopEffect):
    pass

@dataclasses.dataclass(frozen=True)
class ExitLoopEffect(ToolLoopEffect):
    pass


# --- State Machine Transition ---
@deal.ensure(lambda state, event, result: result[0].round_num <= max(state.max_rounds, state.round_num))
@deal.ensure(lambda state, event, result: not (isinstance(event, StopRequestedEvent) and any(isinstance(e, SpawnLLMWorkerEffect) for e in result[1])))
@deal.ensure(lambda state, event, result: result[0].round_num >= state.round_num)
def next_state(state: ToolLoopState, event: ToolLoopEvent) -> Tuple[ToolLoopState, List[ToolLoopEffect]]:
    """Pure transition function for the tool-calling loop."""
    effects: List[ToolLoopEffect] = []

    if isinstance(event, StopRequestedEvent):
        # Stop mid-stream or stop clicked
        effects.append(AddAssistantMessageEffect(content="No response."))
        effects.append(UpdateStatusEffect("Stopped"))
        effects.append(UpdateUIEffect("\n[Stopped by user]\n"))
        effects.append(ExitLoopEffect())
        return dataclasses.replace(state, is_stopped=True, status="Stopped"), effects

    elif isinstance(event, FinalDoneEvent):
        if event.content:
            effects.append(AddAssistantMessageEffect(content=event.content))
            effects.append(UpdateUIEffect("\n"))
        effects.append(UpdateStatusEffect("Ready"))
        effects.append(ExitLoopEffect())
        return dataclasses.replace(state, status="Ready"), effects

    elif isinstance(event, ErrorEvent):
        effects.append(ExitLoopEffect())
        # The caller handles rendering the actual error message
        return dataclasses.replace(state, status="Error"), effects

    elif isinstance(event, StreamDoneEvent):
        response = event.response
        tool_calls = response.get("tool_calls")
        if isinstance(tool_calls, list) and len(tool_calls) == 0:
            tool_calls = None
        content = response.get("content")
        finish_reason = response.get("finish_reason")

        if not isinstance(tool_calls, list):
            tool_calls = None

        effects.append(LogAgentEffect(
            location="chat_panel.py:tool_round",
            message="Tool loop round response",
            data={
                "round": state.round_num,
                "has_tool_calls": bool(tool_calls),
                "num_tool_calls": len(tool_calls) if tool_calls else 0,
            },
            hypothesis_id="A"
        ))

        if not tool_calls:
            effects.append(LogAgentEffect(
                location="chat_panel.py:exit_no_tools",
                message="Exiting loop: no tool_calls",
                data={"round": state.round_num},
                hypothesis_id="A"
            ))
            if content:
                effects.append(LogDebugEffect("Tool loop: Adding assistant message to session"))
                effects.append(AddAssistantMessageEffect(content=content))
                effects.append(UpdateUIEffect("\n"))
            elif finish_reason == "length":
                effects.append(UpdateUIEffect("\n[Response truncated -- the model ran out of tokens...]\n"))
            elif finish_reason == "content_filter":
                effects.append(UpdateUIEffect("\n[Content filter: response was truncated.]\n"))
            else:
                effects.append(UpdateUIEffect("\n[No text from model; any tool changes were still applied.]\n"))

            effects.append(UpdateStatusEffect("Ready"))
            effects.append(ExitLoopEffect())
            return dataclasses.replace(state, status="Ready"), effects

        else:
            effects.append(AddAssistantMessageEffect(content=content, tool_calls=tool_calls))
            if content:
                effects.append(UpdateUIEffect("\n"))

            new_pending_tools = list(state.pending_tools) + tool_calls
            effects.append(TriggerNextToolEffect())
            return dataclasses.replace(state, pending_tools=new_pending_tools), effects

    elif isinstance(event, NextToolEvent):
        # We need to explicitly check if stop was requested through an external flag passed to event,
        # but in our refactor we forgot to check `self.stop_requested` and update `is_stopped`
        # wait! `ToolCallingMixin` sets `self.stop_requested = True`, but it didn't send a `StopRequestedEvent`.
        # `is_stopped` inside state is False here. Let's fix that.
        if not state.pending_tools or state.is_stopped:
            if state.is_stopped:
                # If stopped, don't update status to 'Sending results...' and don't spawn a worker.
                # Just exit. Wait, the old code explicitly did:
                # if not self.stop_requested:
                #    self._set_status("Sending results to AI...")
                # ...
                # self._spawn_llm_worker(...)

                # So if stopped, it DOES spawn the worker or final stream?!
                # Looking at original tool_loop.py:
                # if not self.stop_requested:
                #     self._set_status("Sending results to AI...")
                # self._active_round_num += 1
                # if self._active_round_num >= self._active_max_tool_rounds:
                #     self._spawn_final_stream(...)
                # else:
                #     self._spawn_llm_worker(...)
                pass

            if not state.is_stopped:
                effects.append(UpdateStatusEffect("Sending results to AI..."))

            new_round_num = state.round_num + 1
            if new_round_num >= state.max_rounds:
                effects.append(LogAgentEffect(
                    location="chat_panel.py:exit_exhausted",
                    message="Exiting loop: exhausted max_tool_rounds",
                    data={"rounds": state.max_rounds},
                    hypothesis_id="A"
                ))
                effects.append(SpawnFinalStreamEffect())
                # When capping to max_rounds, it may be strictly less than current round if max_rounds was invalid
                # So we clamp to ensure we never go backwards in time
                capped_round_num = max(state.round_num, state.max_rounds)
                return dataclasses.replace(state, round_num=capped_round_num), effects
            else:
                effects.append(SpawnLLMWorkerEffect(round_num=new_round_num))
                return dataclasses.replace(state, round_num=new_round_num), effects

        else:
            tc = state.pending_tools[0]
            if not isinstance(tc, dict):
                tc = {}
            func_data = tc.get("function", {})
            if not isinstance(func_data, dict):
                func_data = {}

            func_name = func_data.get("name", "unknown")
            func_args_str = func_data.get("arguments", "{}")
            call_id = tc.get("id", "")

            effects.append(UpdateStatusEffect(f"Running: {func_name}"))
            effects.append(UpdateUIEffect(f"[Running tool: {func_name}...]\n"))
            effects.append(UpdateActivityStateEffect(action="tool_execute", round_num=state.round_num, tool_name=func_name))

            effects.append(LogAgentEffect(
                location="chat_panel.py:tool_execute",
                message="Executing tool",
                data={"tool": func_name, "round": state.round_num},
                hypothesis_id="C,D,E"
            ))
            effects.append(LogDebugEffect(f"Tool call: {func_name}({func_args_str})"))

            import json
            try:
                func_args = json.loads(func_args_str) if func_args_str else {}
                if not isinstance(func_args, dict):
                    func_args = {}
            except (json.JSONDecodeError, TypeError):
                func_args = {}

            is_async = func_name in state.async_tools
            effects.append(SpawnToolWorkerEffect(
                call_id=call_id,
                func_name=func_name,
                func_args_str=func_args_str,
                func_args=func_args,
                is_async=is_async
            ))

            # The pending tool is consumed
            return dataclasses.replace(state, pending_tools=state.pending_tools[1:]), effects

    elif isinstance(event, ToolResultEvent):
        # We received the result of a tool call
        import json
        try:
            result_data = json.loads(event.result) if event.result else {}
            if not isinstance(result_data, dict):
                result_data = {}
        except (json.JSONDecodeError, TypeError):
            result_data = {}

        note = result_data.get("message", result_data.get("status", "done"))
        effects.append(LogDebugEffect(f"Tool result: {event.result}"))
        effects.append(UpdateUIEffect(f"[{event.func_name}: {note}]\n"))

        if event.func_name == "apply_document_content" and isinstance(note, str) and note.strip().startswith("Replaced 0 occurrence"):
            params_display = event.func_args_str if len(event.func_args_str) <= 800 else event.func_args_str[:800] + "..."
            effects.append(UpdateUIEffect(f"[Debug: params {params_display}]\n"))

        effects.append(AddToolResultEffect(call_id=event.call_id, result=event.result))

        # Refresh document context if successful mutating tool
        is_success = result_data.get("success") is True or result_data.get("status") == "ok"
        if is_success and event.mutates_document:
            effects.append(UpdateDocumentContextEffect())

        effects.append(TriggerNextToolEffect())
        return state, effects

    return state, effects
