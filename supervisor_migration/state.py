"""
State Models for Supervisor Pattern

Defines all state models with full workflow management support.
Replaces the complex tool-based state from master_agent_graph.py.

Note: LangGraph state classes use TypedDict, not Pydantic.
State is passed as a dict, but we define TypedDict for type hints.
"""

from __future__ import annotations
from typing import Annotated, Literal, Any, TypedDict, NotRequired
from pydantic import BaseModel, Field
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages


class WorkflowStatus(BaseModel):
    """
    Tracks active workflow state.

    Workflow Rules:
    - Only one workflow can be active at a time
    - Starting a new workflow while another is active triggers rejection
    - Attempting to restart a finished workflow triggers rejection
    - Non-workflow agents can be called anytime without restrictions
    """
    name: str = Field(default="", description="Currently active workflow agent name")
    is_finished: bool = Field(default=False, description="Whether workflow has completed")

    def is_active(self) -> bool:
        """Check if a workflow is currently active (started but not finished)."""
        return bool(self.name) and not self.is_finished

    def can_start_workflow(self, workflow_name: str) -> tuple[bool, str]:
        """
        Check if a new workflow can be started.

        Returns:
            Tuple of (can_start, rejection_reason)
        """
        if not self.name:
            # No active workflow, can start any
            return True, ""

        if self.name == workflow_name:
            if self.is_finished:
                return False, "FINISHED"
            else:
                # Continuing same workflow
                return True, ""
        else:
            # Different workflow while one is active
            return False, "DIFFERENT"


class ContextFrame(BaseModel):
    """
    Replaces TaskStruct - maintains context for nested agent calls.

    When Agent A calls Agent B, a ContextFrame is pushed onto the stack
    so that when Agent B completes, we can return to Agent A with proper context.
    """
    agent_name: str = Field(description="Name of parent agent waiting for response")
    context: str = Field(description="What the parent agent was asking for")
    parent_state: dict = Field(default_factory=dict, description="Serialized state to restore on return")
    artifact: dict = Field(default_factory=dict, description="Artifacts passed between agents")
    task_id: str = Field(default="", description="Unique identifier for this context frame")

    model_config = {"extra": "allow"}


class SupervisorState(MessagesState):
    """
    Main state for supervisor graph.

    Replaces MasterAgentState with same capabilities plus improved workflow management.
    Inherits MessagesState which provides: messages: Annotated[list, add_messages]

    Note: This is a TypedDict, so instances are plain dicts with type hints.
    Access state values using dict syntax: state.get("key") or state["key"]
    """
    # Core routing
    current_agent: str

    # Context stack for nested agent calls
    context_stack: list[ContextFrame]

    # Workflow management (matches current codebase behavior)
    workflow: WorkflowStatus

    # Direct request support (preserves is_direct functionality)
    is_direct: bool

    # Agent to route to when is_direct=True
    target_agent: str

    # Trust flag for HITL resume
    trusted: bool

    # Artifact passing between agents
    current_artifact: dict

    # Input path tracking (supports both ToolMessage and HumanMessage paths)
    input_path: Literal["tool", "human", ""]

    # Last agent response for context
    last_agent_response: str

    # Error tracking
    has_error: bool
    error_message: str

    # Collected inputs for agents that require upfront input collection
    collected_inputs: dict  # {agent_name: {field_name: value, ...}}

    # Flag indicating we're in input collection mode
    collecting_inputs_for: str  # Agent name we're collecting inputs for, or ""


# Type alias for state dict (used in function signatures)
SupervisorStateDict = dict[str, Any]


def create_initial_state(
    messages: list = None,
    current_agent: str = "",
    context_stack: list = None,
    workflow: WorkflowStatus = None,
    is_direct: bool = False,
    target_agent: str = "",
    trusted: bool = False,
    current_artifact: dict = None,
    input_path: str = "",
    last_agent_response: str = "",
    has_error: bool = False,
    error_message: str = "",
    collected_inputs: dict = None,
    collecting_inputs_for: str = "",
) -> SupervisorStateDict:
    """
    Create an initial SupervisorState dict with defaults.

    Since SupervisorState is a TypedDict, this helper provides
    a convenient way to create state with default values.
    """
    return {
        "messages": messages or [],
        "current_agent": current_agent,
        "context_stack": context_stack or [],
        "workflow": workflow or WorkflowStatus(),
        "is_direct": is_direct,
        "target_agent": target_agent,
        "trusted": trusted,
        "current_artifact": current_artifact or {},
        "input_path": input_path,
        "last_agent_response": last_agent_response,
        "has_error": has_error,
        "error_message": error_message,
        "collected_inputs": collected_inputs or {},
        "collecting_inputs_for": collecting_inputs_for,
    }


def get_workflow_from_state(state: SupervisorStateDict) -> WorkflowStatus:
    """Extract WorkflowStatus from state dict, handling both dict and object forms."""
    workflow = state.get("workflow")
    if workflow is None:
        return WorkflowStatus()
    if isinstance(workflow, dict):
        return WorkflowStatus(**workflow)
    return workflow


def get_context_stack_from_state(state: SupervisorStateDict) -> list[ContextFrame]:
    """Extract context_stack from state dict, handling both dict and object forms."""
    stack = state.get("context_stack", [])
    result = []
    for frame in stack:
        if isinstance(frame, dict):
            result.append(ContextFrame(**frame))
        else:
            result.append(frame)
    return result
