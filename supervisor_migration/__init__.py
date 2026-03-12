"""
Supervisor Migration Package

Native LangGraph supervisor pattern implementation for Smart Investigator.


Key Components:
- SupervisorState: Main state with workflow management
- Router: Intent classification with workflow validation
- Agent Nodes: Wrapper nodes for each configured agent
- HITL Node: Human-in-the-loop as a graph node (not tool)
- Streaming Utils: MLFlow-compatible streaming events

Usage:
    from supervisor_migration import (
        SupervisorState,
        WorkflowStatus,
        ContextFrame,
        AGENT_ENDPOINTS,
        get_workflow_agents,
        get_non_workflow_agents,
    )

    # For full graph creation (requires all dependencies):
    from supervisor_migration.supervisor_graph import create_supervisor_graph
    from supervisor_migration.supervisor_agent import SupervisorAgent
"""

# Core state models (no external dependencies)
from supervisor_migration.state import (
    SupervisorState,
    ContextFrame,
    WorkflowStatus,
    create_initial_state,
    get_workflow_from_state,
    get_context_stack_from_state,
)

# Agent configuration (no external dependencies)
from supervisor_migration.agent_config import (
    AGENT_ENDPOINTS,
    AgentEndpointConfig,
    get_workflow_agents,
    get_non_workflow_agents,
    get_agents_introduction,
    HITL_AGENT_NAME,
    SUPERVISOR_AGENT_NAME,
)

# Prompts (no external dependencies)
from supervisor_migration.prompts import (
    WELCOME_PROMPT,
    REPEAT_PROMPT,
    REJECT_FINISHED_WORKFLOW,
    ROUTER_PROMPT_TEMPLATE,
)

# Agent config helpers for input collection
from supervisor_migration.agent_config import (
    get_required_inputs,
    get_missing_inputs,
    format_input_collection_prompt,
)

# Note: The following require external dependencies (langchain, langgraph, mlflow, etc.)
# They are imported lazily to avoid import errors when dependencies are not installed.
# Use: from supervisor_migration.supervisor_graph import create_supervisor_graph
# Use: from supervisor_migration.supervisor_agent import SupervisorAgent

__all__ = [
    # State
    "SupervisorState",
    "ContextFrame",
    "WorkflowStatus",
    "create_initial_state",
    # Config
    "AGENT_ENDPOINTS",
    "AgentEndpointConfig",
    "get_workflow_agents",
    "get_non_workflow_agents",
    "get_agents_introduction",
    "get_required_inputs",
    "get_missing_inputs",
    "format_input_collection_prompt",
    "HITL_AGENT_NAME",
    "SUPERVISOR_AGENT_NAME",
    # Prompts
    "WELCOME_PROMPT",
    "REPEAT_PROMPT",
    "REJECT_FINISHED_WORKFLOW",
    "ROUTER_PROMPT_TEMPLATE",
]
