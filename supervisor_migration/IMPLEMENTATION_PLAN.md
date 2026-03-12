# Supervisor Migration - Implementation Plan

## Status: Implemented

This document describes the native LangGraph supervisor pattern implementation that replaces the tool-based orchestration in `master_agent_graph.py`.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SUPERVISOR GRAPH                                     │
│                                                                              │
│   START                                                                      │
│     │                                                                        │
│     ▼                                                                        │
│  ┌──────────┐                                                                │
│  │  router  │◄──────────────────────────────────────────┐                   │
│  └────┬─────┘                                           │                   │
│       │                                                 │                   │
│       ├─────────────────┬─────────────────┐            │                   │
│       ▼                 ▼                 ▼            │                   │
│  ┌──────────┐    ┌──────────────┐   ┌──────────┐       │                   │
│  │ decline  │    │    smart     │   │   hitl   │       │                   │
│  │ _letter  │    │  _strategy   │   │  (node)  │       │                   │
│  └────┬─────┘    └──────┬───────┘   └────┬─────┘       │                   │
│       │                 │                │              │                   │
│       └─────────────────┴────────────────┴──────────────┘                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
supervisor_migration/
├── __init__.py              # Package exports
├── state.py                 # SupervisorState, WorkflowStatus, ContextFrame
├── prompts.py               # All prompts including rejection messages
├── agent_config.py          # Agent configurations with is_workflow flag
├── streaming_utils.py       # MLflow-compatible streaming helpers
├── router.py                # Router with workflow validation
├── agent_nodes.py           # Agent wrapper nodes
├── hitl_node.py             # HITL as graph node
├── supervisor_graph.py      # Main graph assembly
├── supervisor_agent.py      # Entry point (LanggraphResponsesAgent)
├── IMPLEMENTATION_PLAN.md   # This file
└── tests/
    ├── __init__.py
    ├── test_router.py       # 17 tests
    ├── test_workflow.py     # 23 tests
    └── test_integration.py  # 12 tests (5 need mlflow)
```

---

## Key Components

### 1. State Models (`state.py`)

```python
class WorkflowStatus(BaseModel):
    name: str = ""           # Active workflow name
    is_finished: bool = False

    def is_active(self) -> bool
    def can_start_workflow(workflow_name) -> tuple[bool, str]

class ContextFrame(BaseModel):
    agent_name: str          # Parent agent waiting
    context: str             # What parent asked for
    parent_state: dict       # State to restore
    artifact: dict           # Artifacts to pass
    task_id: str

class SupervisorState(MessagesState):  # TypedDict
    current_agent: str
    context_stack: list[ContextFrame]
    workflow: WorkflowStatus
    is_direct: bool
    target_agent: str
    trusted: bool
    current_artifact: dict
    input_path: Literal["tool", "human", ""]
    last_agent_response: str
    has_error: bool
    error_message: str
```

### 2. Agent Configuration (`agent_config.py`)

```python
AGENT_ENDPOINTS = {
    "decline_letter": {
        "endpoint_name": "decline-letter-agent",
        "description": "Crafts standardized declined letters...",
        "is_workflow": True,   # Workflow agent
        ...
    },
    "smart_strategy": {
        "endpoint_name": "smart-strategy-agent",
        "description": "Helps find claim IDs...",
        "is_workflow": True,   # Updated per user change
        ...
    },
}
```

### 3. Router (`router.py`)

Handles:
1. **New conversation** → Welcome prompt via HITL
2. **Direct request** (`is_direct=True`) → Bypass LLM, route to target
3. **Trusted resume** → Return to parent from context_stack
4. **LLM classification** → Intent classification with tool binding
5. **Workflow validation** → Reject invalid transitions

```python
def _process_workflow_rejection(tool_name, workflow, workflow_agents, non_workflow_agents):
    """Returns rejection message or None if allowed."""

def create_router_node(llm, tools, max_last_messages=1):
    """Creates router node function."""

def route_to_agent(state) -> str:
    """Conditional edge function."""
