"""
Agent Nodes

Wrapper nodes for each configured agent with streaming support.
Handles calling Databricks serving endpoints and processing responses.
"""

from typing import Optional, Any, Iterator, Callable
from copy import deepcopy
import json
import logging
import uuid
import traceback
import httpx
import backoff

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from mlflow.types.responses import ResponsesAgentStreamEvent
from mlflow.types.responses_helpers import Content

from databricks.sdk import WorkspaceClient

from supervisor_migration.state import SupervisorState, ContextFrame, WorkflowStatus
from supervisor_migration.agent_config import (
    AGENT_ENDPOINTS,
    AgentEndpointConfig,
    HITL_AGENT_NAME,
    SUPERVISOR_AGENT_NAME,
    get_workflow_agents,
)
from supervisor_migration.streaming_utils import (
    create_thinking_event,
    create_response_event,
    create_error_event,
    passthrough_stream_event,
)
from supervisor_migration.prompts import REPEAT_PROMPT

# Import existing schemas for compatibility
from smart_investigator.foundation.schemas.schemas import (
    EventType,
    DoneType,
    ContentCustomOutput,
    MasterAgentContext,
    ToolDict,
    SIErrorCode,
)

logger = logging.getLogger(__name__)


def _is_retryable_exception(e: Exception) -> bool:
    """Check if exception is retryable."""
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code in (429, 500, 502, 503, 504)
    if isinstance(e, httpx.RequestError):
        return True
    return False


def _call_databricks_endpoint(
    client: Any,
    endpoint_name: str,
    request_payload: dict,
    max_retries: int = 3,
) -> Iterator[ResponsesAgentStreamEvent]:
    """
    Call Databricks serving endpoint with retry logic.

    Args:
        client: Databricks OpenAI client
        endpoint_name: Name of the serving endpoint
        request_payload: Request payload to send
        max_retries: Maximum number of retries

    Yields:
        Stream events from the endpoint
    """

    def backoff_handler(details):
        logger.warning(
            f"Retry {details['tries']}/{max_retries} for {endpoint_name}: {details.get('exception', 'unknown')}"
        )

    @backoff.on_exception(
        backoff.expo,
        (httpx.RequestError, httpx.HTTPStatusError),
        giveup=lambda e: not _is_retryable_exception(e),
        max_tries=max_retries,
        jitter=backoff.full_jitter,
        on_backoff=backoff_handler,
    )
    def make_request():
        # Use Databricks SDK to call endpoint
        # This matches the pattern in tool_factory.py
        response = client.chat.completions.create(
            model=endpoint_name,
            messages=request_payload.get("messages", []),
            stream=True,
            **request_payload.get("extra_params", {}),
        )
        return response

    try:
        response = make_request()
        for chunk in response:
            yield chunk
    except Exception as e:
        logger.error(f"Error calling {endpoint_name}: {e}")
        raise


def _build_agent_request(
    state: SupervisorState,
    agent_name: str,
    config: AgentEndpointConfig,
) -> dict:
    """
    Build request payload for agent endpoint.

    Args:
        state: Current supervisor state
        agent_name: Name of the agent to call
        config: Agent configuration

    Returns:
        Request payload dict
    """
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None

    # Extract user query
    user_query = ""
    if last_message:
        if isinstance(last_message, HumanMessage):
            user_query = last_message.content
        elif isinstance(last_message, AIMessage):
            # Get from tool call arguments
            tool_calls = getattr(last_message, "tool_calls", [])
            if tool_calls:
                args = tool_calls[0].get("args", {})
                user_query = args.get("text", "")

    # Get context from stack
    context_stack = state.get("context_stack", [])
    parent_state = {}
    if context_stack:
        parent_frame = context_stack[-1]
        parent_state = parent_frame.parent_state

    # Build request in MLflow ResponsesAgent format
    request_payload = {
        "messages": [{"role": "user", "content": user_query}],
        "custom_inputs": {
            "frontend_input": {
                "text": user_query,
                "artifact": state.get("current_artifact", {}),
                "is_direct": state.get("is_direct", False),
                "agent_name": agent_name,
            },
            "state": parent_state,
            "is_resume": len(context_stack) > 0,
        },
    }

    return request_payload


