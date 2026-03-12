"""
HITL Node

Human-in-the-loop as a graph node (not a tool).
This is a key difference from the current implementation - HITL becomes
a proper node in the graph rather than a tool that requires interrupt().
"""

from typing import Optional, Any
from copy import deepcopy
import json
import uuid
import logging

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import interrupt
from mlflow.types.responses_helpers import Content

from supervisor_migration.state import SupervisorState, ContextFrame
from supervisor_migration.agent_config import (
    HITL_AGENT_NAME,
    SUPERVISOR_AGENT_NAME,
    get_task_string,
)
from supervisor_migration.prompts import (
    WELCOME_PROMPT,
    REPEAT_PROMPT,
    IRRELEVANT_TOOL_RESPONSE,
)
from supervisor_migration.streaming_utils import create_hitl_content

# Import existing schemas for compatibility
from smart_investigator.foundation.schemas.schemas import (
    ContentCustomOutput,
    MasterAgentContext,
)

logger = logging.getLogger(__name__)


def hitl_node(state: SupervisorState) -> dict:
    """
    Human-in-the-loop node.

    This node:
    1. Prepares content to show to the user
    2. Calls interrupt() to pause execution
    3. When resumed, processes user input and returns to router

    The key insight: HITL is just another node in the graph, not a special tool.
    The interrupt mechanism handles the actual pause/resume.

    Args:
        state: Current supervisor state

    Returns:
        State updates dict (after resume from interrupt)
    """
    context_stack = state.get("context_stack", [])
    last_response = state.get("last_agent_response", "")
    has_error = state.get("has_error", False)
    error_message = state.get("error_message", "")

    # Determine what content to show user
    if has_error:
        # Show error message
        display_text = error_message or "An error occurred. Please try again."
    elif last_response:
        # Show last agent response
        display_text = last_response
    else:
        # Welcome or repeat prompt
        task_str = get_task_string()
        messages = state.get("messages", [])
        if not messages:
            display_text = WELCOME_PROMPT.format(tasks=task_str)
        else:
            display_text = REPEAT_PROMPT.format(tasks=task_str)

    # Build interrupt content
    # Get context for routing
    context = ""
    if context_stack:
        context = context_stack[-1].context

    interrupt_content = create_hitl_content(
        text=display_text,
        agent_name=SUPERVISOR_AGENT_NAME,
        artifact=state.get("current_artifact", {}),
        context=context,
    )

    logger.debug(f"HITL interrupt with content: {display_text[:100]}...")

    # Interrupt and wait for user input
    # The interrupt() call pauses the graph and returns control to the caller
    # When the graph is resumed with Command(resume=...), we get the user's input
    user_response: Content = interrupt(interrupt_content)

    # Process user response
    # The resumed content should be a Content object with user's input
    if isinstance(user_response, Content):
        user_text = user_response.text
        user_custom_inputs = getattr(user_response, "custom_inputs", {})
    elif isinstance(user_response, dict):
        user_text = user_response.get("text", "")
        user_custom_inputs = user_response.get("custom_inputs", {})
    else:
        user_text = str(user_response)
        user_custom_inputs = {}

    # Extract is_direct and target agent from user input
    is_direct = user_custom_inputs.get("is_direct", False)
    target_agent = user_custom_inputs.get("agent_name", "")

    # Create HumanMessage from user input
    human_message = HumanMessage(
        content=user_text,
        additional_kwargs={"custom_inputs": user_custom_inputs},
    )

    # Return state updates
    # The router will process the new human message
    return {
        "messages": [human_message],
        "is_direct": is_direct,
        "target_agent": target_agent,
        "has_error": False,
        "error_message": "",
        "last_agent_response": "",
    }


def create_hitl_node():
    """
    Factory function to create HITL node.
    Useful if we need to pass configuration in the future.

    Returns:
        The hitl_node function
    """
    return hitl_node
