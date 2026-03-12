# Implementation Plan: Native Supervisor Pattern Migration

**Duration:** 10-12 Days
**Scope:** Migrate from agents-as-tools to native LangGraph supervisor pattern

---

## Architectural Changes

### Current Architecture: Agents-as-Tools with Task Stack

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                              FRONTEND REQUEST                                │
  │  {input: [{content: [{text, custom_inputs}]}], custom_inputs: {state, ...}} │
  └─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                         predict_stream() Entry                               │
  │  1. Validate custom_inputs                                                   │
  │  2. Init checkpointer (StatelessMemorySaver)                                │
  │  3. Compile graph                                                            │
  │  4. Preprocess → HumanMessage or Command(resume=...)                        │
  └─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                         LANGGRAPH EXECUTION LOOP                             │
  │  ┌─────────────────────┐    ┌─────────────────────┐                         │
  │  │  intent_classifier  │───▶│     tool_node       │                         │
  │  │     (~200+ lines)     │    │                     │                         │
  │  │                     │    │  • ToolFactory      │                         │
  │  │  • Check task_stack │    │  • Execute tool     │                         │
  │  │  • LLM routing      │◀───│  • Stream events    │                         │
  │  │  • Create AIMessage │    │  • Return ToolMsg   │                         │
  │  └─────────────────────┘    └─────────────────────┘                         │
  │           │                          │                                       │
  │           │ (end_condition)          │ (sub-agent call)                     │
  │           ▼                          ▼                                       │
  │        ┌──────┐            ┌───────────────────┐                            │
  │        │ END  │            │ Databricks Mosaic │                            │
  │        └──────┘            │    Endpoint       │                            │
  │                            └───────────────────┘                            │
  └─────────────────────────────────────────────────────────────────────────────┘
                                        │
                      ┌─────────────────┴─────────────────┐
                      ▼                                   ▼
            ┌─────────────────┐                 ┌─────────────────┐
            │  GraphInterrupt │                 │  Normal Complete │
            │  (HITL pause)   │                 │                  │
            └─────────────────┘                 └─────────────────┘
                      │                                   │
                      └─────────────────┬─────────────────┘
                                        ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                         STREAMING TO FRONTEND                                │
  │  1. ResponseTextDeltaEvent (LLM tokens)                                     │
  │  2. ResponseOutputItemDoneEvent (thinking/llm/response)                     │
  │  3. ResponseCompletedEvent (final state for resume)                         │
  └─────────────────────────────────────────────────────────────────────────────┘

  ---
  Task Stack for Nested Calls (A → B → A)

  Example: User wants declined letter but doesn't know claim_id

  ┌─────────────────────────────────────────────────────────────────┐
  │ Step 1: User asks for declined letter                           │
  │                                                                 │
  │   task_stack: []                                                │
  │   intent_classifier → routes to DeclineLetter tool              │
  └─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ Step 2: DeclineLetter needs claim_id, user doesn't know it      │
  │                                                                 │
  │   task_stack: [
  │     TaskStruct(
  │       parent_tool: "DeclineLetter",
  │       parent_state: {...},           ← saves DeclineLetter state│
  │       tool_struct: ToolStruct(...)
  │     )
  │   ]
  │   intent_classifier → routes to SmartStrategy tool              │
  └─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ Step 3: SmartStrategy completes, returns claim_id               │
  │                                                                 │
  │   task_stack: [] ← popped                                       │
  │   SmartStrategy returns → intent_classifier sees parent         │
  │   → Automatically routes back to DeclineLetter with claim_id    │
  └─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ Step 4: DeclineLetter resumes with claim_id, generates letter   │
  │                                                                 │
  │   task_stack: []                                                │
  │   DeclineLetter completes → END                                 │
  └─────────────────────────────────────────────────────────────────┘

  ---
  Data Model Complexity (Current)

  ┌─────────────────────────────────────────────────────────────────┐
  │                        MasterAgentState                          │
  ├─────────────────────────────────────────────────────────────────┤
  │  messages: List[BaseMessage]                                     │
  │  task_stack: List[TaskStruct]  ─────────────────────┐           │
  └─────────────────────────────────────────────────────────────────┘
                                                         │
                      ┌──────────────────────────────────┘
                      ▼
            ┌─────────────────────────┐
            │      TaskStruct         │
            ├─────────────────────────┤
            │  parent_tool: str       │
            │  parent_state: dict     │
            │  task_id: str           │
            │  tool_struct: ToolStruct│──────┐
            └─────────────────────────┘      │
                                             ▼
                                ┌─────────────────────────┐
                                │      ToolStruct         │
                                ├─────────────────────────┤
                                │  context: str           │
                                │  content: Content       │
                                │  tool_argument: ToolArg │──────┐
                                └─────────────────────────┘      │
                                                                 ▼
                                                ┌─────────────────────────┐
                                                │     ToolArgument        │
                                                ├─────────────────────────┤
                                                │  name: str              │
                                                │  arguments: dict        │
                                                └─────────────────────────┘

  Plus: ToolMetadata, ToolContentStruct, StandardToolArgument, FrontEndInputStruct...
        (8+ schema classes for orchestration)

  ---
  New Architecture (Option B): Native Supervisor

  ┌─────────────────────────────────────────────────────────────────┐
  │                         SIMPLIFIED GRAPH                         │
  │                                                                  │
  │     ┌──────────┐                                                │
  │     │  START   │                                                │
  │     └────┬─────┘                                                │
  │          │                                                       │
  │          ▼                                                       │
  │     ┌──────────┐      ┌──────────────┐                          │
  │     │  router  │─────▶│ decline_letter│                         │
  │     │  (~50    │      └──────┬───────┘                          │
  │     │  lines)  │             │                                   │
  │     │          │◀────────────┘                                   │
  │     │          │                                                 │
  │     │          │      ┌──────────────┐                          │
  │     │          │─────▶│smart_strategy │                         │
  │     │          │      └──────┬───────┘                          │
  │     │          │◀────────────┘                                   │
  │     │          │                                                 │
  │     │          │      ┌──────────────┐                          │
  │     │          │─────▶│    hitl      │ (interrupt)              │
  │     │          │      └──────┬───────┘                          │
  │     │          │◀────────────┘                                   │
  │     │          │                                                 │
  │     │          │─────▶ END                                       │
  │     └──────────┘                                                │
  │                                                                  │
  │  State: { messages, current_agent, context_stack }              │
  │  context_stack: [ContextFrame(agent_name, context)]  ← 2 fields │
  └─────────────────────────────────────────────────────────────────┘

  ---
  Comparison Side-by-Side

  CURRENT (Agents-as-Tools)              NEW (Native Supervisor)
  ─────────────────────────              ─────────────────────────

  intent_classifier (200 lines)    →     router (50 lines)
          │                                      │
          ▼                                      ▼
      ToolNode                             conditional_edges
          │                                      │
          ▼                                      ▼
     ToolFactory                           agent_nodes
                                
          │                                      │
          ▼                                      ▼
     task_stack                            context_stack
     [TaskStruct                           [ContextFrame
       [ToolStruct                           (agent_name,
         [ToolArgument]]]                     context)]

  ~800 lines                         →    ~400 lines
  8+ schema classes                  →    3 simple models

