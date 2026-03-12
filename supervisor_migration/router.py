"""
Router Node

Router with workflow management and both input paths (ToolMessage and HumanMessage).
Uses structured output for intent classification instead of tool binding.
"""

from typing import Optional, Any, List, Literal, Union
from copy import deepcopy
import logging
import httpx
import backoff
from enum import Enum

from pydantic import BaseModel, Field
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage

from supervisor_migration.state import SupervisorState, ContextFrame, WorkflowStatus
from supervisor_migration.prompts import (
    WELCOME_PROMPT,
    REPEAT_PROMPT,
    REJECT_FINISHED_WORKFLOW,
    LLM_NO_TOOL_CALL_RESPONSE,
)
from supervisor_migration.agent_config import (
    AGENT_ENDPOINTS,
    HITL_AGENT_NAME,
    SUPERVISOR_AGENT_NAME,
    get_workflow_agents,
    get_non_workflow_agents,
    get_task_string,
    get_required_inputs,
    get_missing_inputs,
    format_input_collection_prompt,
    get_agents_description_string,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Router Decision Model (Structured Output)
# =============================================================================

def get_agent_literal_type():
    """Dynamically create Literal type from available agents."""
    agent_names = list(AGENT_ENDPOINTS.keys()) + [HITL_AGENT_NAME]
    return Literal[tuple(agent_names)]


class RouterDecision(BaseModel):
    """
    LLM's routing decision.

    This replaces tool binding with structured output for cleaner semantics.
    The LLM decides which agent should handle the request.
    """
    agent: str = Field(
        description="The agent to route to. Must be one of the available agents."
    )
    rationale: str = Field(
        description="Brief, friendly explanation of why this agent is appropriate. "
                    "Address the user as 'you'. Use 'Drafting' not 'Crafting'."
    )
    extracted_input: str = Field(
        description="The key information or intent extracted from user's message"
    )

    def validate_agent(self, valid_agents: list[str]) -> bool:
        """Check if agent is valid."""
        return self.agent in valid_agents


# =============================================================================
# Router Prompt
# =============================================================================

ROUTER_CLASSIFICATION_PROMPT = """You are a friendly and professional AI assistant specializing in routing insurance-related queries.
Your role is to determine which agent should handle the user's request.

IMPORTANT: Always refer to the person as 'you', never as 'the user'.
IMPORTANT: Use 'Drafting' instead of 'Crafting' when referring to creating documents.

## Available Agents
{agent_descriptions}

## Context
{context}

## User Query
{user_query}

{previous_messages}

## Routing Rules (in order of priority)
1. If the query is OUT OF SCOPE (legal liability, payments, refunds, car policies, etc.), route to `human_in_the_loop` to decline.
2. If context exists and mentions an agent, prefer that agent if the query matches its description.
3. If the query partially matches context, route to `human_in_the_loop` for clarification.
4. Otherwise, route to the agent whose description best matches the query.

Choose the most appropriate agent and explain your reasoning.
"""


def _build_classification_prompt(
    user_query: str,
    context: str,
    last_messages: list[str],
) -> str:
    """Build the classification prompt."""
    agent_descriptions = get_agents_description_string()

    previous_messages = ""
    if last_messages:
        joined = "\n- ".join(last_messages)
        previous_messages = f"## Previous Messages (for reference)\n- {joined}"

    return ROUTER_CLASSIFICATION_PROMPT.format(
        agent_descriptions=agent_descriptions,
        context=context or "No prior context.",
        user_query=user_query,
        previous_messages=previous_messages,
    )


# =============================================================================
# Helper Functions
# =============================================================================

def _get_last_human_messages(messages: list[BaseMessage], max_count: int = 1) -> list[str]:
    """Extract last N human message contents for context."""
    count = 0
    last_messages = []
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_messages.append(msg.content)
            count += 1
        if count >= max_count:
            break
    return last_messages


def _check_required_inputs(
    agent_name: str,
    state: SupervisorState,
) -> tuple[bool, Optional[str], dict]:
    """
    Check if agent has required inputs and if they're all provided.

    Returns:
        Tuple of (all_provided, collection_prompt, updated_collected_inputs)
    """
    required = get_required_inputs(agent_name)
    if not required:
        return True, None, {}

    collected_inputs = state.get("collected_inputs", {})
    agent_inputs = collected_inputs.get(agent_name, {})
    missing = get_missing_inputs(agent_name, agent_inputs)

    if not missing:
        return True, None, {}

    prompt = format_input_collection_prompt(agent_name, missing)
    return False, prompt, {"collecting_inputs_for": agent_name}


def _parse_user_inputs(
    user_message: str,
    agent_name: str,
    state: SupervisorState,
) -> dict:
    """
    Parse user message to extract input values.
    """
    collected_inputs = dict(state.get("collected_inputs", {}))
    agent_inputs = dict(collected_inputs.get(agent_name, {}))
    required = get_required_inputs(agent_name)

    missing = get_missing_inputs(agent_name, agent_inputs)

    if len(missing) == 1:
        agent_inputs[missing[0].name] = user_message.strip()
    else:
        lines = user_message.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            for sep in [":", "=", "-"]:
                if sep in line:
                    parts = line.split(sep, 1)
                    if len(parts) == 2:
                        key = parts[0].strip().lower().replace(" ", "_")
                        value = parts[1].strip()

                        for req in required:
                            if (key == req.name.lower() or
                                key == req.display_name.lower().replace(" ", "_") or
                                req.display_name.lower() in key):
                                agent_inputs[req.name] = value
                                break
                    break

    collected_inputs[agent_name] = agent_inputs
    return collected_inputs


def _get_context_from_stack(context_stack: list[ContextFrame]) -> str:
    """Get context string from the top of the context stack."""
    if context_stack:
        return context_stack[-1].context
    return ""


def _process_workflow_rejection(
    agent_name: str,
    workflow: WorkflowStatus,
    workflow_agents: list[str],
    non_workflow_agents: list[str],
) -> Optional[str]:
    """
    Validates workflow rules and returns rejection message if violated.

    Rules:
    - Cannot restart a FINISHED workflow (must start new conversation)
    - CAN switch between workflows mid-conversation
    """
    if agent_name not in workflow_agents:
        return None

    if not workflow.name:
        return None

    if workflow.name == agent_name:
        if workflow.is_finished:
            return REJECT_FINISHED_WORKFLOW.format(workflow_name=workflow.name)
        return None
    else:
        # Different workflow - ALLOWED (can switch mid-conversation)
        return None


# =============================================================================
# LLM Classification
# =============================================================================

def _classify_with_llm(
    llm: BaseChatModel,
    prompt: str,
    valid_agents: list[str],
    max_retries: int = 3,
) -> Optional[RouterDecision]:
    """
    Use LLM with structured output to classify user intent.

    Returns RouterDecision or None if classification fails.
    """

    def is_retryable(e: Exception) -> bool:
        if isinstance(e, (httpx.RequestError, httpx.HTTPStatusError)):
            return True
        return False

    def backoff_handler(details):
        logger.warning(
            f"Backing off {details['wait']:.1f}s after {details['tries']} tries"
        )

    @backoff.on_exception(
        backoff.expo,
        (httpx.RequestError, httpx.HTTPStatusError, Exception),
        giveup=lambda e: not is_retryable(e),
        max_tries=max_retries,
        jitter=backoff.full_jitter,
        on_backoff=backoff_handler,
    )
    def invoke():
        structured_llm = llm.with_structured_output(RouterDecision)
        return structured_llm.invoke(prompt)

    try:
        decision = invoke()

        # Validate agent name
        if decision and decision.agent in valid_agents:
            return decision
        elif decision:
            logger.warning(f"Invalid agent '{decision.agent}', defaulting to HITL")
            return RouterDecision(
                agent=HITL_AGENT_NAME,
                rationale="I need clarification on your request.",
                extracted_input=decision.extracted_input if decision else "",
            )
        return None
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        return None


# =============================================================================
# Router Node Factory
# =============================================================================

def create_router_node(
    llm: BaseChatModel,
    max_last_messages: int = 1,
):
    """
    Creates the router node function.

    The router handles:
    1. New conversation -> HITL with welcome
    2. Input collection mode -> Parse and continue
    3. Direct request (is_direct=True) -> Target agent
    4. Trusted resume -> Parent agent from context_stack
    5. LLM classification -> Selected agent
    6. Workflow validation -> Reject if rules violated
    7. Input validation -> Collect if required

    Args:
        llm: Language model for intent classification
        max_last_messages: Max number of previous human messages to include

    Returns:
        Router node function
    """
    workflow_agents = get_workflow_agents()
    non_workflow_agents = get_non_workflow_agents()
    valid_agents = list(AGENT_ENDPOINTS.keys()) + [HITL_AGENT_NAME]
    task_str = get_task_string()

    def router_node(state: SupervisorState) -> dict:
        """
        Routes to appropriate agent based on state and user input.
        """
        messages = state.get("messages", [])
        context_stack: list[ContextFrame] = deepcopy(state.get("context_stack", []))
        workflow: WorkflowStatus = state.get("workflow", WorkflowStatus())

        # Case 1: New conversation - welcome prompt
        if not messages:
            welcome_text = WELCOME_PROMPT.format(tasks=task_str)
            return {
                "current_agent": HITL_AGENT_NAME,
                "last_agent_response": welcome_text,
                "context_stack": [],
                "collected_inputs": {},
                "collecting_inputs_for": "",
            }

        # Get last message
        last_message = messages[-1]

        # Extract user query
        if isinstance(last_message, HumanMessage):
            user_query = last_message.content
            input_path = "human"
        else:
            user_query = getattr(last_message, "content", "")
            input_path = "tool"

        # Case 2: Input collection mode
        collecting_for = state.get("collecting_inputs_for", "")
        if collecting_for:
            updated_inputs = _parse_user_inputs(user_query, collecting_for, state)
            all_provided, collection_prompt, _ = _check_required_inputs(
                collecting_for,
                {"collected_inputs": updated_inputs},
            )

            if all_provided:
                new_workflow = workflow
                if collecting_for in workflow_agents and workflow.name != collecting_for:
                    new_workflow = WorkflowStatus(name=collecting_for, is_finished=False)

                return {
                    "current_agent": collecting_for,
                    "collected_inputs": updated_inputs,
                    "collecting_inputs_for": "",
                    "workflow": new_workflow,
                    "input_path": input_path,
                }
            else:
                return {
                    "current_agent": HITL_AGENT_NAME,
                    "last_agent_response": collection_prompt,
                    "collected_inputs": updated_inputs,
                    "collecting_inputs_for": collecting_for,
                    "input_path": input_path,
                }

        # Case 3: Direct request - bypass LLM
        is_direct = state.get("is_direct", False)
        target_agent = state.get("target_agent", "")

        if is_direct and target_agent:
            if target_agent in valid_agents:
                rejection = _process_workflow_rejection(
                    target_agent, workflow, workflow_agents, non_workflow_agents
                )
                if rejection:
                    return {
                        "current_agent": HITL_AGENT_NAME,
                        "last_agent_response": rejection,
                        "is_direct": False,
                        "target_agent": "",
                    }

                all_provided, collection_prompt, _ = _check_required_inputs(
                    target_agent, state
                )
                if not all_provided:
                    return {
                        "current_agent": HITL_AGENT_NAME,
                        "last_agent_response": collection_prompt,
                        "collecting_inputs_for": target_agent,
                        "is_direct": False,
                        "target_agent": "",
                        "input_path": input_path,
                    }

                new_workflow = workflow
                if target_agent in workflow_agents and workflow.name != target_agent:
                    new_workflow = WorkflowStatus(name=target_agent, is_finished=False)

                return {
                    "current_agent": target_agent,
                    "workflow": new_workflow,
                    "is_direct": False,
                    "target_agent": "",
                    "input_path": input_path,
                }
            else:
                return {
                    "current_agent": HITL_AGENT_NAME,
                    "last_agent_response": f"Unknown agent: {target_agent}",
                    "is_direct": False,
                    "target_agent": "",
                }

        # Case 4: Trusted resume - use context stack
        trusted = state.get("trusted", False)
        if trusted and context_stack:
            parent_frame = context_stack[-1]
            return {
                "current_agent": parent_frame.agent_name,
                "trusted": False,
                "input_path": input_path,
            }

        # Case 5: LLM classification with structured output
        context = _get_context_from_stack(context_stack)
        last_msgs = _get_last_human_messages(messages, max_last_messages)

        prompt = _build_classification_prompt(
            user_query=user_query,
            context=context,
            last_messages=last_msgs,
        )

        logger.debug(f"Classification prompt:\n{prompt}")

        decision = _classify_with_llm(llm, prompt, valid_agents)

        if decision:
            agent_name = decision.agent

            # Case 6: Workflow validation
            rejection = _process_workflow_rejection(
                agent_name, workflow, workflow_agents, non_workflow_agents
            )
            if rejection:
                return {
                    "current_agent": HITL_AGENT_NAME,
                    "last_agent_response": rejection,
                    "input_path": input_path,
                }

            # Case 7: Input validation
            all_provided, collection_prompt, _ = _check_required_inputs(
                agent_name, state
            )
            if not all_provided:
                return {
                    "current_agent": HITL_AGENT_NAME,
                    "last_agent_response": collection_prompt,
                    "collecting_inputs_for": agent_name,
                    "input_path": input_path,
                }

            # Update workflow if needed
            new_workflow = workflow
            if agent_name in workflow_agents and workflow.name != agent_name:
                new_workflow = WorkflowStatus(name=agent_name, is_finished=False)

            return {
                "current_agent": agent_name,
                "workflow": new_workflow,
                "input_path": input_path,
                "last_agent_response": decision.rationale,
            }

        # Classification failed - ask for clarification
        return {
            "current_agent": HITL_AGENT_NAME,
            "last_agent_response": LLM_NO_TOOL_CALL_RESPONSE,
            "input_path": input_path,
        }

    return router_node


# =============================================================================
# Routing Edge Function
# =============================================================================

def route_to_agent(state: SupervisorState) -> str:
    """
    Conditional edge function to route to the appropriate agent node.
    """
    current_agent = state.get("current_agent", "")

    if not current_agent:
        return HITL_AGENT_NAME

    if current_agent in AGENT_ENDPOINTS:
        return current_agent

    if current_agent == HITL_AGENT_NAME:
        return HITL_AGENT_NAME

    logger.warning(f"Unknown agent '{current_agent}', routing to HITL")
    return HITL_AGENT_NAME
