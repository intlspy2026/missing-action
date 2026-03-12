"""
Supervisor Agent

Entry point extending LanggraphResponsesAgent.
This replaces the current MasterAgent implementation with the supervisor pattern.

Note: Uses structured output for routing (no tools needed).
"""

from typing import Generator, Iterator, Optional, Any
from uuid import uuid4
from copy import deepcopy
import logging
import traceback
import yaml
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.errors import GraphInterrupt
from langgraph.types import Command

from mlflow.pyfunc import PythonModelContext
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)
from mlflow.types.responses_helpers import Content, OutputItem, Response

from databricks.sdk import WorkspaceClient

# Import from existing codebase for compatibility
from smart_investigator.foundation.agents.response_agent import LanggraphResponsesAgent
from smart_investigator.foundation.schemas.schemas import (
    EventType,
    DoneType,
    SIErrorCode,
    LanggraphStreamEvent,
)
from smart_investigator.foundation.llm.poa_azure_openai import get_llm
from smart_investigator.foundation.checkpointers.stateless_checkpointer.stateless_checkpointer import (
    StatelessMemorySaver,
)

# Import supervisor components
from supervisor_migration.state import SupervisorState
from supervisor_migration.supervisor_graph import create_supervisor_graph
from supervisor_migration.agent_config import (
    AGENT_ENDPOINTS,
    SUPERVISOR_AGENT_NAME,
    get_agents_introduction,
)
from supervisor_migration.streaming_utils import (
    create_thinking_event,
    create_response_event,
    create_error_event,
    create_completed_event,
)

logger = logging.getLogger(__name__)