## Key Issues

1. The `task_stack` Anti-Pattern:
   * **Problem**: The intent_classifier manually pushes and pops items from a task_stack to track conversation depth. This reinvents the wheel. LangGraph is already a state machine designed to handle graph traversal.
   * **Consequence**: The logic in intent_classifier (in master_agent_graph.py) is extremely brittle. It contains nested conditions checking if last_task.parent_tool == last_message.name to decide whether to pop the stack. This logic will be a nightmare to debug if an agent fails unexpectedly or returns a non-standard message.

2. Monolithic `intent_classifier` Node:
   * **Problem**: The intent_classifier function does too much: routing, response formatting, state cleanup, and prompt generation.
   * **Consequence**: It violates the Single Responsibility Principle. A change in how "Welcome" messages are formatted requires editing the core routing logic.

3. Excessive Schema Wrapping:
   * **Problem**: Files like schemas.py and response_agent.py are filled with custom classes (ResponseAgentCustomOutput, SIResponsesAgentStreamEvent, Content, OutputItem) that wrap standard LangChain types.
   * **Consequence**: This adds a massive serialization/deserialization overhead. Developers spend more time marshalling data between formats than writing business logic.

4. Complex Tool Factory:
   * **Problem**: ToolFactory dynamically generates tool functions with decorators inside a method.
   * **Consequence**: This makes the code hard to statically analyze, type-check, or unit test. It hides the dependencies of the master agent.

### When TO Use Agents-as-Tools

Keep the current pattern if:
* You expect to add 10+ agents dynamically
* Agents are plugins that users can configure
* You need LLM to discover/compose unknown agents
* You're building a general-purpose agent framework

---

## Critical Design Decisions

### Functionality Parity Checklist

The new implementation MUST support all existing functionality:

