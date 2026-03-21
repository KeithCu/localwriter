import pytest
from plugin.modules.chatbot.tool_loop_state import (
    ToolLoopState,
    StopRequestedEvent,
    FinalDoneEvent,
    ErrorEvent,
    StreamDoneEvent,
    NextToolEvent,
    ToolResultEvent,
    SpawnLLMWorkerEffect,
    SpawnFinalStreamEffect,
    SpawnToolWorkerEffect,
    UpdateUIEffect,
    UpdateStatusEffect,
    LogAgentEffect,
    LogDebugEffect,
    AddAssistantMessageEffect,
    AddToolResultEffect,
    UpdateDocumentContextEffect,
    UpdateActivityStateEffect,
    TriggerNextToolEffect,
    ExitLoopEffect,
    next_state,
)

def create_base_state():
    return ToolLoopState(
        round_num=0,
        pending_tools=[],
        max_rounds=5,
        status="Ready",
        async_tools=frozenset(["web_research", "generate_image"])
    )

def test_stop_requested():
    state = create_base_state()
    event = StopRequestedEvent()
    new_state, effects = next_state(state, event)

    assert new_state.is_stopped is True
    assert new_state.status == "Stopped"

    effect_types = [type(e) for e in effects]
    assert AddAssistantMessageEffect in effect_types
    assert UpdateStatusEffect in effect_types
    assert UpdateUIEffect in effect_types
    assert ExitLoopEffect in effect_types

def test_final_done():
    state = create_base_state()
    event = FinalDoneEvent(content="Final words")
    new_state, effects = next_state(state, event)

    assert new_state.status == "Ready"

    effect_types = [type(e) for e in effects]
    assert AddAssistantMessageEffect in effect_types
    assert UpdateUIEffect in effect_types
    assert UpdateStatusEffect in effect_types
    assert ExitLoopEffect in effect_types
    
    # check that AddAssistantMessageEffect has the content
    msg_effect = next(e for e in effects if isinstance(e, AddAssistantMessageEffect))
    assert msg_effect.content == "Final words"

def test_error_event():
    state = create_base_state()
    event = ErrorEvent(error=Exception("Something broke"))
    new_state, effects = next_state(state, event)

    assert new_state.status == "Error"

    effect_types = [type(e) for e in effects]
    assert ExitLoopEffect in effect_types

def test_stream_done_finish_reasons():
    state = create_base_state()
    
    # finish_reason="length"
    event_len = StreamDoneEvent(response={"finish_reason": "length", "content": None})
    new_state_len, effects_len = next_state(state, event_len)
    assert new_state_len.status == "Ready"
    ui_effs = [e for e in effects_len if isinstance(e, UpdateUIEffect)]
    assert any("out of tokens" in e.text for e in ui_effs)
    
    # finish_reason="content_filter"
    event_filt = StreamDoneEvent(response={"finish_reason": "content_filter", "content": None})
    new_state_filt, effects_filt = next_state(state, event_filt)
    ui_effs = [e for e in effects_filt if isinstance(e, UpdateUIEffect)]
    assert any("Content filter" in e.text for e in ui_effs)

def test_next_tool_max_rounds():
    state = create_base_state()
    # If the state round is 4 and max_rounds is 5, then the new round_num will be 5
    # Let's say we start at round=4 next_state handles NextToolEvent
    state = ToolLoopState(round_num=4, pending_tools=[], max_rounds=5, status="Ready")
    event = NextToolEvent()
    new_state, effects = next_state(state, event)

    assert new_state.round_num == 5
    effect_types = [type(e) for e in effects]
    assert SpawnFinalStreamEffect in effect_types
    assert SpawnLLMWorkerEffect not in effect_types

def test_next_tool_malformed_arguments():
    # If we have a pending tool with malformed arguments, it should parse as empty dict
    tool_calls = [
        {"id": "call_1", "type": "function", "function": {"name": "test_tool", "arguments": "invalid-json"}}
    ]
    state = ToolLoopState(round_num=0, pending_tools=tool_calls, max_rounds=5, status="Ready")
    event = NextToolEvent()
    new_state, effects = next_state(state, event)
    
    assert len(new_state.pending_tools) == 0
    
    spawn_eff = next(e for e in effects if isinstance(e, SpawnToolWorkerEffect))
    assert spawn_eff.func_name == "test_tool"
    assert spawn_eff.func_args == {}  # Handled parsing failure
    assert spawn_eff.func_args_str == "invalid-json"

def test_tool_result_parsing():
    state = create_base_state()
    
    # Valid JSON tool result
    event_valid = ToolResultEvent(call_id="call_x", func_name="test_tool", func_args_str="{}", result='{"success": true, "message": "done"}', mutates_document=True)
    new_state, effects = next_state(state, event_valid)
    effect_types = [type(e) for e in effects]
    assert AddToolResultEffect in effect_types
    assert UpdateDocumentContextEffect in effect_types  # Because is_success=True and mutates=True
    assert TriggerNextToolEffect in effect_types

    # apply_document_content edge case output
    event_adc = ToolResultEvent(call_id="call_y", func_name="apply_document_content", func_args_str='{"content": "A" * 1000}', result='{"message": "Replaced 0 occurrences"}', mutates_document=True)
    new_state_adc, effects_adc = next_state(state, event_adc)
    
    ui_effs = [e for e in effects_adc if isinstance(e, UpdateUIEffect)]
    assert any("[Debug: params" in e.text for e in ui_effs)
    # the 1000 'A's should be truncated to 800 + "..."
    assert any("..." in e.text for e in ui_effs)
