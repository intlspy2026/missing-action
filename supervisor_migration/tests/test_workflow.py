"""
Workflow Management Tests

Tests for WorkflowStatus and workflow state transitions.
"""

import pytest
from supervisor_migration.state import (
    WorkflowStatus,
    SupervisorState,
    ContextFrame,
    create_initial_state,
    get_workflow_from_state,
    get_context_stack_from_state,
)


class TestWorkflowStatus:
    """Tests for WorkflowStatus model."""

    def test_default_values(self):
        """WorkflowStatus should have correct defaults."""
        status = WorkflowStatus()

        assert status.name == ""
        assert status.is_finished is False

    def test_is_active_when_started(self):
        """is_active should return True when workflow is started but not finished."""
        status = WorkflowStatus(name="decline_letter", is_finished=False)

        assert status.is_active() is True

    def test_is_active_when_finished(self):
        """is_active should return False when workflow is finished."""
        status = WorkflowStatus(name="decline_letter", is_finished=True)

        assert status.is_active() is False

    def test_is_active_when_not_started(self):
        """is_active should return False when no workflow started."""
        status = WorkflowStatus()

        assert status.is_active() is False

    def test_can_start_workflow_when_none_active(self):
        """Should allow starting any workflow when none is active."""
        status = WorkflowStatus()

        can_start, reason = status.can_start_workflow("decline_letter")

        assert can_start is True
        assert reason == ""

    def test_can_start_same_workflow_continuing(self):
        """Should allow continuing same workflow."""
        status = WorkflowStatus(name="decline_letter", is_finished=False)

        can_start, reason = status.can_start_workflow("decline_letter")

        assert can_start is True
        assert reason == ""

    def test_cannot_restart_finished_workflow(self):
        """Should not allow restarting a finished workflow."""
        status = WorkflowStatus(name="decline_letter", is_finished=True)

        can_start, reason = status.can_start_workflow("decline_letter")

        assert can_start is False
        assert reason == "FINISHED"

    def test_cannot_start_different_workflow(self):
        """Should not allow starting a different workflow."""
        status = WorkflowStatus(name="decline_letter", is_finished=False)

        can_start, reason = status.can_start_workflow("another_workflow")

        assert can_start is False
        assert reason == "DIFFERENT"


class TestContextFrame:
    """Tests for ContextFrame model."""

    def test_default_values(self):
        """ContextFrame should have correct defaults."""
        frame = ContextFrame(agent_name="test_agent", context="test context")

        assert frame.agent_name == "test_agent"
        assert frame.context == "test context"
        assert frame.parent_state == {}
        assert frame.artifact == {}
        assert frame.task_id == ""

    def test_with_all_values(self):
        """ContextFrame should accept all values."""
        frame = ContextFrame(
            agent_name="test_agent",
            context="test context",
            parent_state={"key": "value"},
            artifact={"artifact_key": "artifact_value"},
            task_id="task-123",
        )

        assert frame.agent_name == "test_agent"
        assert frame.context == "test context"
        assert frame.parent_state == {"key": "value"}
        assert frame.artifact == {"artifact_key": "artifact_value"}
        assert frame.task_id == "task-123"