| Feature | Current Implementation | New Implementation |
|---------|----------------------|-------------------|
| Task nesting (A→B→C→B→A) | `task_stack: List[TaskStruct]` | `context_stack: List[ContextFrame]` |
| LLM intent classification | `hitl_handler` with `IC_PROMPT_TEMPLATE` | Router node with same prompt |
| **Direct request (`is_direct`)** | Bypasses LLM, goes straight to agent | Router checks `is_direct` flag first |
| **`trusted` flag** | Skips LLM classification on resume | Router respects `trusted` flag |
| **State preservation** | `parent_state` in TaskStruct | `parent_state` in ContextFrame |
| **Artifact passing** | `ToolContentStruct.artifact` | `artifact` in ContextFrame |
| Completion detection | `need_resume` / `is_interrupt` | Same flags checked in agent node |
| Retry with backoff | `_get_final_event` retry loop | Same logic in agent node |
| Streaming thinking messages | `prepare_thinking_message()` | Same utility function |

---

## Phase 1: Foundation & Architecture (Days 1-4)

### New `__init__.py` Files to Create

```
src/__init__.py
src/agents/__init__.py
src/agents/orchestrator/__init__.py
src/smart_ investigator/__init__.py
src/smart_ investigator/foundation/__init__.py
src/smart_ investigator/foundation/agents/__init__.py
src/smart_ investigator/foundation/schemas/__init__.py
src/smart_ investigator/foundation/tools/__init__.py
```

### Create `requirements.txt`

```
langgraph>=0.2.0
langchain-core>=0.3.0
langchain-openai>=0.2.0
mlflow>=2.17.0
pydantic>=2.0.0
databricks-sdk>=0.30.0
httpx>=0.27.0
httpx-sse>=0.4.0
backoff>=2.2.0
more-itertools>=10.0.0
fastapi>=0.110.0
pyyaml>=6.0.0
```

### New File: `src/agents/orchestrator/state.py`

Defines state model with FULL functionality support:

```python
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing import Annotated, Literal, Optional, Any

class ContextFrame(BaseModel):
    """
    Replaces TaskStruct - maintains context for nested agent calls.

    When agent A calls agent B:
    1. Push ContextFrame(agent_name="A", parent_state=A's_state, ...) to stack
    2. Execute agent B
    3. When B completes, pop frame and return to A with preserved state
    """
    agent_name: str = Field(description="Name of the parent agent waiting for response")
    context: str = Field(description="What the parent agent was asking for")
    parent_state: dict = Field(default={}, description="Serialized state of parent agent to restore on return")
    artifact: dict = Field(default={}, description="Artifacts passed between agents (e.g., claim data, generated content)")
    task_id: str = Field(default="", description="Unique identifier for this task context")

class SupervisorState(MessagesState):
    """
    Main state for the supervisor graph.

    Replaces MasterAgentState but maintains same capabilities.
    """
    messages: Annotated[list, add_messages]
    current_agent: str = Field(default="", description="Next agent to route to")
    context_stack: list[ContextFrame] = Field(default=[], description="Stack for nested agent calls")

    # Direct request support (preserves is_direct functionality)
    is_direct: bool = Field(default=False, description="If True, bypass LLM classification")
    target_agent: str = Field(default="", description="Agent to call directly when is_direct=True")
    trusted: bool = Field(default=False, description="If True, skip LLM classification on HITL resume")

    # Artifact passing
    current_artifact: dict = Field(default={}, description="Artifact from last agent response")

AGENT_NAMES = Literal[
    "decline_letter",
    "smart_strategy",
    "agent_3",
    "agent_4",
    "agent_5",
    "hitl",
    "end"
]
```

### New File: `src/agents/orchestrator/agent_config.py`

Replaces YAML-based tool configuration:

```python
from typing import TypedDict

class AgentEndpointConfig(TypedDict):
    endpoint_name: str
    description: str
    introduction: str
    expose_to_user: bool
    can_generate_task: bool
    use_checkpointer: bool

AGENT_ENDPOINTS: dict[str, AgentEndpointConfig] = {
    "decline_letter": {
        "endpoint_name": "decline-letter-agent",
        "description": "Crafts standardized declined letters for insurance claims",
        "introduction": "I can help you craft a declined letter.",
        "expose_to_user": True,
        "can_generate_task": True,
        "use_checkpointer": False,
    },
    "smart_strategy": {
        "endpoint_name": "smart-strategy-agent",
        "description": "Helps find claim IDs and related information",
        "introduction": "I can help you find your claim ID.",
        "expose_to_user": True,
        "can_generate_task": True,
        "use_checkpointer": False,
    },
    # Add other agents as needed
}

# Build introduction string for router prompt
def get_agents_introduction() -> str:
    return "\n".join(
        f"- {name}: {config['introduction']}"
        for name, config in AGENT_ENDPOINTS.items()
        if config['expose_to_user']
    )
```