```

### 4. HITL Node (`hitl_node.py`)

HITL as a graph node (not a tool):

```python
def hitl_node(state: SupervisorState) -> dict:
    # 1. Prepare content to show user
    # 2. Call interrupt() to pause
    # 3. Process user response on resume
    # 4. Return state updates for router
```

### 5. Workflow Management

**Rules:**
- CAN switch between workflows mid-conversation (user requirement)
- Cannot restart a FINISHED workflow (must start new conversation)
- Non-workflow agents are always allowed

**Rejection Prompts:**
```python
REJECT_FINISHED_WORKFLOW = "The {workflow_name} workflow has already been completed..."
# REJECT_DIFFERENT_WORKFLOW removed - switching allowed
```

### 6. Input Collection (New)

Some agents require specific inputs before they can execute. The router handles this:

**smart_strategy requires 4 inputs:**
- Claim ID
- Policy Number
- Date Range
- Customer Name

**Flow:**
1. User requests smart_strategy
2. Router detects required inputs not provided
3. Routes to HITL with input collection prompt
4. User provides inputs (single value or key-value pairs)
5. Router parses and stores in `collected_inputs`
6. When all inputs collected, routes to agent

**State fields:**
```python
collected_inputs: dict      # {agent_name: {field: value, ...}}
collecting_inputs_for: str  # Agent we're collecting for, or ""
```

---

## Comparison with Original Implementation

| Aspect | Original (`master_agent_graph.py`) | Supervisor Migration |
|--------|-----------------------------------|---------------------|
| Lines of code | ~320 | ~200 (router.py) |
| HITL | Tool with `interrupt()` | Graph node |
| State | Complex tool-based schemas | Simple TypedDict + Pydantic |
| Workflow logic | Inline in intent_classifier | Separate `_process_workflow_rejection` |
| Input paths | Two separate branches | Unified in router |

---

## Test Coverage

```
47 passed, 5 skipped

test_workflow.py (23 tests)
├── TestWorkflowStatus (8) - is_active, can_start_workflow
├── TestContextFrame (2) - defaults, all values
├── TestSupervisorStateHelpers (10) - create_initial_state, getters
└── TestWorkflowTransitions (3) - start, finish, in_state

test_router.py (17 tests)
├── TestWorkflowRejection (5) - all rejection scenarios
├── TestHelperFunctions (5) - get_last_human_messages, get_context
├── TestRouteToAgent (4) - routing logic
└── TestRouterNode (3) - welcome, direct, invalid

test_integration.py (12 tests, 5 need mlflow)
├── TestGraphCreation (2) - skipped without langgraph
├── TestStateTransitions (2) - welcome, direct routing
├── TestWorkflowManagement (2) - start workflow, non-workflow
├── TestErrorHandling (1) - unknown agent
├── TestContextStack (2) - preserve, nested
└── TestStreamingEvents (3) - skipped without mlflow
```

---

## Usage

```python
# Basic imports (no external deps)
from supervisor_migration import (
    SupervisorState,
    WorkflowStatus,
    ContextFrame,
    create_initial_state,
    AGENT_ENDPOINTS,
    get_workflow_agents,
)

# Full graph (requires langchain, langgraph, mlflow, databricks-sdk)
from supervisor_migration.supervisor_graph import create_supervisor_graph
from supervisor_migration.supervisor_agent import SupervisorAgent

# Create graph
graph = create_supervisor_graph(
    llm=llm,
    tools=tools,
    get_client=lambda: workspace_client.serving_endpoints.get_open_ai_client(),
)
compiled = graph.compile(checkpointer=checkpointer)
```

---

## Dependencies

**Required:**
- `pydantic` - State models
- `langchain-core` - Messages, tools

**Optional (for full functionality):**
- `langgraph` - Graph execution
- `mlflow` - ResponsesAgent interface
- `databricks-sdk` - Endpoint calls
- `backoff` - Retry logic

---

## Next Steps

1. **Integration Testing**: Test with actual Databricks endpoints
2. **Streaming Verification**: Confirm frontend compatibility
3. **Migration**: Swap out `master_agent_graph.py` for `SupervisorAgent`
4. **Cleanup**: Remove old tool-based orchestration code
