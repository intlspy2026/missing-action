from typing import List, TypedDict, Optional, Annotated, Union, Any, Literal, Tuple, Dict
from smart_investigator.foundation.schemas.schemas import SmartInvestigatorAgentState, SIErrorCode
from smart_investigator.foundation.tools.tool_names import EXTERNAL_AGENT_NAME
from agents.external_agent.prompt_manager.knowledge_prompts import (
    KNOWLEDGE_RETRIEVAL_SYSTEM_PROMPT,
    RETRIEVAL_TASKS,
    KNOWLEDGE_RETRIEVAL_TASK_PROMPT,
    SECTION_KNOWLEDGE_REPORT_SYSTEM_PROMPT,
    SECTION_KNOWLEDGE_REPORT_PROMPT,
)
from agents.external_agent.prompt_manager.external_agent_prompts import (
    EXTERNAL_AGENT_SYSTEM_PROMPT,
    KEY_CONCERNS_DRAFT_PROMPT,
    DOC_REQUEST_DRAFT_PROMPT,
    ADDITIONAL_ENQUIRIES_DRAFT_PROMPT,
    INTERVIEW_PLAN_DRAFT_PROMPT,
    SECTION_FEEDBACK_PROMPT,
    SECTION_FEEDBACK_KNOWLEDGE_BLOCK,
)
# --- Commented out: unused imports ---
# from agents.external_agent.prompt_manager.interview_strategy_prompts import INTERVIEW_STRATEGY_SYSTEM_PROMPT, INTERVIEW_STRATEGY_DRAFT_PROMPT, INTERVIEW_STRATEGY_FEEDBACK_PROMPT
# from agents.external_agent.prompt_manager.external_agent_prompts import INTERVIEW_DOC_REQUEST_PROMPT
# from agents.external_agent.prompt_manager.online_eval_prompts import eval_user_msg_template, eval_sys_msg_template
# from agents.external_agent.prompt_manager.knowledge_prompts import KNOWLEDGE_REPORT_SYSTEM_PROMPT, KNOWLEDGE_REPORT_PROMPT
from agents.external_agent.tools.query_investigation_processes import query_investigation_processes
from agents.external_agent.tools.think_tool import think_tool
from agents.external_agent.tools.search_complete import search_complete
from agents.external_agent.utils import (
    build_form_info,
    build_form_key_concerns, parse_form_to_key_concerns,
    build_form_doc_request, parse_form_to_doc_request,
    build_form_enquiries, parse_form_to_enquiries,
    build_form_interview_plan, parse_form_to_interview_plan,
    build_form_final,
)
from smart_investigator.foundation.utils.utils import prepare_thinking_message, prepare_hitl_task
from agents.external_agent.schemas import (
    InterviewQuestion, InterviewQuestionSets,
    DocRequest, DocRequestSet,
    KnowledgeSet, Knowledge,
    HITLDecision, ExternalAgentState,
    KeyConcern, KeyConcernSet,
    ExternalAgentPlan,
    AdditionalEnquiriesSet, AdditionalEnquiries,
)
# --- Commented out: unused schema imports ---
# from agents.external_agent.schemas import InterviewStrategy, InterviewPlan, KnowledgeReport, InterviewPlanState

# --- Commented out: online evaluation no longer used ---
# from smart_investigator.foundation.evals.online.eval_core import run_evaluation_from_yaml

from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, BaseMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.config import get_stream_writer
from langgraph.types import Command, interrupt, StreamWriter
from langgraph.runtime import Runtime, get_runtime
from copy import deepcopy
import json
import logging
import uuid
from datetime import datetime
import asyncio
import mlflow
from mlflow.entities import SpanType

logger = logging.getLogger(__name__)

use_checkpointer = True  # TODO get from config