### New File: `src/agents/orchestrator/router.py`

Router node with LLM classification AND direct request support:

```python
from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import tools_condition
from .state import SupervisorState, AGENT_NAMES
from .agent_config import AGENT_ENDPOINTS, get_agents_introduction
from smart_investigator.foundation.tools.human_in_the_loop import HITL_AGENT_NAME
import logging

logger = logging.getLogger(__name__)

ROUTER_PROMPT_TEMPLATE = """You are an AI assistant specializing in routing insurance-related queries.
Your task is to determine whether the user's query falls into one of provided tools.

First, review the following context:
<context> {context} </context>

Now, consider the user's current query:
<user_query> {user_query} </user_query>

{prompt_last_messages}

The logic to determine the tool in the following order:
1) If the user_query is out of scope, call {hitl_name} to decline an answer.
2) If the context exists, prioritise calling the tool mentioned in the context if its description matches the intention of user_query.
3) If the user_query and the context matches partially, call {hitl_name} for follow-up clarification.
4) If other tools match the intention of user_query, call that tool.

You must return one single tool call only.

Available agents:
{agents}
"""

def create_router_node(llm: BaseChatModel, tools: list[StructuredTool]):
    """
    Creates a router node that handles:
    1. New conversations (welcome message)
    2. Direct requests (bypass LLM)
    3. Trusted resume (bypass LLM)
    4. LLM-based intent classification
    """

    async def router_node(state: SupervisorState) -> dict:
        messages = state.get("messages", [])
        context_stack = state.get("context_stack", [])
        is_direct = state.get("is_direct", False)
        target_agent = state.get("target_agent", "")
        trusted = state.get("trusted", False)

        # --- Case 1: New conversation ---
        if not messages:
            logger.info("New conversation - sending welcome message")
            return {
                "current_agent": "hitl",
                "is_direct": False,
                "trusted": False,
            }

        # --- Case 2: Direct request (bypass LLM) ---
        if is_direct and target_agent:
            if target_agent in AGENT_ENDPOINTS or target_agent == HITL_AGENT_NAME:
                logger.info(f"Direct request to {target_agent}")
                return {
                    "current_agent": target_agent,
                    "is_direct": False,  # Reset for next iteration
                }
            else:
                logger.warning(f"Invalid direct request target: {target_agent}")
                # Fall through to LLM classification

        # --- Case 3: Trusted resume (bypass LLM) ---
        if trusted and context_stack:
            last_context = context_stack[-1]
            logger.info(f"Trusted resume to {last_context.agent_name}")
            return {
                "current_agent": last_context.agent_name,
                "trusted": False,  # Reset for next iteration
            }

        # --- Case 4: LLM-based intent classification ---
        last_message = messages[-1]
        user_query = last_message.content if hasattr(last_message, 'content') else str(last_message)

        # Build context from stack
        context = ""
        if context_stack:
            last_context = context_stack[-1]
            context = last_context.context

        # Build prompt
        prompt = ROUTER_PROMPT_TEMPLATE.format(
            context=context,
            user_query=user_query,
            prompt_last_messages="",  # Can add previous messages if needed
            hitl_name=HITL_AGENT_NAME,
            agents=get_agents_introduction(),
        )

        logger.info(f"Router prompt:\n{prompt}")

        # Call LLM with tool binding
        llm_with_tools = llm.bind_tools(tools=tools)
        response = await llm_with_tools.ainvoke(prompt)

        # Check if LLM made a tool call
        if tools_condition(messages + [response]) == "tools":
            tool_call = response.tool_calls[0]
            agent_name = tool_call["name"]
            logger.info(f"LLM routed to: {agent_name}")
            return {"current_agent": agent_name}
        else:
            # LLM didn't make a tool call - ask for clarification
            logger.warning("LLM did not make a tool call - defaulting to HITL")
            return {"current_agent": "hitl"}

    return router_node


def route_to_agent(state: SupervisorState) -> str:
    """Conditional edge function - returns the agent name to route to."""
    return state.get("current_agent", "hitl")
```

### New File: `src/agents/orchestrator/agent_nodes.py`

Agent wrapper nodes with FULL functionality:

