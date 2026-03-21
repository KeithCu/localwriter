"""Pure state machine for chat sidebar send handlers."""

from dataclasses import dataclass, field
from typing import List, Tuple, Any, Dict, Optional

try:
    import deal
except ImportError:
    # Dummy decorators for production where deal is not installed
    class _DummyDeal:
        @staticmethod
        def pre(func): return lambda f: f
        @staticmethod
        def post(func): return lambda f: f
        @staticmethod
        def ensure(func): return lambda f: f
    deal = _DummyDeal()

# 1. Define State (frozen dataclass)

@dataclass(frozen=True)
class SendHandlerState:
    handler_type: str # 'audio', 'image', 'agent', 'web'
    status: str       # 'ready', 'starting', 'running', 'done', 'error', 'stopped'
    query_text: str = ""
    model: Any = None
    doc_type_str: str = ""
    round_num: int = 0
    pending_tools: tuple = ()
    max_rounds: int = 10
    recent_effects: tuple = ()


# 2. Define Events

@dataclass(frozen=True)
class StartEvent:
    query_text: str
    model: Any
    doc_type_str: str
    wav_path: Optional[str] = None
    stt_model: Optional[str] = None

@dataclass(frozen=True)
class StreamChunkEvent:
    chunk_text: str
    is_thinking: bool = False

@dataclass(frozen=True)
class StreamDoneEvent:
    response: Any = None

@dataclass(frozen=True)
class ErrorEvent:
    error: Exception

@dataclass(frozen=True)
class StopRequestedEvent:
    pass

@dataclass(frozen=True)
class ToolResultEvent:
    tool_id: str
    result: dict

SendHandlerEvent = StartEvent | StreamChunkEvent | StreamDoneEvent | ErrorEvent | StopRequestedEvent | ToolResultEvent

# 3. Define Effects (Commands)

@dataclass(frozen=True)
class SpawnAudioWorkerEffect:
    wav_path: str
    stt_model: str
    model: Any
    query_text: str

@dataclass(frozen=True)
class SpawnDirectImageEffect:
    query_text: str
    model: Any

@dataclass(frozen=True)
class SpawnAgentWorkerEffect:
    query_text: str
    model: Any
    doc_type_str: str

@dataclass(frozen=True)
class SpawnWebWorkerEffect:
    query_text: str
    model: Any

@dataclass(frozen=True)
class UpdateUIEffect:
    text: str
    is_thinking: bool = False
    replace: bool = False

@dataclass(frozen=True)
class SetStatusEffect:
    status_text: str

@dataclass(frozen=True)
class ProceedToChatEffect:
    combined_text: str
    model: Any
    doc_type_str: str

@dataclass(frozen=True)
class CompleteJobEffect:
    terminal_status: str

SendHandlerEffect = SpawnAudioWorkerEffect | SpawnDirectImageEffect | SpawnAgentWorkerEffect | SpawnWebWorkerEffect | UpdateUIEffect | SetStatusEffect | ProceedToChatEffect | CompleteJobEffect

# 5. Effect Interpreter Interface/Placeholder
# The EffectInterpreter class executes the side effects returned by next_state.
# It will be instantiated and called by SendHandlersMixin in send_handlers.py.

class EffectInterpreter:
    def __init__(self, handler_mixin):
        self.handler = handler_mixin
        self.current_state = None

    def interpret(self, effect: SendHandlerEffect):
        if isinstance(effect, UpdateUIEffect):
            self.handler._append_response(effect.text)
        elif isinstance(effect, SetStatusEffect):
            self.handler._set_status(effect.status_text)
        elif isinstance(effect, CompleteJobEffect):
            self.handler._terminal_status = effect.terminal_status
            if effect.terminal_status not in ("Error", "Stopped"):
                self.handler._terminal_status = "Ready"
                self.handler._set_status("Ready")
        elif isinstance(effect, SpawnAudioWorkerEffect):
            self.handler._execute_audio_effect(effect.wav_path, effect.stt_model, effect.model, effect.query_text, self.current_state, self)
        elif isinstance(effect, SpawnDirectImageEffect):
            self.handler._execute_direct_image_effect(effect.query_text, effect.model, self.current_state, self)
        elif isinstance(effect, SpawnAgentWorkerEffect):
            self.handler._execute_agent_backend_effect(effect.query_text, effect.model, effect.doc_type_str, self.current_state, self)
        elif isinstance(effect, SpawnWebWorkerEffect):
            self.handler._execute_web_research_effect(effect.query_text, effect.model, self.current_state, self)
        elif isinstance(effect, ProceedToChatEffect):
            self.handler._do_send_chat_with_tools(effect.combined_text, effect.model, effect.doc_type_str)


# 4. Pure Transition Function

@deal.pre(lambda state, event: state.round_num <= state.max_rounds)
@deal.post(lambda result: result[0].round_num <= result[0].max_rounds)
@deal.ensure(lambda state, event, result:
    not (isinstance(event, StopRequestedEvent) and
         any(isinstance(e, (SpawnAudioWorkerEffect, SpawnDirectImageEffect, SpawnAgentWorkerEffect, SpawnWebWorkerEffect)) for e in result[1])))
