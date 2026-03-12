from agents.orchestrator.tool_set import tools as agent_tools
from agents.orchestrator.master_agent_prompts import WELCOME_PROMPT, REPEAT_PROMPT, IC_PROMPT_TEMPLATE_WITHOUT_CONTEXT, IC_PROMPT_TEMPLATE_WITH_CONTEXT
from smart_investigator.foundation.tools.tool_names import MASTER_AGENT_NAME
from smart_investigator.foundation.tools.human_in_the_loop import human_in_the_loop
from dataclasses import dataclass
from typing import List, TypedDict, Optional, Annotated, Union, Any
from smart_investigator.foundation.schemas.schemas import SmartInvestigatorAgentState, SIResponsesAgentStreamEvent, ToolStruct, TaskStruct, FrontEndInputStruct, StandardToolArgument, ToolArgument, SIResponsesAgentStreamEvent, FrontendInput, SIErrorCode
from smart_investigator.foundation.utils.utils import get_hash_id, format_task_struct, inject_parameters, is_retryable_exception, get_contents
from smart_investigator.foundation.utils.utils import prepare_hitl_task
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.types import Command, interrupt
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, BaseMessage, SystemMessage
from langchain_core.tools import tool, StructuredTool
from langgraph.runtime import Runtime
from langgraph.prebuilt import ToolNode, InjectedState, tools_condition
from langgraph.runtime import get_runtime
from copy import deepcopy
import httpx
import json
import backoff
import uuid
import logging

logger = logging.getLogger(__name__)

class WorkflowStatus(TypedDict):
    name: str
    is_finished: bool

class MasterAgentState(SmartInvestigatorAgentState):
    task_stack: List[TaskStruct]
    workflow: WorkflowStatus
    # current_depth: int # TODO: control max_depth

class IntentClassifierStruct(BaseModel):
    tool: str = Field(description="Must be one of the exact name of the tool provided above.")
    text: str = Field(description="The input text into the tool.")
    rationale: str = Field(description="The question asks about coverage of a specific loss event.")

class EndMessage(AIMessage):
    pass

@dataclass
class MasterAgentContext:
    """Context for interrupt operations"""
    infinite_loop: bool = False

# Prepare objects
tool_parser = PydanticOutputParser(pydantic_object=SIResponsesAgentStreamEvent)

### Acquire tools ###
# tools = agent_tools + [human_in_the_loop]

def get_default_context(agent_name: str, text: str) -> str:
    return f"{agent_name} was requesting for `{text}`"


def get_accessible_tools(tools: List[StructuredTool], task_stack: List[Union[dict, TaskStruct]]) -> List[StructuredTool]:
    """
    Filter tools based on task_stack context.

    When inside a workflow (task_stack non-empty), only allow:
    1. Tools marked as accessible_inside_workflow=True (e.g., smart_strategy, human_in_the_loop)
    2. The current workflow tool(s) on the task_stack (so user can continue interacting with active workflow)
    """
    if not task_stack:
        return tools  # All tools available outside workflow

    # Get current workflow tool(s) from task_stack
    current_workflow_tools = {
        format_task_struct(task).parent_tool for task in task_stack
    }

    # Filter to only accessible tools
    return [
        tool for tool in tools
        if getattr(tool.metadata, 'accessible_inside_workflow', False)
        or tool.name in current_workflow_tools
    ]