```python
from typing import Tuple, Optional
from copy import deepcopy
from langgraph.types import StreamWriter
from langgraph.config import get_stream_writer
from langgraph.runtime import Runtime, get_runtime
from langchain_core.messages import AIMessage
from databricks.sdk import WorkspaceClient
from mlflow.types.responses import ResponsesAgentStreamEvent
from .state import SupervisorState, ContextFrame
from .agent_config import AGENT_ENDPOINTS
from smart_investigator.foundation.utils.utils import prepare_thinking_message, is_retryable_exception, backoff_second
from smart_investigator.foundation.schemas.schemas import SIErrorCode, DoneType
import logging
import time
import uuid

logger = logging.getLogger(__name__)


def create_agent_node(agent_name: str, endpoint_config: dict):
    """
    Creates an agent node that:
    1. Streams thinking messages
    2. Calls Databricks endpoint with proper state
    3. Handles completion detection (is_interrupt flag)
    4. Manages context_stack for nested calls
    5. Preserves parent_state for resumption
    6. Passes artifacts between agents
    """

    client = WorkspaceClient().serving_endpoints.get_open_ai_client()

    async def agent_node(state: SupervisorState) -> dict:
        writer: StreamWriter = get_stream_writer()
        runtime: Runtime = get_runtime()
        request = deepcopy(runtime.context.get("request", {}))
        context_stack = deepcopy(state.get("context_stack", []))

        # --- Stream thinking message ---
        thinking_msg = prepare_thinking_message(
            agent_name=agent_name,
            text=f"Processing with {agent_name}..."
        )
        writer(thinking_msg)

        # --- Prepare input state for sub-agent ---
        # If this agent was previously interrupted, restore its state
        input_state = {}
        if context_stack:
            for frame in reversed(context_stack):
                if frame.agent_name == agent_name:
                    input_state = deepcopy(frame.parent_state)
                    break

        # Update request with state
        if not endpoint_config.get('use_checkpointer', False):
            request['custom_inputs']['state'] = input_state

        # --- Call endpoint with retry ---
        final_event, agent_state_out = await _call_endpoint_with_retry(
            client=client,
            endpoint_name=endpoint_config['endpoint_name'],
            request=request,
            writer=writer,
            agent_name=agent_name,
        )

        # --- Extract response data ---
        contents = final_event.item.content
        if not contents:
            raise Exception(f'[{agent_name}] Response content must not be empty!', SIErrorCode.INTERFACE_MISMATCH)

        content = contents[0]
        custom_outputs = content.custom_outputs or {}
        master_agent_context = custom_outputs.get('master_agent_context', {})

        # --- Completion Detection ---
        # This is the KEY logic that determines if agent is done
        is_interrupt = final_event.item.custom_outputs.get('is_interrupt', False)
        is_complete = not is_interrupt

        # Extract artifact from response
        response_artifact = custom_outputs.get('artifact', {})

        if is_complete:
            # --- Agent completed its task ---
            logger.info(f"{agent_name} completed task")

            if context_stack:
                # Return to parent agent
                parent_frame = context_stack[-1]
                logger.info(f"Returning to parent: {parent_frame.agent_name}")

                return {
                    "messages": [AIMessage(content=content.text)],
                    "current_agent": parent_frame.agent_name,
                    "context_stack": context_stack[:-1],  # Pop the frame
                    "current_artifact": response_artifact,
                    "is_direct": True,  # Direct return to parent
                    "target_agent": parent_frame.agent_name,
                    "trusted": True,  # Trust the return path
                }
            else:
                # No parent waiting - go to end or HITL for next task
                return {
                    "messages": [AIMessage(content=content.text)],
                    "current_agent": "hitl",  # Ask what to do next
                    "context_stack": [],
                    "current_artifact": response_artifact,
                    "is_direct": False,
                    "trusted": False,
                }

        else:
            # --- Agent needs more input (interrupted) ---
            logger.info(f"{agent_name} interrupted - needs more input")

            next_tool = master_agent_context.get('next_tool', {})
            next_agent = next_tool.get('name', 'hitl')
            context = master_agent_context.get('context', f"{agent_name} is requesting input")

            # Push current agent to stack so we can return to it
            new_frame = ContextFrame(
                agent_name=agent_name,
                context=context,
                parent_state=agent_state_out,  # Preserve state for resumption
                artifact=response_artifact,
                task_id=str(uuid.uuid4()),
            )

            return {
                "messages": [AIMessage(content=content.text)],
                "current_agent": next_agent,
                "context_stack": context_stack + [new_frame],  # Push frame
                "current_artifact": response_artifact,
                "is_direct": False,
                "trusted": False,
            }

    return agent_node


async def _call_endpoint_with_retry(
    client,
    endpoint_name: str,
    request: dict,
    writer: StreamWriter,
    agent_name: str,
    max_attempts: int = 3,
) -> Tuple[ResponsesAgentStreamEvent, dict]:
    """
    Calls Databricks endpoint with retry logic.

    Retry semantics:
    - Retry on transient errors if nothing streamed yet
    - Do NOT retry if already emitted events (would cause duplicates)
    """
    attempt = 0

    while attempt < max_attempts:
        attempt += 1
        received_any = False
        final_response = None
        state_out = ""

        try:
            stream = client.responses.create(
                model=endpoint_name,
                input=request.get("input", []),
                stream=True,
                extra_body={
                    "user": request.get("user", ""),
                    "custom_inputs": request.get("custom_inputs", {}),
                    "databricks_options": {"return_trace": True},
                },
            )

            for event in stream:
                received_any = True

                if event.type == 'response.output_text.delta':
                    # Stream LLM tokens
                    thinking_event = prepare_thinking_message(stream_event=event)
                    writer(thinking_event)

                elif event.type == 'response.output_item.done':
                    custom_outputs = event.item.custom_outputs
                    if not custom_outputs:
                        raise Exception(f"[{agent_name}] custom_outputs required!", SIErrorCode.INTERFACE_MISMATCH)

                    event_type = custom_outputs.get("event", "")
                    if event_type in (DoneType.llm, DoneType.thinking):
                        thinking_event = prepare_thinking_message(stream_event=event)
                        writer(thinking_event)
                    elif event_type == DoneType.response:
                        final_response = event
                    else:
                        raise Exception(f"[{agent_name}] Invalid event type: {event_type}", SIErrorCode.INTERFACE_MISMATCH)

                elif event.type == 'response.completed':
                    state_out = event.response.metadata.get('state', '')

                else:
                    logger.warning(f"[{agent_name}] Unsupported event type: {event.type}")

            if final_response:
                return final_response, state_out

            raise RuntimeError(f"[{agent_name}] Stream completed without final response")

        except Exception as exc:
            if not is_retryable_exception(exc) or received_any or attempt >= max_attempts:
                raise Exception(f"[{agent_name}] Endpoint error: {exc}", SIErrorCode.AGENT_ENDPOINT_FAILURE)

            sleep_seconds = backoff_second(attempt)
            logger.warning(f"[{agent_name}] Retrying after {sleep_seconds}s (attempt {attempt})")

            retry_msg = prepare_thinking_message(
                agent_name=agent_name,
                text=f"Retrying connection to {agent_name}..."
            )
            writer(retry_msg)
            time.sleep(sleep_seconds)

    raise RuntimeError(f"[{agent_name}] Max retries exceeded")
```

