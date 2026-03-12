"""
Integration Tests

Full integration tests for supervisor pattern.
Tests the complete flow from request to response.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage

from supervisor_migration.state import (
    SupervisorState,
    WorkflowStatus,
    ContextFrame,
    create_initial_state,
)
from supervisor_migration.agent_config import AGENT_ENDPOINTS, HITL_AGENT_NAME

# Conditional import for graph tests (requires langgraph)
try:
    from supervisor_migration.supervisor_graph import create_supervisor_graph
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False
    create_supervisor_graph = None


@pytest.mark.skipif(not HAS_LANGGRAPH, reason="LangGraph not installed")
class TestGraphCreation:
    """Tests for graph creation."""

    def test_graph_has_all_nodes(self):
        """Graph should have router, all agent nodes, and HITL node."""
        mock_llm = Mock()
        mock_client = Mock()

        graph = create_supervisor_graph(
            llm=mock_llm,
            get_client=lambda: mock_client,
        )

        # Check nodes exist
        assert "router" in graph.nodes
        for agent_name in AGENT_ENDPOINTS.keys():
            assert agent_name in graph.nodes
        assert HITL_AGENT_NAME in graph.nodes

    def test_graph_compiles(self):
        """Graph should compile without errors."""
        mock_llm = Mock()
        mock_client = Mock()

        graph = create_supervisor_graph(
            llm=mock_llm,
            get_client=lambda: mock_client,
        )

        # Should compile without error
        compiled = graph.compile()
        assert compiled is not None


class TestStateTransitions:
    """Tests for state transitions through the graph."""

    def test_initial_state_to_welcome(self):
        """Empty messages should trigger welcome prompt."""
        from supervisor_migration.router import create_router_node

        mock_llm = Mock()

        router = create_router_node(mock_llm)

        state = create_initial_state(messages=[])
        result = router(state)

        assert result["current_agent"] == HITL_AGENT_NAME
        assert "last_agent_response" in result

    def test_direct_request_routes_correctly(self):
        """Direct request should route to specified agent."""
        from supervisor_migration.router import create_router_node

        mock_llm = Mock()

        router = create_router_node(mock_llm)

        state = create_initial_state(
            messages=[HumanMessage(content="Help me draft a letter")],
            is_direct=True,
            target_agent="decline_letter",
        )

        result = router(state)

        assert result["current_agent"] == "decline_letter"
        assert result["is_direct"] is False


class TestWorkflowManagement:
    """Tests for workflow management through the graph."""

    def test_workflow_starts_on_first_call(self):
        """Workflow should start when agent is first called."""
        from supervisor_migration.router import create_router_node

        mock_llm = Mock()

        router = create_router_node(mock_llm)

        state = create_initial_state(
            messages=[HumanMessage(content="Draft a decline letter")],
            is_direct=True,
            target_agent="decline_letter",
        )

        result = router(state)

        assert result["current_agent"] == "decline_letter"
        assert result["workflow"].name == "decline_letter"
        assert result["workflow"].is_finished is False

    def test_agent_with_required_inputs_triggers_collection(self):
        """Agent with required inputs should trigger input collection via HITL."""
        from supervisor_migration.router import create_router_node

        mock_llm = Mock()

        router = create_router_node(mock_llm)

        state = create_initial_state(
            messages=[HumanMessage(content="Find my claim")],
            is_direct=True,
            target_agent="smart_strategy",
        )

        result = router(state)

        # Should route to HITL to collect inputs first
        assert result["current_agent"] == "human_in_the_loop"
        assert result["collecting_inputs_for"] == "smart_strategy"
        assert "Claim ID" in result.get("last_agent_response", "")


class TestErrorHandling:
    """Tests for error handling in the graph."""

    def test_unknown_agent_routes_to_hitl(self):
        """Unknown agent in direct request should route to HITL."""
        from supervisor_migration.router import create_router_node

        mock_llm = Mock()

        router = create_router_node(mock_llm)

        state = create_initial_state(
            messages=[HumanMessage(content="Test")],
            is_direct=True,
            target_agent="nonexistent_agent",
        )

        result = router(state)

        assert result["current_agent"] == HITL_AGENT_NAME
        assert "Unknown agent" in result.get("last_agent_response", "")


class TestContextStack:
    """Tests for context stack management."""

    def test_context_preserved_on_stack(self):
        """Context should be preserved when pushed to stack."""
        frame = ContextFrame(
            agent_name="decline_letter",
            context="User wants to draft a decline letter for claim 123",
            parent_state={"claim_id": "123"},
            artifact={"draft": "Initial draft"},
        )

        state = create_initial_state(context_stack=[frame])

        assert len(state["context_stack"]) == 1
        assert state["context_stack"][0].agent_name == "decline_letter"
        assert state["context_stack"][0].context == "User wants to draft a decline letter for claim 123"

    def test_nested_contexts(self):
        """Multiple contexts should stack properly."""
        frame1 = ContextFrame(
            agent_name="decline_letter",
            context="First context",
        )
        frame2 = ContextFrame(
            agent_name="smart_strategy",
            context="Second context",
        )

        state = create_initial_state(context_stack=[frame1, frame2])

        assert len(state["context_stack"]) == 2
        # Most recent should be last
        assert state["context_stack"][-1].agent_name == "smart_strategy"
        assert state["context_stack"][-1].context == "Second context"


class TestStreamingEvents:
    """Tests for streaming event generation."""

    def test_thinking_event_format(self):
        """Thinking events should have correct format."""
        from supervisor_migration.streaming_utils import (
            create_thinking_event,
            HAS_MLFLOW,
            EventType,
            DoneType,
        )

        if not HAS_MLFLOW:
            pytest.skip("MLflow not installed")

        event = create_thinking_event("Processing your request...")

        assert event.type == EventType.done
        assert event.item is not None
        assert event.item.custom_outputs["event"] == DoneType.thinking

    def test_response_event_format(self):
        """Response events should have correct format."""
        from supervisor_migration.streaming_utils import (
            create_response_event,
            HAS_MLFLOW,
            EventType,
            DoneType,
        )

        if not HAS_MLFLOW:
            pytest.skip("MLflow not installed")

        event = create_response_event(
            text="Here is your response",
            agent_name="decline_letter",
            is_interrupt=False,
        )

        assert event.type == EventType.done
        assert event.item is not None
        assert event.item.custom_outputs["event"] == DoneType.response
        assert event.item.custom_outputs["is_interrupt"] is False

    def test_interrupt_response_event_format(self):
        """Interrupt response events should have correct format."""
        from supervisor_migration.streaming_utils import (
            create_response_event,
            HAS_MLFLOW,
            EventType,
            DoneType,
        )

        if not HAS_MLFLOW:
            pytest.skip("MLflow not installed")

        event = create_response_event(
            text="Please provide more information",
            agent_name="decline_letter",
            is_interrupt=True,
        )

        assert event.type == EventType.done
        assert event.item.custom_outputs["is_interrupt"] is True
