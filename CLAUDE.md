# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **Smart Investigator**, a multi-agent orchestration system built with LangGraph, MLFlow, and Databricks. It implements an intent-driven chatbot for insurance-related tasks using Azure OpenAI as the primary LLM.

## Architecture

### Core Components

**Master Agent Orchestrator** (`src/agents/orchestrator/`)
- `master_agent.py` - Main entry point, extends `LanggraphResponsesAgent`, registers with MLFlow
- `master_agent_graph.py` - LangGraph state machine: START → intent_classifier → tool_node → END
- `master_agent_utils.py` - Helper functions for HITL handling, message creation, intent classification
- `master_agent_prompts.py` - Centralized prompt templates (IC prompts, welcome/repeat, workflow rejection messages)
- `tools_set.py` - Constructs tools from YAML config files

**Foundation Layer** (`src/smart_ investigator/foundation/`)
- `agents/response_agent.py` - Base `LanggraphResponsesAgent` implementing MLFlow ResponseAgent interface with streaming support
- `schemas/schemas.py` - Pydantic data models (ToolStruct, TaskStruct, ToolContentStruct, MasterAgentState, etc.)
- `tools/tool_factory.py` - Dynamically creates tools from YAML configuration
- `tools/human_in_the_loop.py` - HITL tool for user input interrupts

### Execution Flow

1. User message → `predict_stream()` endpoint
2. Intent Classifier uses LLM with tool binding to route to appropriate tool
3. Tool executes (local agent or remote Databricks endpoint)
4. Tool output streams back with optional interrupts
5. Task stack maintains context for nested operations (tool A can call tool B)
6. Conversation loops until completion or HITL interrupt

### Key Data Models

- `MasterAgentState` - Extends MessagesState with `task_stack: List[TaskStruct]` and `workflow: WorkflowStatus`
- `WorkflowStatus` - Tracks active workflow with `{name: str, is_finished: bool}`
- `TaskStruct` - Contains parent_tool, parent_state, task_id, and ToolStruct
- `ToolStruct` - Contains context, content (Content), and tool_argument (ToolArgument)
- `ToolContentStruct` - Tool output with interrupt flag, state, next_tool, artifact
- `ToolMetadata` - expose_to_user, ic_introduction, can_generate_task, is_workflow

### Streaming Events

The system uses MLFlow ResponseAgent streaming with custom events:
- `ResponseTextDeltaEvent` - LLM token streaming
- `ResponseOutputItemDoneEvent` - Completed outputs (types: "llm", "thinking", "response")
- `ResponseCompletedEvent` - End of streaming session with state
- `ResponseErrorEvent` - Exception handling

## Key Frameworks

- **LangGraph** - Graph-based state machine orchestration
- **LangChain** - Tool abstractions and LLM integration
- **MLFlow** - Model serving via ResponseAgent interface
- **Databricks SDK** - Cloud serving endpoints
- **Azure OpenAI** - Primary LLM backend
- **Pydantic** - Data validation and serialization

## Tool Configuration

Tools are defined in YAML files in a `tools_config/` directory. Each tool config includes:
- `name`, `description`, `endpoint_name`
- `metadata` (expose_to_user, ic_introduction, can_generate_task)
- `text_annotation`, `rationale_annotation`
- `checkpointer` flag

## Development Notes

- All tools use `StandardToolArgument` with `text: str` and `rationale: str` parameters
- Tools communicate via free text (value field in ToolContentStruct)
- The `interrupt` flag indicates incomplete tasks requiring further assistance
- `can_generate_task=True` allows tools to add tasks to the task_stack
- All prompt templates are centralized in `master_agent_prompts.py`

## Important Patterns

- **Task Stack**: Nested tool calls maintain context via a stack of TaskStruct
- **Human-in-the-Loop**: Uses LangGraph `interrupt()` for user input, resumes with `Command(resume=...)`
- **Checkpointing**: Optional `StatelessMemorySaver` for resumable conversations
- **Tool Factory**: Creates StructuredTool instances with custom `@tool_with_metadata` decorator

## Workflow Management

Tools are classified into two categories based on `ToolMetadata.is_workflow`:
- **Workflow Agents**: Long-running, stateful workflows (e.g., claims processing)
- **Non-Workflow Agents**: Stateless, single-turn tools

### Workflow Rules
1. Only one workflow can be active at a time
2. Starting a new workflow while another is active triggers `REJECT_DIFFERENT_WORKFLOW`
3. Attempting to restart a finished workflow triggers `REJECT_FINISHED_WORKFLOW`
4. Non-workflow agents can be called anytime without restrictions

### Workflow State Tracking
The `workflow` field in `MasterAgentState` tracks:
- `name`: Currently active workflow agent name
- `is_finished`: Whether the workflow has completed

## User Input Paths

User input can arrive via two paths in the intent classifier:

### Path 1: ToolMessage (With Checkpoint/Resume)
- Graph interrupts at HITL tool and checkpoints state
- User responds via `Command(resume=...)`
- Input arrives as `ToolMessage(name="human_in_the_loop")`
- Handled at line 185 in `master_agent_graph.py`

### Path 2: HumanMessage (Direct Invocation)
- No checkpoint required, stateless operation
- User message added directly to `state.messages` as `HumanMessage`
- Handled at line 285 in `master_agent_graph.py`
- Supports `is_direct` flag for routing to specific agents

Both paths call `htil_handler()` for LLM-based intent classification.

## Helper Functions in master_agent_graph.py

- `_traceback_direct_request()` - Pops task stack to find matching agent for direct requests
- `_get_last_human_messages()` - Retrieves last N human messages for context
- `_extract_tool_name()` - Extracts tool name from AIMessage tool_calls
- `_form_htil_tool_call()` - Creates HITL tool call with pre-built text content
- `_process_tool_call_with_reject()` - Validates workflow rules and rejects invalid transitions

## HITL Tool Modes

The `human_in_the_loop` tool has two execution paths based on `output_args`:

### LLM-Initiated (output_args empty)
- LLM decides to call HITL for out-of-scope or clarification
- Uses `text` parameter (includes rationale per tool description)
- Triggered when query doesn't match available tools

### Code-Initiated (output_args provided)
- Code programmatically creates HITL call with pre-built content
- Uses `output_args` parameter, ignores `text`
- Used for welcome prompts, repeat prompts, agent output passthrough

## Prompt Templates

All prompts are centralized in `master_agent_prompts.py`:

### User-Facing Prompts
- `WELCOME_PROMPT` - Initial greeting with available tasks list
- `REPEAT_PROMPT` - Follow-up prompt after task completion

### Intent Classifier Prompts
- `IC_PROMPT_TEMPLATE_WITH_CONTEXT` - Used when task stack has context from previous tool
- `IC_PROMPT_TEMPLATE_WITHOUT_CONTEXT` - Used for fresh queries without prior context

Both IC prompts enforce:
- Professional, calm, business-oriented tone
- Concise responses (no vague/lengthy explanations)
- Second-person address ("you", not "the user")
- No emoticons
- Use "draft" instead of "denial"

### Workflow Rejection Messages
- `REJECT_FINISHED_WORKFLOW` - Shown when user tries to continue a completed workflow
- `REJECT_DIFFERENT_WORKFLOW` - Shown when user tries to start a new workflow while another is active