### New File: `src/agents/orchestrator/supervisor_graph.py`

Main graph with supervisor pattern:

```python
from langgraph.graph import StateGraph, START, END
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import StructuredTool
from .state import SupervisorState
from .router import create_router_node, route_to_agent
from .agent_nodes import create_agent_node
from .agent_config import AGENT_ENDPOINTS
from smart_investigator.foundation.tools.human_in_the_loop import hitl_node, HITL_AGENT_NAME


def create_supervisor_graph(llm: BaseChatModel, tools: list[StructuredTool]) -> StateGraph:
    """
    Creates the main supervisor graph.

    Architecture:
        START → router → [agent nodes / hitl] → router → ... → END

    The router decides which agent to call based on:
    1. is_direct flag (bypass LLM)
    2. trusted flag (bypass LLM on resume)
    3. LLM intent classification

    Agents can:
    - Complete and return to parent (pop context_stack)
    - Interrupt and call another agent (push context_stack)
    - Request HITL for user input
    """
    graph = StateGraph(SupervisorState)

    # --- Add router node ---
    graph.add_node("router", create_router_node(llm, tools))

    # --- Add agent nodes ---
    for name, config in AGENT_ENDPOINTS.items():
        graph.add_node(name, create_agent_node(name, config))

    # --- Add HITL node ---
    graph.add_node(HITL_AGENT_NAME, hitl_node)

    # --- Define edges ---
    graph.add_edge(START, "router")

    # Conditional routing from router to agents
    agent_routes = {name: name for name in AGENT_ENDPOINTS.keys()}
    agent_routes[HITL_AGENT_NAME] = HITL_AGENT_NAME
    agent_routes["end"] = END

    graph.add_conditional_edges("router", route_to_agent, agent_routes)

    # All agents return to router
    for name in AGENT_ENDPOINTS.keys():
        graph.add_edge(name, "router")
    graph.add_edge(HITL_AGENT_NAME, "router")

    return graph
```

---

## Phase 2: Migrate Agents (Days 5-7)

### Modify: `src/agents/orchestrator/master_agent.py`

Switch from tools to supervisor graph:

