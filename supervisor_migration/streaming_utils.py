"""
Streaming Utilities

Streaming helpers maintaining exact frontend compatibility with current implementation.
Uses the same event format as smart_investigator.foundation.schemas.schemas.
"""

from typing import Optional, Any, Iterator, TYPE_CHECKING
import uuid

# Conditional imports for optional dependencies
try:
    from mlflow.types.responses import ResponsesAgentStreamEvent
    from mlflow.types.responses_helpers import OutputItem, Content, Response
    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False
    # Mock types for type hints when mlflow is not installed
    ResponsesAgentStreamEvent = Any
    OutputItem = Any
    Content = Any
    Response = Any

try:
    from smart_investigator.foundation.schemas.schemas import (
        EventType,
        DoneType,
        ContentCustomOutput,
        MasterAgentContext,
        ToolDict,
    )
    HAS_SI_SCHEMAS = True
except ImportError:
    HAS_SI_SCHEMAS = False
    # Fallback mock types
    from enum import Enum

    class EventType(str, Enum):
        delta_text = "response.output_text.delta"
        done = "response.output_item.done"
        completed = "response.completed"
        error = "error"

    class DoneType(str, Enum):
        thinking = "thinking"
        llm = "llm"
        response = "response"

    ContentCustomOutput = dict
    MasterAgentContext = dict
    ToolDict = dict

from supervisor_migration.agent_config import SUPERVISOR_AGENT_NAME


def create_thinking_event(
    text: str,
    agent_name: str = SUPERVISOR_AGENT_NAME,
) -> ResponsesAgentStreamEvent:
    """
    Creates thinking message event - SAME FORMAT as current implementation.
    Used for showing processing status to frontend.

    Args:
        text: The thinking message to display
        agent_name: Name of the agent sending the message

    Returns:
        ResponsesAgentStreamEvent with DoneType.thinking
    """
    return ResponsesAgentStreamEvent(
        type=EventType.done,
        item=OutputItem(
            type="message",
            id=str(uuid.uuid4()),
            content=[
                Content(
                    type="output_text",
                    text=text,
                    custom_outputs={
                        "sender": agent_name,
                    },
                )
            ],
            custom_outputs={
                "event": DoneType.thinking,
                "sender": agent_name,
            },
        ),
    )


def create_response_event(
    text: str,
    agent_name: str,
    is_interrupt: bool = False,
    artifact: Optional[dict] = None,
    master_agent_context: Optional[dict] = None,
) -> ResponsesAgentStreamEvent:
    """
    Creates final response event - SAME FORMAT as current implementation.

    Args:
        text: The response text
        agent_name: Name of the agent sending the response
        is_interrupt: Whether this response requires user input to continue
        artifact: Optional artifact data (forms, metrics, etc.)
        master_agent_context: Optional context for master agent routing

    Returns:
        ResponsesAgentStreamEvent with DoneType.response
    """
    content_custom_outputs = ContentCustomOutput(
        sender=agent_name,
        artifact=artifact or {},
        master_agent_context=master_agent_context or {},
    )

    return ResponsesAgentStreamEvent(
        type=EventType.done,
        item=OutputItem(
            type="message",
            id=str(uuid.uuid4()),
            content=[
                Content(
                    type="output_text",
                    text=text,
                    custom_outputs=content_custom_outputs,
                )
            ],
            custom_outputs={
                "event": DoneType.response,
                "is_interrupt": is_interrupt,
            },
        ),
    )


def create_llm_delta_event(
    text: str,
    agent_name: str,
) -> ResponsesAgentStreamEvent:
    """
    Creates LLM token streaming event.

    Args:
        text: The delta text chunk
        agent_name: Name of the agent generating the text

    Returns:
        ResponsesAgentStreamEvent for text delta
    """
    return ResponsesAgentStreamEvent(
        type=EventType.delta_text,
        delta=text,
        item_id=str(uuid.uuid4()),
        custom_outputs={
            "event": DoneType.llm,
            "sender": agent_name,
        },
    )


def create_error_event(
    error_message: str,
    error_code: str = "UNKNOWN_FAILURE",
    agent_name: str = SUPERVISOR_AGENT_NAME,
) -> ResponsesAgentStreamEvent:
    """
    Creates error event.

    Args:
        error_message: The error message
        error_code: Error code from SIErrorCode
        agent_name: Name of the agent where error occurred

    Returns:
        ResponsesAgentStreamEvent with error type
    """
    return ResponsesAgentStreamEvent(
        type=EventType.error,
        code=error_code,
        message=f"[{agent_name}] {error_message}",
    )


def create_completed_event(
    state: Optional[str] = None,
) -> ResponsesAgentStreamEvent:
    """
    Creates completion event with state for checkpointing.

    Args:
        state: Serialized state for checkpointing

    Returns:
        ResponsesAgentStreamEvent with completed type
    """
    return ResponsesAgentStreamEvent(
        type=EventType.completed,
        response=Response(
            output=[],
            metadata={"state": state or ""},
        ),
        status="completed",
    )


def passthrough_stream_event(
    stream_event: ResponsesAgentStreamEvent,
) -> ResponsesAgentStreamEvent:
    """
    Pass through a stream event from a child agent unchanged.
    Used when streaming events from nested agent calls.

    Args:
        stream_event: The event from child agent

    Returns:
        The same event (for type consistency)
    """
    return stream_event


def create_hitl_content(
    text: str,
    agent_name: str = SUPERVISOR_AGENT_NAME,
    artifact: Optional[dict] = None,
    context: str = "",
    next_tool: Optional[dict] = None,
) -> list[Content]:
    """
    Creates content list for HITL interrupt.

    Args:
        text: The text to show to user
        agent_name: Name of the agent
        artifact: Optional artifact data
        context: Context for next routing decision
        next_tool: Optional next tool specification

    Returns:
        List of Content objects for interrupt
    """
    master_context = MasterAgentContext(
        is_direct=False,
        context=context,
        next_tool=next_tool,
    ) if context or next_tool else {}

    return [
        Content(
            type="output_text",
            text=text,
            custom_outputs=ContentCustomOutput(
                sender=agent_name,
                artifact=artifact or {},
                master_agent_context=master_context,
            ),
        )
    ]


def wrap_agent_response_as_content(
    text: str,
    agent_name: str,
    artifact: Optional[dict] = None,
    is_interrupt: bool = False,
    context: str = "",
    next_tool_name: Optional[str] = None,
    next_tool_args: Optional[str] = None,
) -> list[Content]:
    """
    Wraps an agent response as Content list for further processing.

    Args:
        text: Response text
        agent_name: Name of responding agent
        artifact: Optional artifact data
        is_interrupt: Whether response is an interrupt
        context: Context for routing
        next_tool_name: Optional next tool to call
        next_tool_args: Optional arguments for next tool

    Returns:
        List of Content objects
    """
    next_tool = None
    if next_tool_name:
        next_tool = ToolDict(
            name=next_tool_name,
            arguments=next_tool_args or "",
        )

    master_context = MasterAgentContext(
        is_direct=False,
        context=context,
        next_tool=next_tool,
    )

    return [
        Content(
            type="output_text",
            text=text,
            custom_outputs=ContentCustomOutput(
                sender=agent_name,
                artifact=artifact or {},
                master_agent_context=master_context,
            ),
        )
    ]
