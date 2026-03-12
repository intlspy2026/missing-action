"""
Supervisor Graph

Main graph assembly with workflow-aware routing.
This is the core of the supervisor pattern implementation.

Note: This implementation uses structured output for routing decisions,
not tool binding. The router uses llm.with_structured_output(RouterDecision)
to classify user intent - no tools needed.
"""

from typing import Optional, Callable, Any

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import StateGraph, START, END

from supervisor_migration.state import SupervisorState
from supervisor_migration.agent_config import (
    AGENT_ENDPOINTS,
    HITL_AGENT_NAME,
)
from supervisor_migration.router import create_router_node, route_to_agent
from supervisor_migration.agent_nodes import create_agent_node
from supervisor_migration.hitl_node import hitl_node


def create_supervisor_graph(
    llm: BaseChatModel,
    get_client: Callable[[], Any],
    max_last_messages: int = 1,
) -> StateGraph:
    """
    Creates supervisor graph with workflow-aware routing.

    Graph structure:
    ```
    START
      |
      v
    router ──────────────────────────┐
      |                              |
      ├─> decline_letter ─────────┐  |
      |                           |  |
      ├─> smart_strategy ─────────┤  |
      |                           |  |
      └─> hitl (interrupt) ───────┴──┘
                                     |
                                     v
                                   (loops back to router)
    ```

    All agents return to router for next routing decision.
    HITL uses interrupt() to pause for user input.

    Note: No tools parameter needed - uses structured output for classification.

    Args:
        llm: Language model for intent classification (uses with_structured_output)
        get_client: Function to get Databricks client for agent calls
        max_last_messages: Max previous human messages for context

    Returns:
        Configured StateGraph (not compiled)
    """
    # Create graph with SupervisorState
    graph = StateGraph(SupervisorState)

    # Create router node (no tools needed - uses structured output)
    router = create_router_node(llm, max_last_messages)

    # Add nodes
    graph.add_node("router", router)

    # Add agent nodes
    for agent_name, config in AGENT_ENDPOINTS.items():
        agent_node = create_agent_node(agent_name, config, get_client)
        graph.add_node(agent_name, agent_node)

    # Add HITL node
    graph.add_node(HITL_AGENT_NAME, hitl_node)

    # Add edges
    # START -> router
    graph.add_edge(START, "router")

    # Router -> conditional edges to agents
    route_map = {agent_name: agent_name for agent_name in AGENT_ENDPOINTS.keys()}
    route_map[HITL_AGENT_NAME] = HITL_AGENT_NAME

    graph.add_conditional_edges(
        "router",
        route_to_agent,
        route_map,
    )

    # All agents -> router (for next routing decision)
    for agent_name in AGENT_ENDPOINTS.keys():
        graph.add_edge(agent_name, "router")

    # HITL -> router (after user input is received)
    graph.add_edge(HITL_AGENT_NAME, "router")

    return graph


def create_supervisor_graph_with_end(
    llm: BaseChatModel,
    get_client: Callable[[], Any],
    max_last_messages: int = 1,
) -> StateGraph:
    """
    Creates supervisor graph with END node option.

    Similar to create_supervisor_graph but includes END as a routing option.
    Use this if you don't want infinite_loop behavior.

    Args:
        llm: Language model for intent classification
        get_client: Function to get Databricks client
        max_last_messages: Max previous human messages for context

    Returns:
        Configured StateGraph
    """
    graph = StateGraph(SupervisorState)

    router = create_router_node(llm, max_last_messages)

    graph.add_node("router", router)

    for agent_name, config in AGENT_ENDPOINTS.items():
        agent_node = create_agent_node(agent_name, config, get_client)
        graph.add_node(agent_name, agent_node)

    graph.add_node(HITL_AGENT_NAME, hitl_node)

    graph.add_edge(START, "router")

    def route_with_end(state: SupervisorState) -> str:
        """Route function that can return END."""
        current_agent = state.get("current_agent", "")
        context_stack = state.get("context_stack", [])

        if not current_agent and not context_stack:
            messages = state.get("messages", [])
            if len(messages) > 1:
                return END

        return route_to_agent(state)

    route_map = {agent_name: agent_name for agent_name in AGENT_ENDPOINTS.keys()}
    route_map[HITL_AGENT_NAME] = HITL_AGENT_NAME
    route_map[END] = END

    graph.add_conditional_edges(
        "router",
        route_with_end,
        route_map,
    )

    for agent_name in AGENT_ENDPOINTS.keys():
        graph.add_edge(agent_name, "router")

    graph.add_edge(HITL_AGENT_NAME, "router")

    return graph