```python
# Before
from agents.orchestrator.master_agent_graph import get_master_agent_graph
from agents.orchestrator.tools_set import tools as agent_tools

class MasterAgentResponsesAgent(LanggraphResponsesAgent):
    def get_graph(self) -> StateGraph:
        return get_master_agent_graph(self.llm, tools=agent_tools + [human_in_the_loop])

# After
from agents.orchestrator.supervisor_graph import create_supervisor_graph
from agents.orchestrator.agent_config import AGENT_ENDPOINTS

class MasterAgentResponsesAgent(LanggraphResponsesAgent):
    def get_graph(self) -> StateGraph:
        # Build tools list for LLM binding (used by router for classification)
        tools = self._build_tools_for_router()
        return create_supervisor_graph(self.llm, tools)

    def _build_tools_for_router(self) -> list[StructuredTool]:
        """Build minimal tool definitions for LLM intent classification."""
        from langchain_core.tools import StructuredTool
        tools = []
        for name, config in AGENT_ENDPOINTS.items():
            tool = StructuredTool.from_function(
                func=lambda text, rationale: None,  # Dummy - never called
                name=name,
                description=config['description'],
            )
            tools.append(tool)
        return tools
```

### Modify: `src/smart_ investigator/foundation/tools/human_in_the_loop.py`

Convert to work as a node instead of a tool:

```python
from langgraph.types import interrupt
from langchain_core.messages import AIMessage
from mlflow.types.responses_helpers import Content
from smart_investigator.foundation.schemas.schemas import ContentCustomOutput, MasterAgentContext
from .tool_names import MASTER_AGENT_NAME
import json

HITL_AGENT_NAME = "human_in_the_loop"

WELCOME_PROMPT = """Welcome! I can help you with the following tasks:
{tasks}

What would you like to do?"""

REPEAT_PROMPT = """Is there anything else I can help you with?
{tasks}"""


async def hitl_node(state: SupervisorState) -> dict:
    """
    Human-in-the-loop node using LangGraph interrupt.

    This node:
    1. Prepares output to show the user
    2. Calls interrupt() to pause execution
    3. Returns with user's response when resumed
    """
    from agents.orchestrator.agent_config import get_agents_introduction

    messages = state.get("messages", [])
    context_stack = state.get("context_stack", [])

    # Determine what message to show
    if not messages:
        # Welcome message
        text = WELCOME_PROMPT.format(tasks=get_agents_introduction())
    elif not context_stack:
        # No pending tasks - ask what's next
        text = REPEAT_PROMPT.format(tasks=get_agents_introduction())
    else:
        # Agent requested input - use their message
        last_message = messages[-1]
        text = last_message.content if hasattr(last_message, 'content') else str(last_message)

    # Build interrupt payload
    interrupt_content = [
        Content(
            type='output_text',
            text=text,
            custom_outputs=ContentCustomOutput(
                sender=MASTER_AGENT_NAME,
                artifact={},
                master_agent_context=MasterAgentContext(
                    is_direct=False,
                    context="Waiting for user input",
                    next_tool=None,
                )
            )
        )
    ]

    # Interrupt and wait for user response
    user_response = interrupt(interrupt_content)

    # User has responded - extract their input
    user_text = user_response.text if hasattr(user_response, 'text') else str(user_response)
    user_custom_inputs = getattr(user_response, 'custom_inputs', {})

    # Check for direct request in user's response
    is_direct = user_custom_inputs.get('is_direct', False)
    target_agent = user_custom_inputs.get('agent_name', '')

    return {
        "messages": [AIMessage(content=user_text)],
        "current_agent": "",  # Router will decide
        "is_direct": is_direct,
        "target_agent": target_agent,
        "trusted": False,
    }
```

### Modify: `src/smart_ investigator/foundation/agents/response_agent.py`

Fix exception handling (replace bare `except:` clauses):

```python
# Before (lines 204, 218, 247, 255)
except:
    return []

# After
except Exception as e:
    logger.error(f"Error processing response: {e}")
    return []
```

---

## Phase 3: Update Streaming (Days 8-9)

### Event Compatibility Matrix

| Event | Current Source | New Source | Changes Needed |
|-------|---------------|------------|----------------|
| `ResponseTextDeltaEvent` | Tool streaming | Agent node streaming | Verify format |
| `ResponseOutputItemDoneEvent(thinking)` | `prepare_thinking_message` | Router node | Same format |
| `ResponseOutputItemDoneEvent(response)` | ToolMessage handling | Agent node response | Verify format |
| `ResponseCompletedEvent` | predict_stream | predict_stream | No change |

### Verify in `agent_nodes.py`

