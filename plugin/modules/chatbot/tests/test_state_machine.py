import pytest
from plugin.modules.chatbot.state_machine import (
    SendHandlerState, next_state, StartEvent, StopRequestedEvent,
    StreamChunkEvent, StreamDoneEvent, ErrorEvent, UpdateUIEffect, SetStatusEffect, CompleteJobEffect,
    SpawnDirectImageEffect, SpawnAgentWorkerEffect, SpawnWebWorkerEffect
)

class TestSendHandlerStateMachine:
    def test_start_image(self):
        state = SendHandlerState(handler_type="image", status="ready")
        event = StartEvent(query_text="draw a cat", model=None, doc_type_str="image")

        new_state, effects = next_state(state, event)

        assert new_state.status == "starting"
        assert new_state.query_text == "draw a cat"
        assert len(effects) == 5
        assert isinstance(effects[0], UpdateUIEffect) # You
        assert isinstance(effects[1], UpdateUIEffect) # Using image
        assert isinstance(effects[2], UpdateUIEffect) # AI:
        assert isinstance(effects[3], SetStatusEffect)
        assert isinstance(effects[4], SpawnDirectImageEffect)

    def test_start_web(self):
        state = SendHandlerState(handler_type="web", status="ready")
        event = StartEvent(query_text="search python", model=None, doc_type_str="web")

        new_state, effects = next_state(state, event)

        assert new_state.status == "starting"
        assert new_state.query_text == "search python"
        assert len(effects) == 4
        assert isinstance(effects[0], UpdateUIEffect) # You
        assert isinstance(effects[1], UpdateUIEffect) # Using research
        assert isinstance(effects[2], SetStatusEffect) # Starting
        assert isinstance(effects[3], SpawnWebWorkerEffect)

    def test_stop_event_agent_terminates(self):
        state = SendHandlerState(handler_type="agent", status="running", round_num=2, max_rounds=10)
        event = StopRequestedEvent()

        new_state, effects = next_state(state, event)

        # Verify termination state
        assert new_state.status == "stopped"

        # Verify proper effects
        assert len(effects) == 3
        assert isinstance(effects[0], SetStatusEffect)
        assert effects[0].status_text == "Stopped"
        assert isinstance(effects[1], UpdateUIEffect)
        assert effects[1].text == "\n[Stopped by user]\n"
        assert isinstance(effects[2], CompleteJobEffect)
        assert effects[2].terminal_status == "Stopped"

    def test_stop_event_other_terminates(self):
        state = SendHandlerState(handler_type="web", status="running", round_num=2, max_rounds=10)
        event = StopRequestedEvent()

        new_state, effects = next_state(state, event)

        # Verify termination state
        assert new_state.status == "stopped"

        # Verify proper effects - should NOT have the UpdateUIEffect artifact for web/image
        assert len(effects) == 2
        assert isinstance(effects[0], SetStatusEffect)
        assert effects[0].status_text == "Stopped"
        assert isinstance(effects[1], CompleteJobEffect)
        assert effects[1].terminal_status == "Stopped"

    def test_stream_chunk(self):
        state = SendHandlerState(handler_type="image", status="running", query_text="cat")
        event = StreamChunkEvent(chunk_text="test data")

        new_state, effects = next_state(state, event)

        assert new_state.status == "running" # Unchanged
        assert new_state.query_text == "cat"
        assert len(effects) == 1
        assert isinstance(effects[0], UpdateUIEffect)
        assert effects[0].text == "test data"

    def test_error_event(self):
        state = SendHandlerState(handler_type="web", status="running")
        event = ErrorEvent(error=Exception("Network failure"))

        new_state, effects = next_state(state, event)

        assert new_state.status == "error"
        assert len(effects) == 3
        assert isinstance(effects[0], SetStatusEffect)
        assert effects[0].status_text == "Error"
        assert isinstance(effects[1], UpdateUIEffect)
        assert "Research Chat error: Network failure" in effects[1].text
        assert isinstance(effects[2], CompleteJobEffect)
        assert effects[2].terminal_status == "Error"

    def test_round_counter_invariant(self):
        # A mock test to verify that the next_state contract holds (e.g. no exceptions thrown)
        state = SendHandlerState(handler_type="agent", status="running", round_num=5, max_rounds=10)
        event = StreamDoneEvent(response={})

        new_state, effects = next_state(state, event)
        assert new_state.round_num <= 10 # Post condition passes