class SupervisorAgent(LanggraphResponsesAgent):
    """
    Supervisor Agent implementing native LangGraph supervisor pattern.

    This replaces the current MasterAgent with a cleaner architecture:
    - Router node for intent classification (uses structured output, not tools)
    - Agent nodes for each configured agent
    - HITL node for user interaction

    Maintains full compatibility with MLflow ResponsesAgent interface
    and existing streaming event format.
    """

    @property
    def AgentName(self) -> str:
        return SUPERVISOR_AGENT_NAME

    def __init__(self):
        """Initialize the supervisor agent."""
        super().__init__()
        self.llm: Optional[BaseChatModel] = None
        self.graph: Optional[StateGraph] = None
        self.model_config: dict = {}
        self.context: dict = {}
        self.use_checkpointer: bool = False
        self.max_checkpoints: int = 1
        self._workspace_client: Optional[WorkspaceClient] = None

    def load_context(self, context: PythonModelContext):
        """
        Load model context from MLflow artifacts.

        Args:
            context: MLflow Python model context
        """
        # Load configuration
        artifact_path = context.artifacts.get("configs", "")
        if artifact_path:
            with open(artifact_path, "r", encoding="utf-8") as f:
                self.model_config = yaml.safe_load(f) or {}
        else:
            self.model_config = {}

        # Initialize LLM
        self.llm = get_llm(self.model_config)

        # Build graph (no tools needed - uses structured output)
        self.graph = self.get_graph()

        # Checkpointer config
        self.use_checkpointer = self.model_config.get("model", {}).get("use_checkpointer", False)
        self.max_checkpoints = self.model_config.get("model", {}).get("max_checkpoints", 1)

        # Context with Databricks client
        model_context = self.model_config.get("model", {}).get("context", {})
        self.context = model_context if model_context else {}
        self._workspace_client = WorkspaceClient()
        self.context["client"] = self._workspace_client.serving_endpoints.get_open_ai_client()

    def get_graph(self) -> StateGraph:
        """
        Get the supervisor graph.

        Note: No tools parameter - uses structured output for classification.

        Returns:
            Configured StateGraph
        """

        def get_client():
            if self._workspace_client is None:
                self._workspace_client = WorkspaceClient()
            return self._workspace_client.serving_endpoints.get_open_ai_client()

        return create_supervisor_graph(
            llm=self.llm,
            get_client=get_client,
            max_last_messages=1,
        )

    def _init_checkpointer(self, request: ResponsesAgentRequest) -> Optional[BaseCheckpointSaver]:
        """Initialize checkpointer from request."""
        if not self.use_checkpointer:
            return None

        state_json = request.custom_inputs.get("state", "{}")
        return StatelessMemorySaver(
            initial_state_json=state_json,
            max_checkpoints=self.max_checkpoints,
        )

    def _init_agent(self, checkpointer: Optional[BaseCheckpointSaver]) -> CompiledStateGraph:
        """Compile the graph with optional checkpointer."""
        if checkpointer:
            return self.graph.compile(checkpointer=checkpointer)
        return self.graph.compile()

    def _preprocess_request(
        self,
        request: ResponsesAgentRequest,
        config: dict,
        checkpointer: Optional[BaseCheckpointSaver],
    ) -> dict:
        """
        Preprocess request into graph input.

        Handles both new messages and resume from interrupt.
        """
        if not request.input:
            return {"messages": []}

        content = request.input[0].content[0]
        if isinstance(content, dict):
            content = Content(**content)

        text = content.text
        custom_inputs = getattr(content, "custom_inputs", {})

        human_message = HumanMessage(
            content=text,
            additional_kwargs={"custom_inputs": custom_inputs},
        )

        # Check if resuming from interrupt
        if checkpointer:
            is_resume = request.custom_inputs.get("is_resume", False)
            history = checkpointer.get_tuple(config)

            if history and is_resume and history.pending_writes:
                return Command(resume=content, update={"default_resume": True})

        # Build state input
        state_dict = deepcopy(request.custom_inputs.get("state", {}))
        messages = state_dict.get("messages", [])
        messages.append(human_message)
        state_dict["messages"] = messages

        # Extract direct request flags
        is_direct = custom_inputs.get("is_direct", False)
        target_agent = custom_inputs.get("agent_name", "")

        state_dict["is_direct"] = is_direct
        state_dict["target_agent"] = target_agent

        return state_dict

    def predict_stream(
        self,
        request: ResponsesAgentRequest,
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        """
        Main streaming prediction endpoint.

        Implements MLflow ResponsesAgent interface with streaming.

        Args:
            request: ResponsesAgent request

        Yields:
            Stream of ResponsesAgentStreamEvent
        """
        if not request.custom_inputs:
            yield create_error_event("No custom_inputs in request")
            return

        try:
            # Initialize
            config = {"configurable": {"thread_id": request.user}}
            checkpointer = self._init_checkpointer(request)
            agent = self._init_agent(checkpointer)
            lg_input = self._preprocess_request(request, config, checkpointer)

            final_response = None

            # Build input context
            request_copy = deepcopy(request)
            request_copy.custom_inputs["state"] = {}
            input_context = {**self.context, "request": request_copy.model_dump()}

            # Stream graph execution
            stream_mode = self.model_config.get("model", {}).get(
                "langgraph_event", ["messages", "values", "custom"]
            )

            for mode, response in agent.stream(
                lg_input,
                stream_mode=stream_mode,
                config=config,
                context=input_context,
            ):
                if mode == LanggraphStreamEvent.messages:
                    # LLM token streaming
                    chunk, metadata = response
                    if hasattr(chunk, "content") and chunk.content:
                        yield ResponsesAgentStreamEvent(
                            type=EventType.delta_text,
                            delta=chunk.content,
                            item_id=str(uuid4()),
                        )

                elif mode == LanggraphStreamEvent.custom:
                    # Custom events (thinking messages)
                    stream_event = response.get("stream_event")
                    if stream_event:
                        yield stream_event
                    else:
                        text = response.get("text", "")
                        if text:
                            yield create_thinking_event(text)

                elif mode == LanggraphStreamEvent.values:
                    # Final values - save for last
                    final_response = response

        except GraphInterrupt as e:
            # Interrupt for HITL
            interrupt_content = e.args[0] if e.args else []
            yield create_response_event(
                text=interrupt_content[0].text if interrupt_content else "",
                agent_name=SUPERVISOR_AGENT_NAME,
                is_interrupt=True,
            )

        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Supervisor error: {e}\n{error_trace}")
            yield create_error_event(str(e), SIErrorCode.UNKNOWN_FAILURE)

        # Yield final response
        if final_response:
            messages = final_response.get("messages", [])
            last_message = messages[-1] if messages else None
            text = last_message.content if last_message else ""

            is_interrupt = LanggraphStreamEvent.interrupt in final_response

            yield create_response_event(
                text=text,
                agent_name=SUPERVISOR_AGENT_NAME,
                is_interrupt=is_interrupt,
                artifact=final_response.get("current_artifact", {}),
            )

        # Yield completion event
        state_json = checkpointer.to_json() if checkpointer else ""
        yield create_completed_event(state_json)

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        """
        Non-streaming prediction.

        Args:
            request: ResponsesAgent request

        Returns:
            ResponsesAgentResponse
        """
        # Collect all stream events
        events = list(self.predict_stream(request))

        # Find the final response event
        final_event = None
        for event in reversed(events):
            if event.type == EventType.done:
                final_event = event
                break

        if final_event and final_event.item:
            return ResponsesAgentResponse(
                output=[final_event.item],
                custom_outputs=getattr(final_event.item, "custom_outputs", {}),
            )

        return ResponsesAgentResponse(
            output=[],
            custom_outputs={},
        )