```python
# Ensure streaming events match frontend expectations
writer({
    "type": "response.output_text.delta",
    "delta": chunk_text,
    "item_id": item_id
})

# Ensure done events match
writer({
    "type": "response.output_item.done",
    "item": {
        "type": "message",
        "content": [...],
        "custom_outputs": {"event": "thinking", ...}
    }
})
```

### Test Streaming End-to-End

1. Start conversation - verify welcome message streams
2. Route to agent - verify thinking message appears
3. Agent responds - verify response streams correctly
4. HITL interrupt - verify interrupt event format
5. Resume - verify state preserved

---

## Phase 4: Cleanup (Days 10-11)

### Files to Delete

```
src/smart_ investigator/foundation/tools/tool_factory.py
src/smart_ investigator/foundation/tools/tool_set.py
src/smart_ investigator/foundation/tools/tool_set_utils.py
src/agents/orchestrator/tools_set.py
src/agents/orchestrator/master_agent_graph.py
```

### Simplify: `src/smart_ investigator/foundation/schemas/schemas.py`

Remove these schemas (no longer needed):
- `ToolMetadata`
- `ToolContentStruct`
- `ToolStruct`
- `ToolArgument`
- `TaskStruct`

Keep:
- `SupervisorState` (or move to state.py)
- `ContextFrame`
- Event types and error codes
- Frontend I/O types

### Simplify: `src/agents/orchestrator/master_agent_utils.py`

Remove:
- `_traceback_direct_request()`
- `format_task_struct()`
- Task stack management functions
- `IntentClassifierStruct`

Keep:
- HITL utility functions
- Message creation helpers
- Error handling utilities

### Delete Commented Code

Remove all commented-out code blocks across files. Git history preserves everything.

---

## Verification Checklist

### After Phase 1 (Day 4)
- [ ] All Python files compile without syntax errors
- [ ] New graph compiles: `python -c "from src.agents.orchestrator.supervisor_graph import create_supervisor_graph"`
- [ ] Router unit test passes with mock LLM
- [ ] Direct request test: `is_direct=True` bypasses LLM
- [ ] Trusted flag test: `trusted=True` bypasses LLM on resume

### After Phase 2 (Day 7)
- [ ] New conversation shows welcome message
- [ ] "craft a declined letter" routes to decline_letter agent
- [ ] HITL interrupt/resume works
- [ ] State preservation: agent state restored after nested call returns
- [ ] Artifact passing: artifacts flow between agents

### After Phase 3 (Day 9)
- [ ] Streaming events match before/after migration
- [ ] Frontend displays messages correctly

### After Phase 4 (Day 11)
- [ ] Full conversation flow works:
  ```
  User: I want to craft a declined letter
  → Routes to DeclineLetter
  User: Where to find a claim id?
  → Routes to SmartStrategy (nested call)
  → DeclineLetter state pushed to context_stack
  User: I am a partner
  → SmartStrategy completes
  → Pops context_stack, returns to DeclineLetter with restored state
  User: My id is 123ABH
  → DeclineLetter continues with previous state
  User: Motor
  → Letter generated, conversation ends
  ```
- [ ] Direct request test: Frontend sends `is_direct=True, agent_name="smart_strategy"` → routes directly
- [ ] Error handling test: Databricks timeout returns error message
- [ ] No deleted files are imported anywhere

---

## Summary

| Metric | Before | After |
|--------|--------|-------|
| Orchestration code | ~800 lines | ~400 lines |
| Number of schemas | 8+ tool-related | 3 simple models |
| Main routing function | 221 lines | ~50 lines |
| Files in orchestrator/ | 4 | 6 (but simpler) |

### What Changes for Frontend
**Likely no changes needed**, but verify:
- `custom_outputs.agent_name` - Still present
- `custom_outputs.master_agent_context` - Preserved
- `custom_inputs.is_direct` - Still supported
- `custom_inputs.agent_name` - Still supported
- Streaming events - Same types, same format

### What Stays the Same
- MLflow ResponseAgent integration
- Databricks endpoint calls
- HITL interrupt/resume pattern
- All 5 sub-agents (just called differently)
- `predict_stream()` interface
- Direct request functionality
- State preservation for nested calls
- Artifact passing between agents

### Risk Assessment
- **Medium risk** - Architecture change, but simpler result
- Nested calls handled via `context_stack` instead of `task_stack`
- Phase 3 has 2 days buffer for streaming format issues
- All existing functionality explicitly preserved

### Key Design Decisions Documented

1. **ContextFrame replaces TaskStruct** - Same fields, cleaner structure
2. **Router handles all routing logic** - Direct, trusted, and LLM-based
3. **Completion detected via `is_interrupt`** - Same as before
4. **State preserved in `parent_state`** - Same as before
5. **Artifacts flow via `artifact` field** - Same as before