def next_state(
    state: SendHandlerState,
    event: SendHandlerEvent
) -> Tuple[SendHandlerState, List[SendHandlerEffect]]:
    """Pure state transition - NO SIDE EFFECTS"""

    effects: List[SendHandlerEffect] = []

    if isinstance(event, StopRequestedEvent):
        # Regardless of current handler, stopping terminates the work
        effects.append(SetStatusEffect("Stopped"))
        if state.handler_type == "agent":
            effects.append(UpdateUIEffect("\n[Stopped by user]\n"))
        effects.append(CompleteJobEffect("Stopped"))
        new_state = SendHandlerState(
            handler_type=state.handler_type,
            status="stopped",
            query_text=state.query_text,
            model=state.model,
            doc_type_str=state.doc_type_str,
            round_num=state.round_num,
            pending_tools=state.pending_tools,
            max_rounds=state.max_rounds,
            recent_effects=tuple(effects)
        )
        return new_state, effects

    if isinstance(event, ErrorEvent):
        from plugin.modules.http.errors import format_error_message
        err_msg = format_error_message(event.error)

        effects.append(SetStatusEffect("Error"))
        if state.handler_type == 'audio':
            effects.append(UpdateUIEffect(f"\n[Transcription error: {err_msg}]\n"))
        elif state.handler_type == 'web':
            effects.append(UpdateUIEffect(f"\n[Research Chat error: {err_msg}]\n"))
        else:
            effects.append(UpdateUIEffect(f"\n[Error: {err_msg}]\n"))

        effects.append(CompleteJobEffect("Error"))
        new_state = SendHandlerState(
            handler_type=state.handler_type,
            status="error",
            query_text=state.query_text,
            model=state.model,
            doc_type_str=state.doc_type_str,
            round_num=state.round_num,
            pending_tools=state.pending_tools,
            max_rounds=state.max_rounds,
            recent_effects=tuple(effects)
        )
        return new_state, effects

    if isinstance(event, StreamChunkEvent):
        effects.append(UpdateUIEffect(event.chunk_text, event.is_thinking))
        new_state = SendHandlerState(
            handler_type=state.handler_type,
            status=state.status,
            query_text=state.query_text,
            model=state.model,
            doc_type_str=state.doc_type_str,
            round_num=state.round_num,
            pending_tools=state.pending_tools,
            max_rounds=state.max_rounds,
            recent_effects=tuple(effects)
        )
        return new_state, effects

    if isinstance(event, StreamDoneEvent):
        if state.status in ("error", "stopped"):
            return state, effects

        if state.handler_type == 'audio':
            transcript_text = event.response if event.response else ""
            combined_text = state.query_text
            if transcript_text:
                combined_text = (
                    (combined_text + "\n" + transcript_text).strip()
                    if combined_text
                    else transcript_text
                )

            if combined_text:
                effects.append(ProceedToChatEffect(combined_text, state.model, state.doc_type_str))
            else:
                effects.append(SetStatusEffect("Ready"))
                effects.append(CompleteJobEffect("Ready"))
        elif state.handler_type in ('image', 'agent', 'web'):
            effects.append(SetStatusEffect("Ready"))
            effects.append(CompleteJobEffect("Ready"))

        new_state = SendHandlerState(
            handler_type=state.handler_type,
            status="done",
            query_text=state.query_text,
            model=state.model,
            doc_type_str=state.doc_type_str,
            round_num=state.round_num,
            pending_tools=state.pending_tools,
            max_rounds=state.max_rounds,
            recent_effects=tuple(effects)
        )
        return new_state, effects

    if isinstance(event, StartEvent):
        base_state_kwargs = dict(
            handler_type=state.handler_type,
            status="starting",
            query_text=event.query_text,
            model=event.model,
            doc_type_str=event.doc_type_str,
            round_num=state.round_num,
            pending_tools=state.pending_tools,
            max_rounds=state.max_rounds,
        )

        if state.handler_type == 'audio':
            effects.append(SetStatusEffect("Transcribing audio..."))
            effects.append(UpdateUIEffect("\n[Transcribing audio...]\n"))
            effects.append(SpawnAudioWorkerEffect(
                wav_path=event.wav_path,
                stt_model=event.stt_model,
                model=event.model,
                query_text=event.query_text
            ))

            new_state = SendHandlerState(**base_state_kwargs, recent_effects=tuple(effects))
            return new_state, effects

        elif state.handler_type == 'image':
            effects.append(UpdateUIEffect(f"\nYou: {event.query_text}\n"))
            effects.append(UpdateUIEffect("\n[Using image model (direct).]\n"))
            effects.append(UpdateUIEffect("AI: Creating image...\n"))
            effects.append(SetStatusEffect("Creating image..."))
            effects.append(SpawnDirectImageEffect(event.query_text, event.model))
            new_state = SendHandlerState(**base_state_kwargs, recent_effects=tuple(effects))
            return new_state, effects

        elif state.handler_type == 'agent':
            effects.append(UpdateUIEffect(f"\nYou: {event.query_text}\n"))
            effects.append(UpdateUIEffect("\n[Using external agent backend.]\n"))
            effects.append(UpdateUIEffect("AI: "))
            effects.append(SetStatusEffect("Starting agent..."))
            effects.append(SpawnAgentWorkerEffect(event.query_text, event.model, event.doc_type_str))
            new_state = SendHandlerState(**base_state_kwargs, recent_effects=tuple(effects))
            return new_state, effects

        elif state.handler_type == 'web':
            effects.append(UpdateUIEffect(f"\nYou: {event.query_text}\n"))
            effects.append(UpdateUIEffect("\n[Using research chat.]\n"))
            effects.append(SetStatusEffect("Starting research..."))
            effects.append(SpawnWebWorkerEffect(event.query_text, event.model))
            new_state = SendHandlerState(**base_state_kwargs, recent_effects=tuple(effects))
            return new_state, effects

    return state, effects
