# State Machine Extraction Roadmap

This document identifies complex orchestration functions that should undergo state machine extraction (like `tool_loop.py`) to enable formal verification.

## Priority 1: Chatbot Orchestration (Current Focus)

### 1. **tool_loop.py** ⏳ *(Jules in progress)*
**Complexity**: ⭐⭐⭐⭐⭐
**State variables**: `_active_round_num`, `_active_pending_tools`, `_send_busy`
**Side effects**: Thread spawning, UI updates, network calls
**Verification targets**:
- Round counter never exceeds max
- Stop requests terminate immediately
- Tool results processed in order

### 2. **send_handlers.py** - SendHandlersMixin
**Complexity**: ⭐⭐⭐⭐
**State variables**: Audio recording state, web research state, image generation state
**Side effects**: File I/O, subprocess management, API calls
**Verification targets**:
- Only one handler active at a time
- Resources properly cleaned up
- Error states handled consistently

### 3. **panel.py** - SendButtonListener
**Complexity**: ⭐⭐⭐
**State variables**: Button states, UI model synchronization
**Side effects**: UNO control updates, event bus emissions
**Verification targets**:
- Send/Stop button states mutually exclusive
- UI always reflects actual state

## Priority 2: Framework Services

### 4. **event_bus.py** - EventBusService
**Complexity**: ⭐⭐⭐⭐
**State variables**: Subscriber registry, event queue
**Side effects**: Callback invocation, error handling
**Verification targets**:
- No event loss under load
- Subscribers notified in order
- Memory leaks prevented

### 5. **config.py** - ConfigService
**Complexity**: ⭐⭐⭐
**State variables**: Configuration cache, dirty flags
**Side effects**: File I/O, validation errors
**Verification targets**:
- Atomic updates
- Validation before persistence
- Thread-safe access

## Priority 3: AI Horde Client

### 6. **aihordeclient/__init__.py** - AIHordeClient
**Complexity**: ⭐⭐⭐⭐
**State variables**: Job queue, connection state, progress tracking
**Side effects**: Network requests, file downloads, UI updates
**Verification targets**:
- Job queue processed FIFO
- Progress updates monotonic
- Error recovery paths

## Priority 4: HTTP Server

### 7. **http/routes.py** - RouteHandler
**Complexity**: ⭐⭐⭐
**State variables**: Request context, route registry
**Side effects**: HTTP responses, error handling
**Verification targets**:
- Route matching correctness
- Error responses consistent
- No resource leaks

## Implementation Pattern

### For each module:

```python
# 1. Define State (frozen dataclass)
@dataclass(frozen=True)
class ToolLoopState:
    round_num: int
    pending_tools: list[ToolCall]
    max_rounds: int
    status: ToolLoopStatus

# 2. Define Events
@dataclass(frozen=True)
class StreamDoneEvent:
    content: str
    
@dataclass(frozen=True)
class ToolResultEvent:
    tool_id: str
    result: dict

# 3. Define Effects (Commands)
@dataclass(frozen=True)
class SpawnLLMWorkerEffect:
    messages: list[dict]
    
@dataclass(frozen=True)
class UpdateUIEffect:
    text: str
    is_thinking: bool = False

# 4. Pure Transition Function
@deal.pre(lambda state, event: state.round_num <= state.max_rounds)
@deal.post(lambda state, event, result: result[0].round_num <= state.max_rounds)
@deal.ensure(lambda state, event, result: 
    not (isinstance(event, StopRequestedEvent) and 
         any(isinstance(e, SpawnLLMWorkerEffect) for e in result[1])))
def next_state(
    state: ToolLoopState, 
    event: ToolLoopEvent
) -> tuple[ToolLoopState, list[ToolLoopEffect]]:
    """Pure state transition - NO SIDE EFFECTS"""
    # ... implementation ...

# 5. Effect Interpreter (side effects here)
class EffectInterpreter:
    def interpret(self, effect: ToolLoopEffect):
        if isinstance(effect, SpawnLLMWorkerEffect):
            # Actual thread spawning, UNO calls, etc.
            pass
        elif isinstance(effect, UpdateUIEffect):
            # Actual UI updates
            pass
```

## Verification Strategy

### Contract Examples:

```python
# Tool loop invariants
@deal.ensure(lambda s, e, r: r[0].round_num >= s.round_num)  # Monotonic
@deal.ensure(lambda s, e, r: len(r[1]) <= 3)  # Max 3 effects per transition

# Event handling
@deal.pre(lambda s, e: not (isinstance(e, ToolResultEvent) and not s.pending_tools))

# Resource safety
@deal.ensure(lambda s, e, r: 
    not any(isinstance(eff, SpawnLLMWorkerEffect) for eff in r[1]) or
    not any(isinstance(eff, SpawnLLMWorkerEffect) for eff in s.recent_effects))
```

## Testing Approach

### Unit Test Structure:
```python
class TestToolLoopStateMachine:
    def test_stop_event_terminates(self):
        state = ToolLoopState(round_num=2, pending_tools=[...], max_rounds=10)
        event = StopRequestedEvent()
        
        new_state, effects = next_state(state, event)
        
        # Verify no new workers spawned
        assert not any(isinstance(e, SpawnLLMWorkerEffect) for e in effects)
        
        # Verify termination state
        assert new_state.status == ToolLoopStatus.TERMINATED

    def test_round_counter_invariant(self):
        """Round counter never exceeds max"""
        state = ToolLoopState(round_num=9, pending_tools=[], max_rounds=10)
        event = StreamDoneEvent("some content")
        
        new_state, _ = next_state(state, event)
        assert new_state.round_num <= 10
```

## Roadmap Timeline

```
Q1 2026: ✅ tool_loop.py (Jules - in progress)
Q1 2026: 🔄 send_handlers.py
Q1 2026: 📋 panel.py button states
Q2 2026: 📡 event_bus.py
Q2 2026: ⚙️  config.py
Q3 2026: 🤖 aihordeclient/
Q3 2026: 🌐 http/routes.py
```

## Benefits

1. **Verifiability**: Pure functions can use CrossHair
2. **Testability**: Deterministic state transitions
3. **Maintainability**: Clear separation of concerns
4. **Safety**: Mathematical proofs about critical paths
5. **Performance**: Easier to optimize pure logic

## Anti-Patterns to Avoid

❌ **Mixing state and effects** - Keep transition function pure
❌ **Complex event types** - Keep events simple data carriers
❌ **Overly broad effects** - Make effects granular
❌ **Ignoring edge cases** - Explicitly handle all event types
