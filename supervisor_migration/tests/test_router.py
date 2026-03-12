"""
Router Tests

Tests for router node and workflow validation logic.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage

from supervisor_migration.state import (
    SupervisorState,
    WorkflowStatus,
    ContextFrame,
    create_initial_state,
)
from supervisor_migration.router import (
    create_router_node,
    route_to_agent,
    _process_workflow_rejection,
    _get_last_human_messages,
    _get_context_from_stack,
    _check_required_inputs,
    _parse_user_inputs,
)
from supervisor_migration.agent_config import (
    HITL_AGENT_NAME,
    get_workflow_agents,
    get_non_workflow_agents,
    get_required_inputs,
)


class TestInputCollection:
    """Tests for input collection functionality."""

    def test_smart_strategy_requires_inputs(self):
        """smart_strategy should have required inputs defined."""
        required = get_required_inputs("smart_strategy")
        assert len(required) == 4
        field_names = [r.name for r in required]
        assert "claim_id" in field_names
        assert "policy_number" in field_names
        assert "date_range" in field_names
        assert "customer_name" in field_names

    def test_decline_letter_no_required_inputs(self):
        """decline_letter should not have required inputs."""
        required = get_required_inputs("decline_letter")
        assert len(required) == 0

    def test_check_required_inputs_missing(self):
        """Should detect missing inputs."""
        state = create_initial_state(collected_inputs={})
        all_provided, prompt, _ = _check_required_inputs("smart_strategy", state)

        assert all_provided is False
        assert prompt is not None
        assert "Claim ID" in prompt
        assert "Policy Number" in prompt

    def test_check_required_inputs_partial(self):
        """Should detect partially provided inputs."""
        state = create_initial_state(
            collected_inputs={
                "smart_strategy": {
                    "claim_id": "CLM-123",
                    "policy_number": "POL-456",
                }
            }
        )
        all_provided, prompt, _ = _check_required_inputs("smart_strategy", state)

        assert all_provided is False
        assert prompt is not None
        assert "Date Range" in prompt
        assert "Customer Name" in prompt
        # Already provided fields should not be in prompt
        assert "Claim ID" not in prompt

    def test_check_required_inputs_all_provided(self):
        """Should pass when all inputs provided."""
        state = create_initial_state(
            collected_inputs={
                "smart_strategy": {
                    "claim_id": "CLM-123",
                    "policy_number": "POL-456",
                    "date_range": "2024-01-01 to 2024-12-31",
                    "customer_name": "John Smith",
                }
            }
        )
        all_provided, prompt, _ = _check_required_inputs("smart_strategy", state)

        assert all_provided is True
        assert prompt is None

    def test_parse_user_inputs_single_value(self):
        """Should parse single value when one input missing."""
        state = create_initial_state(
            collected_inputs={
                "smart_strategy": {
                    "claim_id": "CLM-123",
                    "policy_number": "POL-456",
                    "date_range": "2024-01-01 to 2024-12-31",
                    # customer_name missing
                }
            }
        )
        result = _parse_user_inputs("John Smith", "smart_strategy", state)

        assert result["smart_strategy"]["customer_name"] == "John Smith"

    def test_parse_user_inputs_key_value_format(self):
        """Should parse key-value pairs."""
        state = create_initial_state(collected_inputs={})
        user_input = """Claim ID: CLM-123
Policy Number: POL-456
Date Range: 2024-01-01 to 2024-12-31
Customer Name: John Smith"""

        result = _parse_user_inputs(user_input, "smart_strategy", state)

        assert result["smart_strategy"]["claim_id"] == "CLM-123"
        assert result["smart_strategy"]["policy_number"] == "POL-456"


class TestWorkflowRejection:
    """Tests for _process_workflow_rejection function."""

    def test_non_workflow_agent_always_allowed(self):
        """Non-workflow agents should always be allowed."""
        workflow = WorkflowStatus(name="decline_letter", is_finished=False)
        workflow_agents = ["decline_letter"]
        non_workflow_agents = ["smart_strategy"]

        result = _process_workflow_rejection(
            agent_name="smart_strategy",
            workflow=workflow,
            workflow_agents=workflow_agents,
            non_workflow_agents=non_workflow_agents,
        )

        assert result is None  # No rejection

    def test_no_active_workflow_allows_new(self):
        """Starting a workflow when none is active should be allowed."""
        workflow = WorkflowStatus()  # Empty workflow
        workflow_agents = ["decline_letter"]
        non_workflow_agents = ["smart_strategy"]

        result = _process_workflow_rejection(
            agent_name="decline_letter",
            workflow=workflow,
            workflow_agents=workflow_agents,
            non_workflow_agents=non_workflow_agents,
        )

        assert result is None  # No rejection

    def test_same_workflow_not_finished_allowed(self):
        """Continuing same workflow that's not finished should be allowed."""
        workflow = WorkflowStatus(name="decline_letter", is_finished=False)
        workflow_agents = ["decline_letter"]
        non_workflow_agents = ["smart_strategy"]

        result = _process_workflow_rejection(
            agent_name="decline_letter",
            workflow=workflow,
            workflow_agents=workflow_agents,
            non_workflow_agents=non_workflow_agents,
        )

        assert result is None  # No rejection

    def test_same_workflow_finished_rejected(self):
        """Trying to restart a finished workflow should be rejected."""
        workflow = WorkflowStatus(name="decline_letter", is_finished=True)
        workflow_agents = ["decline_letter"]
        non_workflow_agents = ["smart_strategy"]

        result = _process_workflow_rejection(
            agent_name="decline_letter",
            workflow=workflow,
            workflow_agents=workflow_agents,
            non_workflow_agents=non_workflow_agents,
        )

        assert result is not None
        assert "decline_letter" in result
        assert "completed" in result.lower()

    def test_different_workflow_allowed(self):
        """Switching to a different workflow mid-conversation should be ALLOWED."""
        workflow = WorkflowStatus(name="decline_letter", is_finished=False)
        workflow_agents = ["decline_letter", "smart_strategy"]
        non_workflow_agents = []

        result = _process_workflow_rejection(
            agent_name="smart_strategy",
            workflow=workflow,
            workflow_agents=workflow_agents,
            non_workflow_agents=non_workflow_agents,
        )

        # Should be allowed - no rejection
        assert result is None