def get_graph(llm: BaseChatModel) -> StateGraph:
    # ------------------------------------
    # Helpers
    # ------------------------------------

    def _get_ctx(state: dict) -> tuple[Runtime, StreamWriter, list]:
        runtime = get_runtime()
        writer = get_stream_writer()
        messages = state.get("messages", []) or []
        return runtime, writer, messages

    def _frontend_input(runtime: Runtime) -> dict[str, Any]:
        req = runtime.context.get("request", {}) or {}

        return (req.get("input", {}) or {})[0].get("content", {})[0] or {}

    def _classify_hitl(
        hitl_text: str,
        hitl_artifact: dict[str, Any],
        prev_task: str
    ) -> HITLDecision:
        """
        Classification rules:
        - If artifact is present, and no text => accept (user edited/confirmed structured output)
        - Else if text is present => classify intent & summarise task using LLM
        """

        if hitl_artifact and not hitl_text:
            return HITLDecision(intent="accept", task_summary="")

        # if hitl_text.strip():
        #    # Treat plain text as feedback by default (this matches your stated behavior)
        #    return HITLDecision(intent="feedback", hitl_text.strip())

        parser = PydanticOutputParser(pydantic_object=HITLDecision)
        prompt = f"""
        You are routing and summarising the next task for a human-in-the-loop response for an insurance fraud external agent instruction workflow. The task should either be to draft instructions, or to edit based on user feedback.

        Previous task: {prev_task}

        Human response text:
        {hitl_text if hitl_text else "<empty>"}

        Human response artifact:
        {hitl_artifact if hitl_artifact else "<empty>"}

        Classify intent:
        - "accept": user accepts OR the artifact has been provided back with no human response text.
        - "feedback": user gives feedback/instructions to revise.
        - "unrelated": user asks something unrelated.

        Summarise the task:
        - If the intent is unrelated, or if there is no human response text, leave the task as ""
        - Otherwise, write a short paragraph that states the next task.
        - Start the task_summary with "Task: "

        {parser.get_format_instructions()}
        Return JSON only.
        """

        resp = llm.invoke(
            input=prompt,
            temperature=0.0,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        content = resp.content if isinstance(
            resp.content, str) else resp.content[0]["text"]
        hitl_decision = parser.parse(content)

        return hitl_decision

    def _route_from_pending_step(pending_step: str) -> str:
        """
        Where to go next after classifying the HITL.
        - unrelated always restarts
        - accept/feedback re-enters the relevant node
        """
        if pending_step == "init":
            return "initialise_query"
        if pending_step == "key_concerns_review":
            return "generate_key_concerns"
        if pending_step == "doc_request_review":
            return "generate_doc_request"
        if pending_step == "enquiries_review":
            return "generate_enquiries"
        if pending_step == "interview_plan_review":
            return "generate_interview_plan"

        # unknown step -> restart
        return "initialise_query"

    def _resolve_hitl_artifact(state: "ExternalAgentState", pending_step: str, incoming_artifact: dict | None, *, intent: str = "") -> Any:
        """
        If the frontend didn't send an artifact (common for feedback-only resumes),
        fall back to the last generated output stored in state for the relevant step.
        For section review steps on accept, parse incoming form payload through the
        appropriate parser. For feedback, always return the previous state output —
        the user is providing text feedback, not editing the form.
        """
        incoming_artifact = incoming_artifact or {}

        step_to_parser = {
            "key_concerns_review": (parse_form_to_key_concerns, "key_concerns"),
            "doc_request_review": (parse_form_to_doc_request, "doc_request"),
            "enquiries_review": (parse_form_to_enquiries, "additional_enquiries"),
            "interview_plan_review": (parse_form_to_interview_plan, "interview_plan"),
        }

        if pending_step in step_to_parser:
            parser_fn, state_key = step_to_parser[pending_step]
            previous = state.get(state_key)
            # Only parse form submission on accept; for feedback return previous as-is
            if intent == "accept" and incoming_artifact:
                try:
                    parsed = parser_fn(incoming_artifact, previous=previous)
                    # If parsing produced empty output but previous has content,
                    # the wrong form artifact was sent — fall back to previous
                    parsed_list = (
                        getattr(parsed, "concern_set", None) or
                        getattr(parsed, "document_set", None) or
                        getattr(parsed, "enquiries_set", None) or
                        getattr(parsed, "question_sets", None)
                    )
                    if not parsed_list and previous:
                        return previous
                    return parsed
                except Exception:
                    return previous
            return previous

        # For init/unknown, nothing sensible to fall back to
        return incoming_artifact

    def _next_section(current: str, selected_sections: list[str]) -> str:
        """
        Given the current section, return the next section node name
        based on the fixed order and selected_sections.
        Order: key_concerns → doc_request → additional_enquiries → interview_plan → assemble_plan
        """
        order = [
            ("doc_request", "generate_doc_request"),
            ("additional_enquiries", "generate_enquiries"),
            ("interview_plan", "generate_interview_plan"),
        ]

        if current == "key_concerns":
            remaining = order
        elif current == "doc_request":
            remaining = order[1:]
        elif current == "additional_enquiries":
            remaining = order[2:]
        else:
            return "assemble_plan"

        for section_key, node_name in remaining:
            if section_key in selected_sections:
                return node_name

        return "assemble_plan"


    def _parse_investigation_type_to_filters(lob: str, inv_type: str) -> dict:
        """
        Input examples:
        - lob: "Motor", investigation_type: "Staged accident"
        - lob: "Motor", investigation_type: "Misrepresentation | sub-type"

        Output:
        {"lob": ["Motor"], "fraud_type": ["staged accident"]}
        """
        s = (inv_type or "").strip()

        # Fraud type is before the sub type delimiter "|"
        fraud_type = s.split("|", 1)[0].strip()

        if not fraud_type:
            raise ValueError(
                f"Could not parse fraud_type from investigation_type: {inv_type}")

        return {"lob": [lob], "fraud_type": [fraud_type]}

    # ------------------------------------
    # Async tool helpers (unchanged)
    # ------------------------------------

    async def _run_tool_call_async(
        call: dict,
        *,
        filters: dict,
        knowledge_endpoint: str
    ) -> Tuple[str, dict, Any]:
        """
        Run ONE tool call concurrently (async).
        Returns: (tool_name, args, result)
        """
        tool_name = call["name"]
        args = call.get("args", {}) or {}

        if tool_name == "query_investigation_processes":
            result = await asyncio.to_thread(
                query_investigation_processes.invoke,
                {"endpoint_name": knowledge_endpoint,
                    "query": args["query"], "filters": filters},
            )
            return tool_name, args, result

        if tool_name == "think_tool":
            result = await asyncio.to_thread(
                think_tool.invoke,
                args.get("reflection", ""),
            )
            return tool_name, args, result

        if tool_name == "search_complete":
            return tool_name, args, {"ok": True}

        return tool_name, args, {"error": f"Unknown tool {tool_name}"}

    async def _run_retrieval_task(
        task_key: str,
        system_prompt: str,
        prompt: str,
        llm_with_tools,
        filters: dict,
        knowledge_endpoint: str,
        max_iterations: int = 20
    ) -> list[Knowledge]:
        """
        Run ONE retrieval task and return extracted knowledge
        """
        prompts = [SystemMessage(content=system_prompt),
                   HumanMessage(content=prompt)]

        collected: list[Knowledge] = []

        for _ in range(max_iterations):
            llm_response = await asyncio.to_thread(
                llm_with_tools.invoke,
                prompts,
                temperature=0.0,
                max_tokens=8192,
            )

            tool_calls = getattr(llm_response, "tool_calls", []) or []
            if not tool_calls:
                break

            finish = any(c["name"] == "search_complete" for c in tool_calls)
            calls_to_run = [
                c for c in tool_calls if c["name"] != "search_complete"]

            if not calls_to_run:
                break

            results = await asyncio.gather(
                *[_run_tool_call_async(c, filters=filters, knowledge_endpoint=knowledge_endpoint)
                  for c in calls_to_run],
                return_exceptions=True,
            )

            for call, r in zip(calls_to_run, results):
                if isinstance(r, Exception):
                    raise Exception(
                        f"Retrieval task '{task_key}' failed",
                        SIErrorCode.AGENT_ENDPOINT_FAILURE,
                    ) from r

                tool_name, _, result = r
                prompts.append(
                    HumanMessage(f"[Tool {tool_name}] result:\n{result}")
                )

                if tool_name == "query_investigation_processes":
                    rows = (result or {}).get("knowledge", []) or []
                    for row in rows:
                        collected.append(
                            Knowledge(
                                query=row.get("query", ""),
                                answer=row.get("answer", ""),
                            )
                        )

            if finish:
                break

        return collected

    # ------------------------------------
    # Per-section knowledge helpers
    # ------------------------------------

    async def _retrieve_section_knowledge(
        task_key: str,
        task_def: dict,
        state: "ExternalAgentState",
        knowledge_endpoint: str,
    ) -> KnowledgeSet:
        """
        Retrieve knowledge for a single section.
        Loops over investigation_types from state, runs _run_retrieval_task
        for the given task_key only. Returns raw KnowledgeSet.
        """
        lob = state.get("lob", "")
        investigation_types = state.get("investigation_type", []) or []
        if not investigation_types or not lob:
            raise ValueError(
                f"lob or investigation_type has not been passed in state: {state}")

        parser = PydanticOutputParser(pydantic_object=KnowledgeSet)
        llm_with_tools = llm.bind_tools(
            [query_investigation_processes, search_complete, think_tool])

        knowledge_items: list[Knowledge] = []

        for inv_type in investigation_types:
            filters = _parse_investigation_type_to_filters(lob, inv_type)
            system_prompt = KNOWLEDGE_RETRIEVAL_SYSTEM_PROMPT
            prompt = KNOWLEDGE_RETRIEVAL_TASK_PROMPT.format(
                task=task_def["task"],
                stopping_criteria=task_def["stopping_criteria"],
                investigation_type=inv_type,
                format=parser.get_format_instructions(),
            )

            result = await _run_retrieval_task(
                task_key=task_key,
                system_prompt=system_prompt,
                prompt=prompt,
                llm_with_tools=llm_with_tools,
                filters=filters,
                knowledge_endpoint=knowledge_endpoint,
            )
            knowledge_items.extend(result)

        return KnowledgeSet(knowledge=knowledge_items)

    def _synthesize_section_knowledge(
        section_name: str,
        knowledge_set: KnowledgeSet,
        investigation_types: list[str],
        output_schema,
    ) -> Any:
        """
        Synthesize raw knowledge into a section-specific structured output.
        Uses SECTION_KNOWLEDGE_REPORT_PROMPT with the given output_schema
        as the Pydantic parser format.
        """
        parser = PydanticOutputParser(pydantic_object=output_schema)
        prompt = SECTION_KNOWLEDGE_REPORT_PROMPT.format(
            section_name=section_name,
            investigation_type=", ".join(investigation_types),
            knowledge_set=knowledge_set.model_dump_json(),
            format=parser.get_format_instructions(),
        )

        prompts = [
            SystemMessage(content=SECTION_KNOWLEDGE_REPORT_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        response = llm.invoke(
            input=prompts,
            temperature=0.0,
            max_tokens=8192,
            response_format={"type": "json_object"},
        )
        content = response.content if isinstance(
            response.content, str) else response.content[0]["text"]
        return parser.parse(content)

    # --- Commented out: replaced by per-section _retrieve_section_knowledge helper ---
    # async def retrieve_knowledge_async(state: "ExternalAgentState") -> Command:
    #     runtime, writer, messages = _get_ctx(state)
    #     knowledge_endpoint = runtime.context["resources_endpoint_name"]
    #
    #     writer(prepare_thinking_message(EXTERNAL_AGENT_NAME,
    #            "Retrieving knowledge on external agent..."))
    #
    #     decision = state.get("hitl_decision")
    #     task_summary = decision.task_summary if decision else ""
    #
    #     lob = state.get("lob", "")
    #     investigation_types = state.get("investigation_type", []) or []
    #     if not investigation_types or not lob:
    #         raise ValueError(
    #             f"lob or investigation_type has not been passed in state: {state}")
    #     initial_review = state.get("initial_review", "")
    #
    #     parser = PydanticOutputParser(pydantic_object=KnowledgeSet)
    #     llm_with_tools = llm.bind_tools(
    #         [query_investigation_processes, search_complete, think_tool])
    #
    #     knowledge_items: list[Knowledge] = []
    #
    #     for inv_type in investigation_types:
    #         filters = _parse_investigation_type_to_filters(lob, inv_type)
    #         system_prompt = KNOWLEDGE_RETRIEVAL_SYSTEM_PROMPT
    #         task_results = await asyncio.gather(
    #             *[
    #                 _run_retrieval_task(
    #                     task_key=task_key,
    #                     system_prompt=system_prompt,
    #                     prompt=KNOWLEDGE_RETRIEVAL_TASK_PROMPT.format(
    #                         task=task_def["task"],
    #                         stopping_criteria=task_def["stopping_criteria"],
    #                         investigation_type=inv_type,
    #                         format=parser.get_format_instructions(),
    #                     ),
    #                     llm_with_tools=llm_with_tools,
    #                     filters=filters,
    #                     knowledge_endpoint=knowledge_endpoint
    #                 )
    #                 for task_key, task_def in RETRIEVAL_TASKS.items()
    #             ]
    #         )
    #         for result in task_results:
    #             knowledge_items.extend(result)
    #
    #     knowledge = KnowledgeSet(knowledge=knowledge_items)
    #
    #     report_parser = PydanticOutputParser(pydantic_object=KnowledgeReport)
    #     report_system_prompt = KNOWLEDGE_REPORT_SYSTEM_PROMPT
    #     report_prompt = KNOWLEDGE_REPORT_PROMPT.format(
    #         investigation_type=", ".join(investigation_types),
    #         knowledge_set=knowledge.model_dump_json(),
    #         format=report_parser.get_format_instructions()
    #     )
    #     report_prompts = [SystemMessage(content=report_system_prompt), HumanMessage(content=report_prompt)]
    #     report_response = llm.invoke(input=report_prompts, temperature=0.0, max_tokens=8192, response_format={"type": "json_object"})
    #     report_content = report_response.content if isinstance(report_response.content, str) else report_response.content[0]["text"]
    #     knowledge_report = report_parser.parse(report_content)
    #
    #     return Command(
    #         goto="generate_plan",
    #         update={
    #             "knowledge": knowledge_report,
    #             "messages": messages + [AIMessage("Investigation processes retrieved.")],
    #             "pending_step": None,
    #         },
    #     )
    #
    # def retrieve_knowledge(state: "ExternalAgentState") -> Command:
    #     """Sync wrapper so LangGraph node can stay def-based."""
    #     try:
    #         return asyncio.run(retrieve_knowledge_async(state))
    #     except RuntimeError:
    #         loop = asyncio.get_event_loop()
    #         return loop.run_until_complete(retrieve_knowledge_async(state))

    # ------------------------------------
    # Nodes
    # ------------------------------------

    def route_interrupt(state: "ExternalAgentState") -> Command:
        """
        Central interrupt handler:
        1) Calls interrupt(...) exactly once per HITL prompt.
        2) On resume, classifies accept/feedback/unrelated.
        3) Extracts a concise task summary for the agent.
        4) Routes back to the correct node based on pending_step.
        """
        runtime, writer, messages = _get_ctx(state)

        pending_step = state.get("pending_step")
        hitl_task = state.get("hitl_task")
        prev_decision = state.get("hitl_decision")

        # - First pass: pauses execution here.
        # - Resume: returns immediately with resume payload (text).
        _ = interrupt(hitl_task)

        hitl = _frontend_input(runtime)
        hitl_text = (hitl.get("text") or "").strip()
        incoming_artifact = hitl.get("custom_inputs", {}).get(
            "artifact").get("form_data") or {}
        prev_task = prev_decision.task_summary if prev_decision else ""

        hitl_decision = _classify_hitl(hitl_text, incoming_artifact, prev_task)
        hitl_artifact = _resolve_hitl_artifact(
            state, pending_step, incoming_artifact, intent=hitl_decision.intent)

        intent = hitl_decision.intent
        task_summary = hitl_decision.task_summary

        if intent == "unrelated":
            text = "Please review the AI generated output and either edit and submit, or provide your feedback."
            new_hitl_task = prepare_hitl_task(
                agent_name=EXTERNAL_AGENT_NAME,
                text=text,
                context="User must accept, edit+submit, or provide feedback relevant to the current output.",
                state={} if use_checkpointer else {
                    **state, "messages": messages + [AIMessage(text)]},
                artifact=hitl_artifact,
            )

            writer(prepare_thinking_message(EXTERNAL_AGENT_NAME,
                   "HITL response unrelated; re-prompting user."))
            return Command(
                goto="route_interrupt",
                update={
                    "hitl_task": new_hitl_task,
                    "hitl_decision": hitl_decision,
                    "hitl_artifact": hitl_artifact,
                    "messages": messages + [AIMessage(f"HITL decision: unrelated (step={pending_step})")],
                },
            )

        custom_message = prepare_thinking_message(
            EXTERNAL_AGENT_NAME, f"Decision is {intent}, proceeding... \n{task_summary}")
        writer(custom_message)

        goto = _route_from_pending_step(pending_step)

        return Command(
            goto=goto,
            update={
                "resume": False,
                "hitl_decision": hitl_decision,
                "hitl_artifact": hitl_artifact,
                "hitl_task": None,
                "messages": messages + [AIMessage(f"HITL decision: {intent} (step={pending_step}, task={task_summary})")],
            },
        )

    def initialise_query(state: "ExternalAgentState") -> Command:
        runtime, writer, messages = _get_ctx(state)
        form_config = runtime.context["forms"]

        decision = state.get("hitl_decision")
        hitl_artifact = state.get("hitl_artifact") or {}
        feedback = decision.task_summary if decision and decision.intent == "feedback" else ""

        # If user accepted the form (artifact present), persist into state and proceed
        if decision and decision.intent == "accept" and hitl_artifact:
            claim_id = hitl_artifact.get("claim_id")
            brand = hitl_artifact.get("brand")
            lob = hitl_artifact.get("lob")
            investigation_type = hitl_artifact.get("investigation_type")
            investigation_scope = hitl_artifact.get("investigation_scope")
            initial_review = hitl_artifact.get("initial_review")
            additional_info = hitl_artifact.get("additional_info")
            selected_sections = hitl_artifact.get("selected_sections", ["doc_request", "additional_enquiries"])

            if claim_id and investigation_type and investigation_scope and initial_review:
                return Command(
                    goto="dispatch_sections",
                    update={
                        "claim_id": claim_id,
                        "brand": brand,
                        "lob": lob,
                        "investigation_type": investigation_type,
                        "investigation_scope": investigation_scope,
                        "initial_review": initial_review,
                        "additional_info": additional_info,
                        "selected_sections": selected_sections,
                        "hitl_decision": decision,
                        "hitl_artifact": None,
                        "pending_step": None,
                        "messages": messages + [AIMessage("Inputs captured. Dispatching section generation.")],
                    },
                )

        # If already have required fields, proceed
        if state.get("claim_id") and state.get("lob") and state.get("investigation_type") and state.get("initial_review"):
            return Command(
                goto="dispatch_sections",
                update={"messages": messages +
                        [AIMessage("Inputs present. Dispatching section generation.")], "pending_step": None},
            )

        # Otherwise: prompt user with form via HITL
        text = "Hi! I am the External Agent - I can assist you in writing instructions for external agent appointment. To begin, please proceed to fill out the form..."
        artifact = build_form_info(form_config)
        hitl_task = prepare_hitl_task(
            agent_name=EXTERNAL_AGENT_NAME,
            text=text,
            context="User must provide details.",
            state={} if use_checkpointer else {
                **state, "messages": messages + [AIMessage(text)]},
            artifact=artifact,
        )

        custom_message = prepare_thinking_message(
            EXTERNAL_AGENT_NAME, f"Waiting for form submission...")
        writer(custom_message)

        return Command(
            goto="route_interrupt",
            update={
                "pending_step": "init",
                "hitl_task": hitl_task,
                "messages": messages + [AIMessage("Awaiting form submission.")],
                "hitl_decision": None,
                "hitl_artifact": None,
            },
        )

    def dispatch_sections(state: "ExternalAgentState") -> Command:
        """Thin node that kicks off sequential section generation."""
        messages = state.get("messages", [])
        return Command(
            goto="generate_key_concerns",
            update={
                "hitl_decision": None,
                "hitl_artifact": None,
                "messages": messages + [AIMessage("Dispatching section generation...")],
            },
        )

    # ------------------------------------
    # Per-section generation nodes
    # ------------------------------------

    def generate_key_concerns(state: "ExternalAgentState") -> Command:
        runtime, writer, messages = _get_ctx(state)

        decision = state.get("hitl_decision")
        hitl_artifact = state.get("hitl_artifact") or {}
        feedback = decision.task_summary if decision and decision.intent == "feedback" else ""
        selected_sections = state.get("selected_sections", []) or []

        # --- Accept path: persist and move to next section ---
        if decision and decision.intent == "accept":
            if isinstance(hitl_artifact, KeyConcernSet):
                accepted = hitl_artifact
            elif hitl_artifact and isinstance(hitl_artifact, dict):
                try:
                    accepted = KeyConcernSet(**hitl_artifact)
                except Exception:
                    accepted = state.get("key_concerns")
            else:
                accepted = state.get("key_concerns")

            goto = _next_section("key_concerns", selected_sections)
            return Command(
                goto=goto,
                update={
                    "key_concerns": accepted,
                    "hitl_decision": None,
                    "hitl_artifact": None,
                    "pending_step": None,
                    "messages": messages + [AIMessage("Key concerns accepted.")],
                },
            )

        initial_review = state.get("initial_review", "")
        additional_info = state.get("additional_info", "")
        system_prompt = EXTERNAL_AGENT_SYSTEM_PROMPT
        parser = PydanticOutputParser(pydantic_object=KeyConcernSet)

        # --- Feedback path: regenerate from previous output + feedback ---
        if feedback:
            prev_output = state.get("key_concerns")
            prev_version_json = prev_output.model_dump_json(indent=2, exclude_none=True) if prev_output else "{}"

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Revising key concerns based on feedback..."))

            prompt = SECTION_FEEDBACK_PROMPT.format(
                section_name="key concerns",
                prev_version=prev_version_json,
                feedback=feedback,
                initial_review=initial_review,
                additional_info=additional_info,
                knowledge_block="",
                format=parser.get_format_instructions(),
            )
        else:
            # --- Draft path: generate from scratch ---
            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Drafting key concerns..."))

            prompt = KEY_CONCERNS_DRAFT_PROMPT.format(
                initial_review=initial_review,
                additional_info=additional_info,
                format=parser.get_format_instructions(),
            )

        prompts = [SystemMessage(content=system_prompt),
                   HumanMessage(content=prompt)]

        response = llm.invoke(
            input=prompts,
            temperature=0.0,
            max_tokens=15104,
            response_format={"type": "json_object"},
        )
        content = response.content if isinstance(
            response.content, str) else response.content[0]["text"]
        parsed: KeyConcernSet = parser.parse(content)

        # Send to HITL review
        artifact = build_form_key_concerns(parsed)
        text = "Key concerns drafted. Please review and provide feedback or accept."
        hitl_task = prepare_hitl_task(
            agent_name=EXTERNAL_AGENT_NAME,
            text=text,
            context="User must review key concerns and either accept, edit+submit, or provide feedback.",
            state={} if use_checkpointer else {
                **state, "messages": messages + [AIMessage(text)]},
            artifact=artifact,
        )

        return Command(
            goto="route_interrupt",
            update={
                "key_concerns": parsed,
                "pending_step": "key_concerns_review",
                "hitl_task": hitl_task,
                "hitl_decision": None,
                "hitl_artifact": None,
                "messages": messages + [AIMessage("Key concerns drafted. Awaiting review.")],
            },
        )

    async def generate_doc_request_async(state: "ExternalAgentState") -> Command:
        runtime, writer, messages = _get_ctx(state)

        decision = state.get("hitl_decision")
        hitl_artifact = state.get("hitl_artifact") or {}
        feedback = decision.task_summary if decision and decision.intent == "feedback" else ""
        selected_sections = state.get("selected_sections", []) or []

        # --- Accept path ---
        if decision and decision.intent == "accept":
            if isinstance(hitl_artifact, DocRequestSet):
                accepted = hitl_artifact
            elif hitl_artifact and isinstance(hitl_artifact, dict):
                try:
                    accepted = DocRequestSet(**hitl_artifact)
                except Exception:
                    accepted = state.get("doc_request")
            else:
                accepted = state.get("doc_request")

            goto = _next_section("doc_request", selected_sections)
            return Command(
                goto=goto,
                update={
                    "doc_request": accepted,
                    "hitl_decision": None,
                    "hitl_artifact": None,
                    "pending_step": None,
                    "messages": messages + [AIMessage("Document requests accepted.")],
                },
            )

        initial_review = state.get("initial_review", "")
        additional_info = state.get("additional_info", "")
        system_prompt = EXTERNAL_AGENT_SYSTEM_PROMPT
        parser = PydanticOutputParser(pydantic_object=DocRequestSet)
        knowledge_json = None

        # --- Feedback path ---
        if feedback:
            prev_output = state.get("doc_request")
            prev_version_json = prev_output.model_dump_json(indent=2, exclude_none=True) if prev_output else "{}"

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Revising document requests based on feedback..."))

            # Reuse cached knowledge from draft path
            cached_knowledge = state.get("doc_request_knowledge") or ""
            knowledge_block = SECTION_FEEDBACK_KNOWLEDGE_BLOCK.format(knowledge=cached_knowledge) if cached_knowledge else ""

            prompt = SECTION_FEEDBACK_PROMPT.format(
                section_name="document requests",
                prev_version=prev_version_json,
                feedback=feedback,
                initial_review=initial_review,
                additional_info=additional_info,
                knowledge_block=knowledge_block,
                format=parser.get_format_instructions(),
            )
        else:
            # --- Draft path (existing logic) ---
            knowledge_endpoint = runtime.context["resources_endpoint_name"]

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Retrieving knowledge for document requests..."))

            raw_knowledge = await _retrieve_section_knowledge(
                task_key="doc_requests",
                task_def=RETRIEVAL_TASKS["doc_requests"],
                state=state,
                knowledge_endpoint=knowledge_endpoint,
            )

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Synthesising document request knowledge..."))

            investigation_types = state.get("investigation_type", []) or []
            synthesized = _synthesize_section_knowledge(
                section_name="document requests",
                knowledge_set=raw_knowledge,
                investigation_types=investigation_types,
                output_schema=DocRequestSet,
            )

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Drafting document requests..."))

            knowledge_json = synthesized.model_dump_json(indent=2, exclude_none=True)
            prompt = DOC_REQUEST_DRAFT_PROMPT.format(
                initial_review=initial_review,
                knowledge=knowledge_json,
                format=parser.get_format_instructions(),
            )

        prompts = [SystemMessage(content=system_prompt),
                   HumanMessage(content=prompt)]

        response = llm.invoke(
            input=prompts,
            temperature=0.0,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )
        content = response.content if isinstance(
            response.content, str) else response.content[0]["text"]
        parsed: DocRequestSet = parser.parse(content)

        # Send to HITL review
        artifact = build_form_doc_request(parsed)
        text = "Document requests drafted. Please review and provide feedback or accept."
        hitl_task = prepare_hitl_task(
            agent_name=EXTERNAL_AGENT_NAME,
            text=text,
            context="User must review document requests and either accept, edit+submit, or provide feedback.",
            state={} if use_checkpointer else {
                **state, "messages": messages + [AIMessage(text)]},
            artifact=artifact,
        )

        update = {
            "doc_request": parsed,
            "pending_step": "doc_request_review",
            "hitl_task": hitl_task,
            "hitl_decision": None,
            "hitl_artifact": None,
            "messages": messages + [AIMessage("Document requests drafted. Awaiting review.")],
        }
        # Cache knowledge on first draft for feedback reuse
        if knowledge_json is not None:
            update["doc_request_knowledge"] = knowledge_json

        return Command(goto="route_interrupt", update=update)

    def generate_doc_request(state: "ExternalAgentState") -> Command:
        """Sync wrapper for generate_doc_request_async."""
        try:
            return asyncio.run(generate_doc_request_async(state))
        except RuntimeError:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(generate_doc_request_async(state))

    async def generate_enquiries_async(state: "ExternalAgentState") -> Command:
        runtime, writer, messages = _get_ctx(state)

        decision = state.get("hitl_decision")
        hitl_artifact = state.get("hitl_artifact") or {}
        feedback = decision.task_summary if decision and decision.intent == "feedback" else ""
        selected_sections = state.get("selected_sections", []) or []

        # --- Accept path ---
        if decision and decision.intent == "accept":
            if isinstance(hitl_artifact, AdditionalEnquiriesSet):
                accepted = hitl_artifact
            elif hitl_artifact and isinstance(hitl_artifact, dict):
                try:
                    accepted = AdditionalEnquiriesSet(**hitl_artifact)
                except Exception:
                    accepted = state.get("additional_enquiries")
            else:
                accepted = state.get("additional_enquiries")

            goto = _next_section("additional_enquiries", selected_sections)
            return Command(
                goto=goto,
                update={
                    "additional_enquiries": accepted,
                    "hitl_decision": None,
                    "hitl_artifact": None,
                    "pending_step": None,
                    "messages": messages + [AIMessage("Additional enquiries accepted.")],
                },
            )

        initial_review = state.get("initial_review", "")
        additional_info = state.get("additional_info", "")
        system_prompt = EXTERNAL_AGENT_SYSTEM_PROMPT
        parser = PydanticOutputParser(pydantic_object=AdditionalEnquiriesSet)
        knowledge_json = None

        # --- Feedback path ---
        if feedback:
            prev_output = state.get("additional_enquiries")
            prev_version_json = prev_output.model_dump_json(indent=2, exclude_none=True) if prev_output else "{}"

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Revising additional enquiries based on feedback..."))

            cached_knowledge = state.get("enquiries_knowledge") or ""
            knowledge_block = SECTION_FEEDBACK_KNOWLEDGE_BLOCK.format(knowledge=cached_knowledge) if cached_knowledge else ""

            prompt = SECTION_FEEDBACK_PROMPT.format(
                section_name="additional enquiries",
                prev_version=prev_version_json,
                feedback=feedback,
                initial_review=initial_review,
                additional_info=additional_info,
                knowledge_block=knowledge_block,
                format=parser.get_format_instructions(),
            )
        else:
            # --- Draft path (existing logic) ---
            knowledge_endpoint = runtime.context["resources_endpoint_name"]

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Retrieving knowledge for additional enquiries..."))

            raw_knowledge = await _retrieve_section_knowledge(
                task_key="additional_enquiries",
                task_def=RETRIEVAL_TASKS["additional_enquiries"],
                state=state,
                knowledge_endpoint=knowledge_endpoint,
            )

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Synthesising additional enquiries knowledge..."))

            investigation_types = state.get("investigation_type", []) or []
            synthesized = _synthesize_section_knowledge(
                section_name="additional enquiries",
                knowledge_set=raw_knowledge,
                investigation_types=investigation_types,
                output_schema=AdditionalEnquiriesSet,
            )

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Drafting additional enquiries..."))

            knowledge_json = synthesized.model_dump_json(indent=2, exclude_none=True)
            prompt = ADDITIONAL_ENQUIRIES_DRAFT_PROMPT.format(
                initial_review=initial_review,
                knowledge=knowledge_json,
                format=parser.get_format_instructions(),
            )

        prompts = [SystemMessage(content=system_prompt),
                   HumanMessage(content=prompt)]

        response = llm.invoke(
            input=prompts,
            temperature=0.0,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )
        content = response.content if isinstance(
            response.content, str) else response.content[0]["text"]
        parsed: AdditionalEnquiriesSet = parser.parse(content)

        # Send to HITL review
        artifact = build_form_enquiries(parsed)
        text = "Additional enquiries drafted. Please review and provide feedback or accept."
        hitl_task = prepare_hitl_task(
            agent_name=EXTERNAL_AGENT_NAME,
            text=text,
            context="User must review additional enquiries and either accept, edit+submit, or provide feedback.",
            state={} if use_checkpointer else {
                **state, "messages": messages + [AIMessage(text)]},
            artifact=artifact,
        )

        update = {
            "additional_enquiries": parsed,
            "pending_step": "enquiries_review",
            "hitl_task": hitl_task,
            "hitl_decision": None,
            "hitl_artifact": None,
            "messages": messages + [AIMessage("Additional enquiries drafted. Awaiting review.")],
        }
        if knowledge_json is not None:
            update["enquiries_knowledge"] = knowledge_json

        return Command(goto="route_interrupt", update=update)

    def generate_enquiries(state: "ExternalAgentState") -> Command:
        """Sync wrapper for generate_enquiries_async."""
        try:
            return asyncio.run(generate_enquiries_async(state))
        except RuntimeError:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(generate_enquiries_async(state))

    async def generate_interview_plan_async(state: "ExternalAgentState") -> Command:
        runtime, writer, messages = _get_ctx(state)

        decision = state.get("hitl_decision")
        hitl_artifact = state.get("hitl_artifact") or {}
        feedback = decision.task_summary if decision and decision.intent == "feedback" else ""

        # --- Accept path (interview_plan is always last → assemble_plan) ---
        if decision and decision.intent == "accept":
            if isinstance(hitl_artifact, InterviewQuestionSets):
                accepted = hitl_artifact
            elif hitl_artifact and isinstance(hitl_artifact, dict):
                try:
                    accepted = InterviewQuestionSets(**hitl_artifact)
                except Exception:
                    accepted = state.get("interview_plan")
            else:
                accepted = state.get("interview_plan")

            return Command(
                goto="assemble_plan",
                update={
                    "interview_plan": accepted,
                    "hitl_decision": None,
                    "hitl_artifact": None,
                    "pending_step": None,
                    "messages": messages + [AIMessage("Interview plan accepted.")],
                },
            )

        initial_review = state.get("initial_review", "")
        additional_info = state.get("additional_info", "")
        system_prompt = EXTERNAL_AGENT_SYSTEM_PROMPT
        parser = PydanticOutputParser(pydantic_object=InterviewQuestionSets)
        knowledge_json = None

        # --- Feedback path ---
        if feedback:
            prev_output = state.get("interview_plan")
            prev_version_json = prev_output.model_dump_json(indent=2, exclude_none=True) if prev_output else "{}"

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Revising interview plan based on feedback..."))

            cached_knowledge = state.get("interview_plan_knowledge") or ""
            knowledge_block = SECTION_FEEDBACK_KNOWLEDGE_BLOCK.format(knowledge=cached_knowledge) if cached_knowledge else ""

            prompt = SECTION_FEEDBACK_PROMPT.format(
                section_name="interview plan",
                prev_version=prev_version_json,
                feedback=feedback,
                initial_review=initial_review,
                additional_info=additional_info,
                knowledge_block=knowledge_block,
                format=parser.get_format_instructions(),
            )
        else:
            # --- Draft path (existing logic) ---
            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Retrieving knowledge for interview plan..."))

            # NOTE: interview plan retrieval tasks are currently commented out in RETRIEVAL_TASKS.
            # When ready, uncomment "question_categories" and "underwriting_financial" in knowledge_prompts.py.
            task_key = "interview_plan"
            task_def = RETRIEVAL_TASKS.get(task_key)
            if not task_def:
                writer(prepare_thinking_message(
                    EXTERNAL_AGENT_NAME, "No retrieval task configured for interview plan, drafting from initial review..."))
                raw_knowledge = KnowledgeSet(knowledge=[])
            else:
                knowledge_endpoint = runtime.context["resources_endpoint_name"]
                raw_knowledge = await _retrieve_section_knowledge(
                    task_key=task_key,
                    task_def=task_def,
                    state=state,
                    knowledge_endpoint=knowledge_endpoint,
                )

            investigation_types = state.get("investigation_type", []) or []
            if raw_knowledge.knowledge:
                writer(prepare_thinking_message(
                    EXTERNAL_AGENT_NAME, "Synthesising interview plan knowledge..."))

                synthesized = _synthesize_section_knowledge(
                    section_name="interview plan",
                    knowledge_set=raw_knowledge,
                    investigation_types=investigation_types,
                    output_schema=InterviewQuestionSets,
                )
                knowledge_json = synthesized.model_dump_json(indent=2, exclude_none=True)
            else:
                knowledge_json = ""

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Drafting interview plan..."))

            prompt = INTERVIEW_PLAN_DRAFT_PROMPT.format(
                initial_review=initial_review,
                knowledge=knowledge_json,
                format=parser.get_format_instructions(),
            )

        prompts = [SystemMessage(content=system_prompt),
                   HumanMessage(content=prompt)]

        response = llm.invoke(
            input=prompts,
            temperature=0.0,
            max_tokens=8192,
            response_format={"type": "json_object"},
        )
        content = response.content if isinstance(
            response.content, str) else response.content[0]["text"]
        parsed: InterviewQuestionSets = parser.parse(content)

        # Send to HITL review
        artifact = build_form_interview_plan(parsed)
        text = "Interview plan drafted. Please review and provide feedback or accept."
        hitl_task = prepare_hitl_task(
            agent_name=EXTERNAL_AGENT_NAME,
            text=text,
            context="User must review interview plan and either accept, edit+submit, or provide feedback.",
            state={} if use_checkpointer else {
                **state, "messages": messages + [AIMessage(text)]},
            artifact=artifact,
        )

        update = {
            "interview_plan": parsed,
            "pending_step": "interview_plan_review",
            "hitl_task": hitl_task,
            "hitl_decision": None,
            "hitl_artifact": None,
            "messages": messages + [AIMessage("Interview plan drafted. Awaiting review.")],
        }
        if knowledge_json is not None:
            update["interview_plan_knowledge"] = knowledge_json

        return Command(goto="route_interrupt", update=update)

    def generate_interview_plan(state: "ExternalAgentState") -> Command:
        """Sync wrapper for generate_interview_plan_async."""
        try:
            return asyncio.run(generate_interview_plan_async(state))
        except RuntimeError:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(generate_interview_plan_async(state))

    # --- Commented out: replaced by per-section generate nodes ---
    # def generate_plan(state: "ExternalAgentState") -> Command:
    #     runtime, writer, messages = _get_ctx(state)
    #
    #     decision = state.get("hitl_decision")
    #     hitl_artifact = state.get("hitl_artifact") or {}
    #     hitl_feedback = decision.task_summary if decision and decision.intent == "feedback" else ""
    #
    #     # Accept => persist edited plan and proceed to finalise
    #     if decision and decision.intent == "accept" and hitl_artifact:
    #         interview_plan = hitl_artifact
    #         return Command(
    #             goto="finalise_plan",
    #             update={
    #                 "interview_plans": interview_plan,
    #                 "messages": messages + [AIMessage("Interview plan accepted.")],
    #                 "pending_step": None,
    #                 "hitl_artifact": None,
    #             },
    #         )
    #
    #     initial_review = state.get("initial_review", "")
    #     additional_info = state.get("additional_info", "")
    #     knowledge_report = state.get("knowledge")
    #     doc_knowledge_json = knowledge_report.model_dump_json(indent=2, exclude_none=True, include={"document_set"})
    #     enquiry_knowledge_json = knowledge_report.model_dump_json(indent=2, exclude_none=True, include={"enquiries_rationale"})
    #
    #     prev_plan = state.get("interview_plans") or {}
    #     prev_version = getattr(prev_plan, "version", None)
    #     if prev_version is None and isinstance(prev_plan, dict):
    #         prev_version = prev_plan.get("version", 0)
    #     version = prev_version + 1
    #
    #     online_feedback = state.get("online_eval", {}).get("per_metric", [])
    #     online_feedback_block = (
    #         "\n\n".join(f"Metric: {f['metric_id']} \nSuggestions: {f['suggestions']}" for f in online_feedback)
    #         if online_feedback else ""
    #     )
    #     feedback = (hitl_feedback).strip()
    #
    #     system_prompt = EXTERNAL_AGENT_SYSTEM_PROMPT
    #
    #     if feedback:
    #         # feedback path
    #         pass
    #     else:
    #         # draft path — key concerns, doc request, additional enquiries sequentially
    #         pass
    #
    #     return Command(goto="online_evaluation", update={...})

    # ------------------------------------
    # Assembly and finalisation nodes
    # ------------------------------------

    def assemble_plan(state: "ExternalAgentState") -> Command:
        """Collect per-section outputs and assemble ExternalAgentPlan."""
        writer: StreamWriter = get_stream_writer()
        messages = state.get("messages", [])

        writer(prepare_thinking_message(
            EXTERNAL_AGENT_NAME, "Assembling external agent plan..."))

        key_concerns = state.get("key_concerns")
        doc_request = state.get("doc_request")
        additional_enquiries = state.get("additional_enquiries")
        # interview_plan = state.get("interview_plan")

        plan = ExternalAgentPlan(
            concern_set=key_concerns if key_concerns else KeyConcernSet(concern_set=[]),
            document_set=doc_request if doc_request else DocRequestSet(document_set=[]),
            enquiry_set=additional_enquiries if additional_enquiries else AdditionalEnquiriesSet(enquiries_set=[]),
            # interview_plan=interview_plan,
            version=1,
            created_at=datetime.utcnow().isoformat(),
            update_notes=None,
        )

        return Command(
            goto="finalise_plan",
            update={
                "external_agent_plan": plan,
                "messages": messages + [AIMessage("External agent plan assembled.")],
            },
        )

    def finalise_plan(state: "ExternalAgentState") -> Command:
        writer: StreamWriter = get_stream_writer()
        messages = state.get("messages", [])

        custom_message = prepare_thinking_message(
            EXTERNAL_AGENT_NAME, "Finalising instructions for external agent...")
        writer(custom_message)

        final_plan = state.get("external_agent_plan")
        claim_id = state.get("claim_id")

        artifact = build_form_final(claim_id, final_plan) if final_plan else {}

        return Command(
            update={
                "messages": messages + [AIMessage("Final external agent instructions submitted.")],
                "artifact": artifact,
                "pending_step": None,
            }
        )

    # ------------------------------------
    # Routing
    # ------------------------------------

    # ------------------------------------
    # Graph
    # ------------------------------------

    graph = (
        StateGraph(ExternalAgentState)
        .add_node("initialise_query", initialise_query)
        .add_node("dispatch_sections", dispatch_sections)
        .add_node("generate_key_concerns", generate_key_concerns)
        .add_node("generate_doc_request", generate_doc_request)
        .add_node("generate_enquiries", generate_enquiries)
        .add_node("generate_interview_plan", generate_interview_plan)
        .add_node("assemble_plan", assemble_plan)
        .add_node("finalise_plan", finalise_plan)
        .add_node("route_interrupt", route_interrupt)
        .add_edge(START, "initialise_query")
        .add_edge("dispatch_sections", "generate_key_concerns")
        .add_edge("assemble_plan", "finalise_plan")
        .add_edge("finalise_plan", END)
    )

    return graph