class TestSupervisorStateHelpers:
    """Tests for SupervisorState helper functions.

    Note: SupervisorState is a TypedDict, so state is a dict, not an object.
    These tests use the helper functions.
    """

    def test_create_initial_state_defaults(self):
        """create_initial_state should set correct defaults."""
        state = create_initial_state()

        assert state["messages"] == []
        assert state["current_agent"] == ""
        assert state["context_stack"] == []
        assert isinstance(state["workflow"], WorkflowStatus)
        assert state["workflow"].name == ""
        assert state["is_direct"] is False
        assert state["target_agent"] == ""
        assert state["trusted"] is False
        assert state["current_artifact"] == {}
        assert state["input_path"] == ""
        assert state["last_agent_response"] == ""
        assert state["has_error"] is False
        assert state["error_message"] == ""

    def test_create_initial_state_with_workflow(self):
        """create_initial_state should accept workflow status."""
        workflow = WorkflowStatus(name="decline_letter", is_finished=False)
        state = create_initial_state(workflow=workflow)

        assert state["workflow"].name == "decline_letter"
        assert state["workflow"].is_finished is False

    def test_create_initial_state_with_context_stack(self):
        """create_initial_state should accept context stack."""
        frame = ContextFrame(agent_name="test_agent", context="test context")
        state = create_initial_state(context_stack=[frame])

        assert len(state["context_stack"]) == 1
        assert state["context_stack"][0].agent_name == "test_agent"

    def test_create_initial_state_direct_request(self):
        """create_initial_state should track direct request flags."""
        state = create_initial_state(
            is_direct=True,
            target_agent="decline_letter",
        )

        assert state["is_direct"] is True
        assert state["target_agent"] == "decline_letter"

    def test_get_workflow_from_state_with_object(self):
        """get_workflow_from_state should handle WorkflowStatus object."""
        workflow = WorkflowStatus(name="test", is_finished=True)
        state = {"workflow": workflow}

        result = get_workflow_from_state(state)

        assert result.name == "test"
        assert result.is_finished is True

    def test_get_workflow_from_state_with_dict(self):
        """get_workflow_from_state should handle dict representation."""
        state = {"workflow": {"name": "test", "is_finished": True}}

        result = get_workflow_from_state(state)

        assert result.name == "test"
        assert result.is_finished is True

    def test_get_workflow_from_state_missing(self):
        """get_workflow_from_state should return default when missing."""
        state = {}

        result = get_workflow_from_state(state)

        assert result.name == ""
        assert result.is_finished is False

    def test_get_context_stack_from_state_with_objects(self):
        """get_context_stack_from_state should handle ContextFrame objects."""
        frame = ContextFrame(agent_name="test", context="ctx")
        state = {"context_stack": [frame]}

        result = get_context_stack_from_state(state)

        assert len(result) == 1
        assert result[0].agent_name == "test"

    def test_get_context_stack_from_state_with_dicts(self):
        """get_context_stack_from_state should handle dict representation."""
        state = {"context_stack": [{"agent_name": "test", "context": "ctx"}]}

        result = get_context_stack_from_state(state)

        assert len(result) == 1
        assert result[0].agent_name == "test"

    def test_get_context_stack_from_state_empty(self):
        """get_context_stack_from_state should return empty list when missing."""
        state = {}

        result = get_context_stack_from_state(state)

        assert result == []


class TestWorkflowTransitions:
    """Tests for workflow state transitions."""

    def test_start_workflow(self):
        """Starting a workflow should set name and is_finished=False."""
        # Initial state - no workflow
        initial = WorkflowStatus()
        assert initial.name == ""
        assert initial.is_finished is False

        # Start workflow
        started = WorkflowStatus(name="decline_letter", is_finished=False)
        assert started.name == "decline_letter"
        assert started.is_finished is False
        assert started.is_active() is True

    def test_finish_workflow(self):
        """Finishing a workflow should set is_finished=True."""
        # Started workflow
        started = WorkflowStatus(name="decline_letter", is_finished=False)
        assert started.is_active() is True

        # Finish workflow
        finished = WorkflowStatus(name="decline_letter", is_finished=True)
        assert finished.name == "decline_letter"
        assert finished.is_finished is True
        assert finished.is_active() is False

    def test_workflow_in_state(self):
        """Workflow should be properly tracked in state."""
        # Start with no workflow
        state = create_initial_state()
        workflow = get_workflow_from_state(state)
        assert workflow.name == ""

        # Update with workflow
        new_workflow = WorkflowStatus(name="decline_letter", is_finished=False)
        state["workflow"] = new_workflow

        workflow = get_workflow_from_state(state)
        assert workflow.name == "decline_letter"
        assert workflow.is_active() is True