class TestHelperFunctions:
    """Tests for router helper functions."""

    def test_get_last_human_messages_single(self):
        """Should return last human message."""
        messages = [
            HumanMessage(content="First message"),
            AIMessage(content="AI response"),
            HumanMessage(content="Second message"),
        ]

        result = _get_last_human_messages(messages, max_count=1)

        assert len(result) == 1
        assert result[0] == "Second message"

    def test_get_last_human_messages_multiple(self):
        """Should return multiple last human messages."""
        messages = [
            HumanMessage(content="First message"),
            AIMessage(content="AI response"),
            HumanMessage(content="Second message"),
            AIMessage(content="Another AI response"),
            HumanMessage(content="Third message"),
        ]

        result = _get_last_human_messages(messages, max_count=2)

        assert len(result) == 2
        assert result[0] == "Third message"
        assert result[1] == "Second message"

    def test_get_last_human_messages_empty(self):
        """Should return empty list when no messages."""
        result = _get_last_human_messages([], max_count=1)
        assert len(result) == 0

    def test_get_context_from_stack_with_context(self):
        """Should return context from top of stack."""
        stack = [
            ContextFrame(agent_name="agent1", context="First context"),
            ContextFrame(agent_name="agent2", context="Second context"),
        ]

        result = _get_context_from_stack(stack)

        assert result == "Second context"

    def test_get_context_from_stack_empty(self):
        """Should return empty string when stack is empty."""
        result = _get_context_from_stack([])
        assert result == ""


class TestRouteToAgent:
    """Tests for route_to_agent function."""

    def test_routes_to_configured_agent(self):
        """Should route to configured agent."""
        state = create_initial_state(current_agent="decline_letter")

        result = route_to_agent(state)

        assert result == "decline_letter"

    def test_routes_to_hitl(self):
        """Should route to HITL when specified."""
        state = create_initial_state(current_agent=HITL_AGENT_NAME)

        result = route_to_agent(state)

        assert result == HITL_AGENT_NAME

    def test_routes_to_hitl_when_empty(self):
        """Should route to HITL when current_agent is empty."""
        state = create_initial_state(current_agent="")

        result = route_to_agent(state)

        assert result == HITL_AGENT_NAME

    def test_routes_to_hitl_for_unknown_agent(self):
        """Should route to HITL for unknown agent names."""
        state = create_initial_state(current_agent="unknown_agent")

        result = route_to_agent(state)

        assert result == HITL_AGENT_NAME


class TestRouterNode:
    """Tests for router node function."""

    @patch("supervisor_migration.router._classify_with_llm")
    def test_new_conversation_returns_welcome(self, mock_classify):
        """New conversation should return welcome prompt."""
        mock_llm = Mock()
        router = create_router_node(
            llm=mock_llm,
            max_last_messages=1,
        )

        state = create_initial_state(messages=[])

        result = router(state)

        assert result["current_agent"] == HITL_AGENT_NAME
        assert "last_agent_response" in result
        assert result["context_stack"] == []
        # LLM should not be called for new conversations
        mock_classify.assert_not_called()

    @patch("supervisor_migration.router._classify_with_llm")
    def test_direct_request_bypasses_llm(self, mock_classify):
        """Direct request should bypass LLM classification."""
        mock_llm = Mock()
        router = create_router_node(
            llm=mock_llm,
            max_last_messages=1,
        )

        state = create_initial_state(
            messages=[HumanMessage(content="Test")],
            is_direct=True,
            target_agent="decline_letter",
        )

        result = router(state)

        assert result["current_agent"] == "decline_letter"
        assert result["is_direct"] is False
        # LLM should not be called for direct requests
        mock_classify.assert_not_called()

    @patch("supervisor_migration.router._classify_with_llm")
    def test_direct_request_with_invalid_agent(self, mock_classify):
        """Direct request with invalid agent should go to HITL."""
        mock_llm = Mock()
        router = create_router_node(
            llm=mock_llm,
            max_last_messages=1,
        )

        state = create_initial_state(
            messages=[HumanMessage(content="Test")],
            is_direct=True,
            target_agent="invalid_agent",
        )

        result = router(state)

        assert result["current_agent"] == HITL_AGENT_NAME
        assert "Unknown agent" in result.get("last_agent_response", "")