def _process_agent_response(
    response_content: str,
    response_custom_outputs: dict,
    agent_name: str,
    state: SupervisorState,
) -> dict:
    """
    Process agent response and determine next steps.

    Args:
        response_content: Text content from agent
        response_custom_outputs: Custom outputs from agent
        agent_name: Name of the responding agent
        state: Current supervisor state

    Returns:
        State updates dict
    """
    context_stack: list[ContextFrame] = deepcopy(state.get("context_stack", []))
    workflow: WorkflowStatus = state.get("workflow", WorkflowStatus())

    # Check if response indicates task is complete
    need_resume = response_custom_outputs.get("is_interrupt", False)
    master_context = response_custom_outputs.get("master_agent_context", {})
    artifact = response_custom_outputs.get("artifact", {})

    # Pop context stack if returning to parent
    if context_stack and context_stack[-1].agent_name == agent_name:
        context_stack.pop()

    if not need_resume:
        # Task complete
        # Check if workflow is finished
        if workflow.name == agent_name:
            workflow = WorkflowStatus(name=workflow.name, is_finished=True)

        # Determine next agent
        if context_stack:
            # Return to parent agent
            parent_frame = context_stack[-1]
            return {
                "current_agent": parent_frame.agent_name,
                "context_stack": context_stack,
                "workflow": workflow,
                "current_artifact": artifact,
                "last_agent_response": response_content,
            }
        else:
            # No parent - go to HITL
            return {
                "current_agent": HITL_AGENT_NAME,
                "context_stack": context_stack,
                "workflow": workflow,
                "current_artifact": artifact,
                "last_agent_response": response_content,
            }
    else:
        # Task incomplete - needs more input
        context = master_context.get("context", f"{agent_name} was requesting: {response_content[:100]}")
        next_tool = master_context.get("next_tool", {})

        # Create new context frame
        new_frame = ContextFrame(
            agent_name=agent_name,
            context=context,
            parent_state=response_custom_outputs.get("state", {}),
            artifact=artifact,
            task_id=str(uuid.uuid4()),
        )
        context_stack.append(new_frame)

        # Determine next agent
        next_agent = HITL_AGENT_NAME
        if next_tool and next_tool.get("name"):
            next_agent = next_tool["name"]

        return {
            "current_agent": next_agent,
            "context_stack": context_stack,
            "current_artifact": artifact,
            "last_agent_response": response_content,
        }


def create_agent_node(
    agent_name: str,
    config: AgentEndpointConfig,
    get_client: Callable[[], Any],
) -> Callable[[SupervisorState], dict]:
    """
    Creates an agent node function for a specific agent.

    Args:
        agent_name: Name of the agent
        config: Agent endpoint configuration
        get_client: Function to get Databricks client

    Returns:
        Agent node function
    """

    def agent_node(state: SupervisorState) -> dict:
        """
        Calls the agent endpoint and processes response.

        Returns dict with state updates.
        """
        try:
            # Build request
            request_payload = _build_agent_request(state, agent_name, config)

            # Get client
            client = get_client()

            # Call endpoint
            endpoint_name = config["endpoint_name"]
            final_content = ""
            final_custom_outputs = {}

            logger.info(f"Calling agent {agent_name} at {endpoint_name}")

            for chunk in _call_databricks_endpoint(client, endpoint_name, request_payload):
                # Process streaming response
                # Accumulate final content
                if hasattr(chunk, "choices") and chunk.choices:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "content") and delta.content:
                        final_content += delta.content

            # Parse final response
            # The actual response format depends on the agent implementation
            # For now, assume the content is the response text
            final_custom_outputs = {
                "is_interrupt": False,
                "artifact": {},
                "master_agent_context": {},
            }

            return _process_agent_response(
                final_content,
                final_custom_outputs,
                agent_name,
                state,
            )

        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Error in agent {agent_name}: {e}\n{error_trace}")

            return {
                "current_agent": HITL_AGENT_NAME,
                "has_error": True,
                "error_message": f"Error in {agent_name}: {str(e)}",
                "last_agent_response": f"An error occurred while processing your request: {str(e)}",
            }

    return agent_node


def create_agent_nodes(
    get_client: Callable[[], Any],
) -> dict[str, Callable[[SupervisorState], dict]]:
    """
    Creates all agent nodes from configuration.

    Args:
        get_client: Function to get Databricks client

    Returns:
        Dict mapping agent names to node functions
    """
    nodes = {}
    for agent_name, config in AGENT_ENDPOINTS.items():
        nodes[agent_name] = create_agent_node(agent_name, config, get_client)
    return nodes