# def hitl_handler(state: MasterAgentState, llm: BaseChatModel, tools: List[StructuredTool]) -> AIMessage:
def hitl_handler(task_stack: List[Union[dict, TaskStruct]], llm: BaseChatModel, tools: List[StructuredTool], input_args: dict = {}, output_args: dict = {}, last_messages: list[str] = []) -> AIMessage:
    """Handle HITL message (either directly from START or from hitl tool)"""
    content = next(get_contents(input_args))
    user_query = content.text
    is_direct = content.custom_inputs.get("is_direct", False)
    target_tool_name = content.custom_inputs.get("agent_name", "")

    # Filter tools based on workflow context (task_stack)
    accessible_tools = get_accessible_tools(tools, task_stack)

    if not is_direct:
        # Allow using llm for intent classifier
        if task_stack:
            last_task: TaskStruct = format_task_struct(task_stack[-1])
            context = last_task.task.context
        else:
            context = ""

        joined_last_messages = "".join(["\n- " + msg for msg in last_messages]) + "\n"
        prompt_last_messages = f"Just for preference (i.e., the decision should be based primarily on the current user_query), the user also previously mentioned:\n<previous>\n{joined_last_messages}</previous>" if joined_last_messages else ""

        if not context:
            IC_PROMPT_TEMPLATE = IC_PROMPT_TEMPLATE_WITHOUT_CONTEXT
        else:
            IC_PROMPT_TEMPLATE = IC_PROMPT_TEMPLATE_WITH_CONTEXT

        ic_prompt = IC_PROMPT_TEMPLATE.format(
            context = context,
            user_query = user_query,
            prompt_last_messages = prompt_last_messages,
            human_in_the_loop = human_in_the_loop.name
        )

        def backoff_hdlr(details):
            logger.error("Backing off {wait:0.1f} seconds after {tries} tries "
                         "calling function {target} with args {args} and kwargs "
                         "{kwargs}".format(**details))

        @backoff.on_exception(
            backoff.expo,
            (httpx.RequestError, httpx.HTTPStatusError),
            giveup=lambda e: not is_retryable_exception(e),
            max_tries=3,
            jitter=backoff.full_jitter,
            on_backoff=backoff_hdlr
        )
        def invoke_with_retry(tools: list[StructuredTool], prompt: str):
            return llm.bind_tools(tools=tools).invoke(prompt)

        logger.error(f"***Prompt:\n{ic_prompt}\n")
        ic_ai_message = invoke_with_retry(tools=accessible_tools, prompt=ic_prompt)
        if tools_condition(state={'messages': [ic_ai_message]}) == END:
            # ai_message is not a tool calling
            # send the content to hitl
            retry_prompt = f"The assistance is confused with the next step. {ic_ai_message.content}. Would you please retype a clearer response?"
            next_task = json.dumps(dict(text=retry_prompt))
            ai_message = create_tool_calls_message(next_task, human_in_the_loop.name)
        else:
            ai_message = ic_ai_message

    else:
        # Direct input
        # llm classification is not used, rely only on task stack
        # Simply return the human content to the parent_tool
        if target_tool_name in [tool.name for tool in accessible_tools]:
            next_task = StandardToolArgument(text=user_query, rationale=f"A direct request for {target_tool_name}.").model_dump_json()
            ai_message = create_tool_calls_message(next_task, target_tool_name)
        else:
            # Tool not accessible - either doesn't exist or blocked inside current workflow
            if target_tool_name in [tool.name for tool in tools]:
                # Tool exists but is blocked inside workflow
                raise Exception(f'[{MASTER_AGENT_NAME}] Tool {target_tool_name} is not accessible inside current workflow.', SIErrorCode.INTERFACE_MISMATCH)
            else:
                # Tool doesn't exist
                raise Exception(f'[{MASTER_AGENT_NAME}] agent_name should not be empty.', SIErrorCode.INTERFACE_MISMATCH)

    return ai_message

def create_tool_calls_message(task_args: str, tool_name: str, output_args: dict[str, Any] | SIResponsesAgentStreamEvent = {}) -> AIMessage:
    """Generate an AIMessage with a single tool call"""
    # TODO: artifact to be changed to Serializable type???
    tool_call = {
        'index': 0,
        'id': f'call_{uuid.uuid1()}',
        'function': {'arguments': task_args, 'name': tool_name}, # TODO: check tool name and input struct
        'type': 'function'
    }
    ai_message = AIMessage(content='', additional_kwargs={'tool_calls': [tool_call]})
    if output_args:
        if isinstance(output_args, SIResponsesAgentStreamEvent):
            return inject_parameters(ai_message, output_args=output_args.model_dump())
        else:
            return inject_parameters(ai_message, output_args=output_args)
    else:
        return ai_message