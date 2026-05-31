from typing import List, TypedDict, Optional, Annotated, Union, Any, Literal, Tuple, Dict
from smart_investigator.foundation.schemas.schemas import SmartInvestigatorAgentState, SIErrorCode
from smart_investigator.foundation.tools.tool_names import EXTERNAL_AGENT_NAME
from agents.external_agent.prompt_manager.knowledge_prompts import (
    KNOWLEDGE_RETRIEVAL_SYSTEM_PROMPT,
    RETRIEVAL_TASKS,
    KNOWLEDGE_RETRIEVAL_TASK_PROMPT,
    SECTION_KNOWLEDGE_REPORT_SYSTEM_PROMPT,
    SECTION_KNOWLEDGE_REPORT_PROMPT,
    DOC_REQUEST_PARSER_SYSTEM_PROMPT,
    DOC_REQUEST_PARSER_PROMPT,
    ENQUIRIES_PARSER_SYSTEM_PROMPT,
    ENQUIRIES_PARSER_PROMPT,
    DEDUP_PROMPT,
)
from agents.external_agent.prompt_manager.external_agent_prompts import (
    EXTERNAL_AGENT_SYSTEM_PROMPT,
    KEY_CONCERNS_DRAFT_PROMPT,
    DOC_REQUEST_RELEVANCE_PROMPT,
    DOC_REQUEST_SME_PROMPT,
    NARRATIVE_DOC_REQUEST_DRAFT_PROMPT,
    ADDITIONAL_ENQUIRIES_RELEVANCE_PROMPT,
    ADDITIONAL_ENQUIRIES_FINAL_PROMPT,
    INTERVIEW_PLAN_DRAFT_PROMPT,
    SECTION_FEEDBACK_PROMPT,
    SECTION_FEEDBACK_KNOWLEDGE_BLOCK,
)
from agents.external_agent.prompt_manager.standards import (
    MOTOR_DOC_REQUEST_GOLD_STANDARDS,
    MOTOR_DOC_REQUEST_GOLD_STANDARDS_BLOCK,
    PROPERTY_DOC_REQUEST_GOLD_STANDARDS,
    PROPERTY_DOC_REQUEST_GOLD_STANDARDS_BLOCK,
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

# ---------------------------------------------------------------------------
# Hard-exclusion pre-filter: strips methodology doc types that have no
# factual hook in case facts, before the LLM ever sees them.
#
# Each hook keyword is compiled as a case-insensitive word-boundary regex
# to prevent false matches (e.g. "work" matching "WorkBench").
# ---------------------------------------------------------------------------
import re as _re

_HARD_EXCLUSIONS = {
    # doc_type pattern → hook keywords (word-boundary regexes)
    "work roster":       [r"work roster", r"time sheet", r"shift work",
                          r"clock in", r"clock out", r"on duty"],
    "timesheet":         [r"work roster", r"time sheet", r"shift work",
                          r"clock in", r"clock out", r"on duty"],
    "insurance history": [r"other insurer", r"external claims?",
                          r"claims? ?made ?outside", r"outside of suncorp",
                          r"lodged a claim with"],
    "claims history":    [r"other insurer", r"external claims?",
                          r"claims? ?made ?outside", r"outside of suncorp",
                          r"lodged a claim with"],
    "criminal history":  [r"criminal", r"offen[dc]er?", r"convict(?:ed|ion)",
                           r"arrest(?:ed)?"],
    "background check":  [r"criminal", r"offen[dc]er?", r"convict(?:ed|ion)",
                           r"charg(?:ed?|ing)", r"police", r"arrest(?:ed)?"],
    "medical certificate": [r"injur", r"hospital", r"medical treat", r"admission",
                            r"surger", r"doctor", r"ambulance", r"mental health"],
    "hospital":           [r"hospitali[sz]", r"admission", r"injur",
                            r"ambulance", r"surger"],
    "medical records":     [r"injur", r"hospital", r"medical treat", r"admission",
                            r"surger", r"doctor", r"ambulance", r"mental health"],
    "rideshare":         [r"rideshare", r"taxi", r"\buber\b", r"\bdidi\b",
                          r"\bbolt\b", r"\bola\b"],
    "taxi":              [r"rideshare", r"taxi", r"\buber\b", r"\bdidi\b",
                          r"\bbolt\b", r"\bola\b"],
    "transport receipt": [r"rideshare", r"taxi", r"\buber\b", r"\bdidi\b",
                          r"\bbolt\b", r"\bola\b"],
    "toll":              [r"\btoll\b", r"\bmotorway\b", r"\bexpressway\b",
                          r"\btollway\b"],
    "tenancy":           [r"\btenant\b", r"\btenancy\b", r"\brental\b",
                          r"\blease\b", r"\blandlord\b"],
    "contract of sale":  [r"contract of sale", r"\bconveyanc", r"\bsettlement\b",
                          r"\bpurchaser\b", r"\bvendor\b"],
}

# Pre-compile hook patterns for each exclusion group
_HOOK_REGEXES = {
    group: [_re.compile(patt, _re.IGNORECASE) for patt in patterns]
    for group, patterns in _HARD_EXCLUSIONS.items()
}

_CATCH_ALL_MARKERS = [
    "any other document",
    "other documents",
    "other supporting",
]


def _has_hook(case_text: str, group: str) -> bool:
    """Check if any hook regex for `group` finds a match in case_text."""
    regexes = _HOOK_REGEXES.get(group, [])
    if not regexes:
        return False
    case_lower = case_text.lower()
    return any(rgx.search(case_lower) for rgx in regexes)


def _is_catch_all(doc_type: str) -> bool:
    doc_lower = doc_type.lower()
    return any(marker in doc_lower for marker in _CATCH_ALL_MARKERS)


def _doc_type_is_excludable(doc_type: str, case_text: str) -> bool:
    """Return True if doc_type matches a hard exclusion with no hook."""
    doc_lower = doc_type.lower()
    if "signed authorit" in doc_lower:
        return False
    for pattern in _HARD_EXCLUSIONS:
        if pattern in doc_lower:
            if not _has_hook(case_text, pattern):
                return True
            return False
    return False


def _split_sub_items(text: str) -> list:
    if ";" in text:
        return [s.strip() for s in text.split(";") if s.strip()]
    if "\n-" in text or "\n•" in text:
        parts = []
        for line in text.split("\n"):
            stripped = line.lstrip("-• \t")
            if stripped:
                parts.append(stripped)
        return parts
    return [text]


def _filter_doc_details(doc_details: str, case_text: str) -> str:
    sub_items = _split_sub_items(doc_details)
    if len(sub_items) <= 1:
        return doc_details
    kept = []
    for item in sub_items:
        if not _doc_type_is_excludable(item, case_text):
            kept.append(item)
    if not kept:
        return ""
    if ";" in doc_details:
        return "; ".join(kept)
    if "\n" in doc_details:
        return "\n".join(kept)
    return ", ".join(kept)


def strip_hard_exclusions(doc_list_data: dict, initial_review: str,
                          additional_info: str) -> dict:
    docs = doc_list_data.get("document_set", [])
    case_text = f"{initial_review or ''} {additional_info or ''}"
    result = []
    stripped = []
    for doc in docs:
        doc_type = doc.get("doc_type", "")
        if _doc_type_is_excludable(doc_type, case_text):
            stripped.append(doc_type)
            continue
        doc_details = doc.get("doc_details", "")
        if _is_catch_all(doc_type) and doc_details:
            cleaned = _filter_doc_details(doc_details, case_text)
            if not cleaned.strip():
                stripped.append(f"{doc_type} [all sub-items filtered]")
                continue
            for item in _split_sub_items(cleaned):
                result.append({"doc_type": item, "doc_details": item})
            continue
        if doc_details:
            cleaned = _filter_doc_details(doc_details, case_text)
            if cleaned != doc_details:
                doc["doc_details"] = cleaned
        result.append(doc)
    if stripped:
        logger.info("Hard-exclusion pre-filter stripped %d doc types: %s",
                      len(stripped), stripped)
    doc_list_data["document_set"] = result
    return doc_list_data


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
        - "accept": user accepts OR the artifact has been provided back with no human response text OR the artifact's reviewed section came back empty AND the user's text declines to add anything (e.g. "no", "no need", "skip", "nothing to add", "leave empty", "that's fine").
        - "feedback": user gives feedback that mentions which section, concern, document, enquiry, or item the change applies to — even loosely (e.g. "change John to Jerry in phone records" names a section, so apply it everywhere within that section).
        - "ambiguous": user gives feedback with no indication of WHERE to apply it — no section, no item, no context clue (e.g. "change the date from 22 Apr to 25 May" gives no location). In this case, write a clarifying question in task_summary asking the user which section or item they want updated.
        - "unrelated": user asks something unrelated.

        Summarise the task:
        - If the intent is "unrelated" or there is no human response text, leave task_summary as "".
        - If the intent is "ambiguous", write a short clarifying question asking the user to specify exactly where they want the change applied. Do NOT start with "Task: ".
        - Otherwise, write a short paragraph that states the next task. Start with "Task: ".

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
        Resolve the FE-submitted form payload into a canonical section object.

        Parses on both accept and feedback: even when the user provides text
        feedback, FE-side edits (NA-drops, in-form changes) must be merged into
        the previous version so downstream regeneration sees what's on screen.

        Falls back to the previous state value when no artifact is sent or parsing
        produces empty/invalid output.
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
            # Parse on accept and feedback so FE edits/NA-drops survive into state.
            if incoming_artifact and intent in ("accept", "feedback"):
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
                        _, writer, _ = _get_ctx(state)
                        writer(prepare_thinking_message(
                            EXTERNAL_AGENT_NAME,
                            f"Parsed artifact for {pending_step} returned empty result — falling back to previous content."))
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

    # ------------------------------------
    # Chunk-based per-section retrieval (delta-table path)
    # ------------------------------------

    # Maps the item_key arg to the Pydantic schema attribute that holds the
    # list of items, and the field on each item used as its dedup text.
    _SECTION_META = {
        "doc_list": {"items_attr": "document_set", "text_field": "doc_type"},
        "enquiry_list": {"items_attr": "enquiries_set", "text_field": "enquiry"},
    }

    _DEFAULT_STAGE_BY_SECTION = {
        "doc_request": "document request",
        "additional_enquiries": "additional enquiries",
    }

    # SME-driven overrides: certain (lob, fraud_type) combinations file their
    # textbook content under non-default stages. Keys use lowercased fraud_type
    # for case-insensitive matching. Sections not listed fall back to the
    # default stage above.
    _STAGE_OVERRIDES: dict[tuple[str, str], dict[str, str]] = {
        ("Property", "policy exclusions: escape of liquid"): {
            "doc_request": "interviews",
        },
        ("Property", "policy exclusions: deliberate/reckless"): {
            "doc_request": "ea appointment",
            "additional_enquiries": "ea appointment",
        },
        ("Motor", "dui"): {
            "additional_enquiries": "external agent appointment",
        },
        ("Motor", "reckless"): {
            "doc_request": "external agent appointment",
            "additional_enquiries": "external agent appointment",
        },
        ("Motor", "motor sports"): {
            "doc_request": "external agent appointment",
            "additional_enquiries": "external agent appointment",
        },
    }

    def _resolve_stage(lob: str, fraud_type: str, section: str) -> str:
        override = _STAGE_OVERRIDES.get((lob, fraud_type.lower()), {})
        return override.get(section, _DEFAULT_STAGE_BY_SECTION[section])

    async def _retrieve_section_chunks_async(
        state: "ExternalAgentState",
        *,
        section: str,
        parser_system_prompt: str,
        parser_prompt_template: str,
        output_schema,
        item_key: str,
        skip_on_empty: bool = False,
    ) -> tuple[list[dict], list[str]]:
        """
        Chunk-based retrieval for sections sourced from the textbook delta table
        (doc_request, additional_enquiries).

        For each investigation_type:
          1. Resolve the textbook stage for (lob, fraud_type, section) — defaults
             come from `_DEFAULT_STAGE_BY_SECTION`, with SME-driven overrides in
             `_STAGE_OVERRIDES` (e.g. Motor DUI's additional_enquiries lives
             under "external agent appointment", not "additional enquiries").
          2. Filter `df` by lob + fraud_type + resolved stage.
          3. Concatenate chunk_data → combined_chunks.
          4. LLM-parse combined_chunks into `output_schema`.
          5. Append {"investigation_type": <inv_type>, item_key: <parsed>} to knowledge_output.

        When multiple investigation_types are selected, run DEDUP_PROMPT across the
        combined item set and strip duplicates (cross-set only).

        When `skip_on_empty=True`, inv_types with no matching chunks are appended
        to the returned skipped list instead of raising — letting the caller emit
        a user-facing message for those inv_types and continue with whatever
        knowledge was retrieved for the rest.

        Returns:
          (knowledge_output, skipped_inv_types) — `knowledge_output` is the list of
          per-inv_type parsed entries; `skipped_inv_types` is the list of inv_types
          that had no chunks (only populated when `skip_on_empty=True`).

        Raises:
          ValueError: when state lacks lob/investigation_type, when no chunks match
                      a (lob, fraud_type, stage) combination and `skip_on_empty` is
                      False, or when dedup fails.
        """
        lob = state.get("lob", "")
        investigation_types = state.get("investigation_type", []) or []
        if not investigation_types or not lob:
            raise ValueError(
                f"lob or investigation_type has not been passed in state: {state}")

        meta = _SECTION_META[item_key]
        items_attr = meta["items_attr"]
        text_field = meta["text_field"]

        parser = PydanticOutputParser(pydantic_object=output_schema)
        knowledge_output: list[dict] = []
        skipped_inv_types: list[str] = []

        for inv_type in investigation_types:
            fraud_type = inv_type.split("|", 1)[0].strip()
            stage = _resolve_stage(lob, fraud_type, section)
            filtered_df = df[
                (df["lob"] == lob) &
                (df["fraud_type"] == fraud_type) &
                (df["stage"].apply(lambda stages: stage in stages))
            ].copy()

            if filtered_df.empty:
                if skip_on_empty:
                    skipped_inv_types.append(inv_type)
                    continue
                raise ValueError(
                    f"No textbook information found for lob={lob}, "
                    f"fraud_type={fraud_type}, stage={stage}"
                )

            chunks = filtered_df["chunk_data"].dropna().tolist()
            combined_chunks = "\n\n".join(chunks)

            parser_prompts = [
                SystemMessage(content=parser_system_prompt),
                HumanMessage(content=parser_prompt_template.format(
                    investigation_type=inv_type,
                    chunks=combined_chunks,
                    format=parser.get_format_instructions(),
                )),
            ]

            parser_response = await asyncio.to_thread(
                llm.invoke,
                input=parser_prompts,
                temperature=0.0,
                max_tokens=16384,
                response_format={"type": "json_object"},
            )
            content = parser_response.content if isinstance(
                parser_response.content, str) else parser_response.content[0]["text"]
            parsed = parser.parse(content)

            # Chunks existed but the LLM parser yielded no items for this
            # inv_type (commonly because the sub-type filter inside the parser
            # prompt found nothing applicable). Treat the same as no-chunks.
            if not getattr(parsed, items_attr):
                if skip_on_empty:
                    skipped_inv_types.append(inv_type)
                    continue
                raise ValueError(
                    f"Parser produced empty {items_attr} for lob={lob}, "
                    f"fraud_type={fraud_type}, stage={stage}, inv_type={inv_type}"
                )

            knowledge_output.append({
                "investigation_type": inv_type,
                item_key: parsed,
            })

        if len(knowledge_output) > 1:
            _dedup_section_items(
                knowledge_output,
                item_key=item_key,
                items_attr=items_attr,
                text_field=text_field,
                item_type_label=_DEFAULT_STAGE_BY_SECTION[section],
            )

        return knowledge_output, skipped_inv_types

    def _dedup_section_items(
        knowledge_output: list[dict],
        *,
        item_key: str,
        items_attr: str,
        text_field: str,
        item_type_label: str,
    ) -> None:
        """
        Run DEDUP_PROMPT over items across investigation-type sets and remove
        duplicates (cross-set only). Mutates each set's items list in-place.

        Raises on LLM failure or unparseable response.
        """
        id_to_item_set: dict[str, str] = {}
        formatted_blocks: list[str] = []

        for set_idx, knowledge_item in enumerate(knowledge_output):
            set_id = f"S{set_idx + 1:03d}"
            items = getattr(knowledge_item[item_key], items_attr)
            prompt_items = []
            for item_idx, item in enumerate(items):
                iid = f"{set_id}_I{item_idx + 1:03d}"
                id_to_item_set[iid] = set_id
                prompt_items.append({
                    "item_id": iid,
                    "item_set_id": set_id,
                    "text": getattr(item, text_field),
                })
            formatted_blocks.append(
                f"### SET: {set_id}\n" + json.dumps(prompt_items, indent=2)
            )

        dedup_prompt = DEDUP_PROMPT.format(
            item_type=item_type_label,
            items="\n\n".join(formatted_blocks),
        )

        dedup_response = llm.invoke(
            input=[HumanMessage(content=dedup_prompt)],
            temperature=0.0,
            max_tokens=16384,
            response_format={"type": "json_object"},
        )
        dedup_content = dedup_response.content if isinstance(
            dedup_response.content, str) else dedup_response.content[0]["text"]
        dedup_result = json.loads(dedup_content)

        duplicate_ids: set[str] = set()
        for group in dedup_result.get("duplicate_groups", []):
            for dup_id in group.get("duplicate_item_ids", []):
                duplicate_ids.add(dup_id)

        for set_idx, knowledge_item in enumerate(knowledge_output):
            set_id = f"S{set_idx + 1:03d}"
            container = knowledge_item[item_key]
            items = getattr(container, items_attr)
            kept = [
                item for item_idx, item in enumerate(items)
                if f"{set_id}_I{item_idx + 1:03d}" not in duplicate_ids
            ]
            setattr(container, items_attr, kept)

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
        artifact_payload = hitl.get("custom_inputs", {}).get("artifact", {}) or {}
        incoming_artifact = (
            artifact_payload.get("current_form_data")
            or artifact_payload.get("form_data")
            or {}
        )
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

        if intent == "ambiguous":
            clarifying_question = hitl_decision.task_summary
            new_hitl_task = prepare_hitl_task(
                agent_name=EXTERNAL_AGENT_NAME,
                text=clarifying_question,
                context="User provided ambiguous feedback. Awaiting a more specific response before applying changes.",
                state={} if use_checkpointer else {
                    **state, "messages": messages + [AIMessage(clarifying_question)]},
                artifact=hitl_artifact,
            )

            writer(prepare_thinking_message(EXTERNAL_AGENT_NAME,
                   "Feedback is ambiguous; asking clarifying question."))
            return Command(
                goto="route_interrupt",
                update={
                    "hitl_task": new_hitl_task,
                    "hitl_decision": hitl_decision,
                    "hitl_artifact": hitl_artifact,
                    "messages": messages + [AIMessage(f"HITL decision: ambiguous (step={pending_step})")],
                },
            )

        custom_message = prepare_thinking_message(
            EXTERNAL_AGENT_NAME, f"Decision is {intent}, proceeding... \n{task_summary}")
        writer(custom_message)

        goto = _route_from_pending_step(pending_step)

        # Persist FE-edited version into the canonical state slot so section
        # nodes can read it directly without re-deriving from hitl_artifact.
        # Guard with isinstance: if resolution didn't yield a valid section
        # object, leave canonical state untouched.
        step_to_state_key = {
            "key_concerns_review": "key_concerns",
            "doc_request_review": "doc_request",
            "enquiries_review": "additional_enquiries",
            "interview_plan_review": "interview_plan",
        }
        canonical_update: dict = {}
        sk = step_to_state_key.get(pending_step)
        if sk and isinstance(hitl_artifact, (KeyConcernSet, DocRequestSet,
                                             AdditionalEnquiriesSet, InterviewQuestionSets)):
            canonical_update[sk] = hitl_artifact

        return Command(
            goto=goto,
            update={
                "resume": False,
                "hitl_decision": hitl_decision,
                "hitl_artifact": hitl_artifact,
                "hitl_task": None,
                **canonical_update,
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
            # investigation_scope = hitl_artifact.get("investigation_scope")
            initial_review = hitl_artifact.get("initial_review")
            additional_info = hitl_artifact.get("additional_info")
            selected_sections = hitl_artifact.get(
                "selected_sections", ["doc_request", "additional_enquiries"])

            if claim_id and investigation_type and initial_review:
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
        feedback = decision.task_summary if decision and decision.intent == "feedback" else ""
        selected_sections = state.get("selected_sections", []) or []

        # --- Accept path: state["key_concerns"] is already canonical (written by route_interrupt) ---
        if decision and decision.intent == "accept":
            goto = _next_section("key_concerns", selected_sections)
            return Command(
                goto=goto,
                update={
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
            prev_version_json = prev_output.model_dump_json(
                indent=2, exclude_none=True) if prev_output else "{}"

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Revising key concerns based on feedback..."))

            prompt = SECTION_FEEDBACK_PROMPT.format(
                section_name="key concerns",
                prev_version=prev_version_json,
                feedback=feedback,
                initial_review=initial_review,
                additional_info=additional_info,
                knowledge_block="",
                gold_standards_block="",
                investigation_type_block="",
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
        feedback = decision.task_summary if decision and decision.intent == "feedback" else ""
        selected_sections = state.get("selected_sections", []) or []

        # --- Accept path: state["doc_request"] is already canonical (written by route_interrupt) ---
        if decision and decision.intent == "accept":
            goto = _next_section("doc_request", selected_sections)
            return Command(
                goto=goto,
                update={
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

        lob = state.get("lob", "")
        if lob == "Motor":
            gold_standards = MOTOR_DOC_REQUEST_GOLD_STANDARDS
            gold_standards_block = MOTOR_DOC_REQUEST_GOLD_STANDARDS_BLOCK
        elif lob == "Property":
            gold_standards = PROPERTY_DOC_REQUEST_GOLD_STANDARDS
            gold_standards_block = PROPERTY_DOC_REQUEST_GOLD_STANDARDS_BLOCK
        else:
            raise ValueError(f"Unsupported LOB: {lob}. Expected 'Motor' or 'Property'.")

        # --- Feedback path ---
        if feedback:
            prev_output = state.get("doc_request")
            prev_version_json = prev_output.model_dump_json(
                indent=2, exclude_none=True) if prev_output else "{}"

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Revising document requests based on feedback..."))

            # Reuse cached knowledge from draft path
            cached_knowledge = state.get("doc_request_knowledge") or ""
            knowledge_block = SECTION_FEEDBACK_KNOWLEDGE_BLOCK.format(
                knowledge=cached_knowledge) if cached_knowledge else ""

            prompt = SECTION_FEEDBACK_PROMPT.format(
                section_name="document requests",
                prev_version=prev_version_json,
                feedback=feedback,
                initial_review=initial_review,
                additional_info=additional_info,
                knowledge_block=knowledge_block,
                gold_standards_block=gold_standards_block,
                investigation_type_block="",
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
        else:
            # --- Draft path: chunk-based retrieval from delta table ---
            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Retrieving document request knowledge from textbook..."))

            per_inv_type, _ = await _retrieve_section_chunks_async(
                state,
                section="doc_request",
                parser_system_prompt=DOC_REQUEST_PARSER_SYSTEM_PROMPT,
                parser_prompt_template=DOC_REQUEST_PARSER_PROMPT,
                output_schema=DocRequestSet,
                item_key="doc_list",
            )

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Drafting document requests..."))

            investigation_types = state.get("investigation_type", []) or []
            investigation_type_str = ", ".join(investigation_types)
            knowledge_json = json.dumps(
                [
                    {
                        "investigation_type": entry["investigation_type"],
                        "doc_list": strip_hard_exclusions(
                            entry["doc_list"].model_dump(exclude_none=True),
                            initial_review,
                            additional_info,
                        ),
                    }
                    for entry in per_inv_type
                ],
                indent=2,
            )

            # --- Call 1: Relevance filter ---
            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Filtering relevant document types..."))

            relevance_prompt = DOC_REQUEST_RELEVANCE_PROMPT.format(
                initial_review=initial_review,
                additional_info=additional_info,
                knowledge=knowledge_json,
                investigation_type=investigation_type_str,
                format=parser.get_format_instructions(),
            )
            relevance_prompts = [SystemMessage(content=system_prompt),
                                HumanMessage(content=relevance_prompt)]
            relevance_response = llm.invoke(
                input=relevance_prompts,
                temperature=0.0,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
            relevance_content = relevance_response.content if isinstance(
                relevance_response.content, str) else relevance_response.content[0]["text"]
            relevance_docs = parser.parse(relevance_content)

            # --- Call 2: SME wording ---
            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Applying SME-standard wording..."))

            prev_version_json = json.dumps(
                relevance_docs.model_dump(exclude_none=True),
                indent=2,
            )

            sme_prompt = DOC_REQUEST_SME_PROMPT.format(
                prev_version=prev_version_json,
                gold_standards=gold_standards,
                initial_review=initial_review,
                additional_info=additional_info,
                format=parser.get_format_instructions(),
            )
            sme_prompts = [SystemMessage(content=system_prompt),
                           HumanMessage(content=sme_prompt)]
            sme_response = llm.invoke(
                input=sme_prompts,
                temperature=0.0,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
            sme_content = sme_response.content if isinstance(
                sme_response.content, str) else sme_response.content[0]["text"]
            methodology_docs = parser.parse(sme_content)

            # Format methodology doc types for narrative dedup reference
            methodology_doc_list = "\n".join(
                f"- {dr.doc_type}: {dr.doc_details}" if dr.doc_details else f"- {dr.doc_type}"
                for dr in methodology_docs.document_set
            ) if methodology_docs.document_set else "(none)"

            # --- Narrative call ---
            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Deriving narrative-driven document types..."))

            narrative_prompt = NARRATIVE_DOC_REQUEST_DRAFT_PROMPT.format(
                methodology_docs=methodology_doc_list,
                initial_review=initial_review,
                investigation_type=investigation_type_str,
                format=parser.get_format_instructions(),
            )
            narrative_prompts = [SystemMessage(content=system_prompt),
                                HumanMessage(content=narrative_prompt)]
            narrative_response = llm.invoke(
                input=narrative_prompts,
                temperature=0.0,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
            narrative_content = narrative_response.content if isinstance(
                narrative_response.content, str) else narrative_response.content[0]["text"]
            narrative_docs = parser.parse(narrative_content)

            # Merge methodology + narrative
            parsed = DocRequestSet(
                document_set=methodology_docs.document_set + narrative_docs.document_set,
                version=1,
            )

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
        feedback = decision.task_summary if decision and decision.intent == "feedback" else ""
        selected_sections = state.get("selected_sections", []) or []

        # --- Accept path: state["additional_enquiries"] is already canonical (written by route_interrupt) ---
        if decision and decision.intent == "accept":
            goto = _next_section("additional_enquiries", selected_sections)
            return Command(
                goto=goto,
                update={
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
        skipped_inv_types: list[str] = []

        # --- Feedback path ---
        if feedback:
            prev_output = state.get("additional_enquiries")
            prev_version_json = prev_output.model_dump_json(
                indent=2, exclude_none=True) if prev_output else "{}"

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Revising additional enquiries based on feedback..."))

            cached_knowledge = state.get("enquiries_knowledge") or ""
            knowledge_block = SECTION_FEEDBACK_KNOWLEDGE_BLOCK.format(
                knowledge=cached_knowledge) if cached_knowledge else ""

            prompt = SECTION_FEEDBACK_PROMPT.format(
                section_name="additional enquiries",
                prev_version=prev_version_json,
                feedback=feedback,
                initial_review=initial_review,
                additional_info=additional_info,
                knowledge_block=knowledge_block,
                gold_standards_block="",
                investigation_type_block="",
                format=parser.get_format_instructions(),
            )
        else:
            # --- Draft path: chunk-based retrieval from delta table ---
            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Retrieving additional enquiries knowledge from textbook..."))

            per_inv_type, skipped_inv_types = await _retrieve_section_chunks_async(
                state,
                section="additional_enquiries",
                parser_system_prompt=ENQUIRIES_PARSER_SYSTEM_PROMPT,
                parser_prompt_template=ENQUIRIES_PARSER_PROMPT,
                output_schema=AdditionalEnquiriesSet,
                item_key="enquiry_list",
                skip_on_empty=True,
            )

            if not per_inv_type:
                # Short-circuit: every inv_type had empty knowledge. Skip the
                # drafting LLM and emit an empty section.
                parsed = AdditionalEnquiriesSet(enquiries_set=[])
            else:
                knowledge_json = json.dumps(
                    [
                        {
                            "investigation_type": entry["investigation_type"],
                            "enquiry_list": entry["enquiry_list"].model_dump(exclude_none=True),
                        }
                        for entry in per_inv_type
                    ],
                    indent=2,
                )

                # --- Call 1: Relevance filter + contextualisation ---
                writer(prepare_thinking_message(
                    EXTERNAL_AGENT_NAME, "Filtering relevant additional enquiries..."))

                relevance_prompt = ADDITIONAL_ENQUIRIES_RELEVANCE_PROMPT.format(
                    initial_review=initial_review,
                    additional_info=additional_info,
                    knowledge=knowledge_json,
                    format=parser.get_format_instructions(),
                )
                relevance_prompts = [SystemMessage(content=system_prompt),
                                    HumanMessage(content=relevance_prompt)]
                relevance_response = llm.invoke(
                    input=relevance_prompts,
                    temperature=0.0,
                    max_tokens=4000,
                    response_format={"type": "json_object"},
                )
                relevance_content = relevance_response.content if isinstance(
                    relevance_response.content, str) else relevance_response.content[0]["text"]
                prev_version: AdditionalEnquiriesSet = parser.parse(relevance_content)

                # --- Call 2: Narrative derivation + aggregation + final polish ---
                writer(prepare_thinking_message(
                    EXTERNAL_AGENT_NAME, "Aggregating and finalising additional enquiries..."))

                prev_version_json = json.dumps(
                    prev_version.model_dump(exclude_none=True),
                    indent=2,
                )
                final_prompt = ADDITIONAL_ENQUIRIES_FINAL_PROMPT.format(
                    prev_version=prev_version_json,
                    initial_review=initial_review,
                    additional_info=additional_info,
                    format=parser.get_format_instructions(),
                )
                final_prompts = [SystemMessage(content=system_prompt),
                                HumanMessage(content=final_prompt)]
                final_response = llm.invoke(
                    input=final_prompts,
                    temperature=0.0,
                    max_tokens=4000,
                    response_format={"type": "json_object"},
                )
                final_content = final_response.content if isinstance(
                    final_response.content, str) else final_response.content[0]["text"]
                parsed: AdditionalEnquiriesSet = parser.parse(final_content)

        # Notify user about inv_types with no textbook coverage AFTER drafting
        # so the right-hand section already shows any enquiries that were
        # produced for the inv_types that did have knowledge.
        if skipped_inv_types and not per_inv_type:
            inv_type_list = ", ".join(skipped_inv_types)
            writer(prepare_hitl_task(
                agent_name=EXTERNAL_AGENT_NAME,
                text=f"No additional enquiry required for {inv_type_list} — feel free to add any enquiry by providing the details, or accept as-is.",
                context="Informational notice: textbook contains no additional enquiries for the listed investigation type(s).",
            ))

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
        feedback = decision.task_summary if decision and decision.intent == "feedback" else ""

        # --- Accept path: state["interview_plan"] is already canonical (written by route_interrupt) ---
        if decision and decision.intent == "accept":
            return Command(
                goto="assemble_plan",
                update={
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
            prev_version_json = prev_output.model_dump_json(
                indent=2, exclude_none=True) if prev_output else "{}"

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Revising interview plan based on feedback..."))

            cached_knowledge = state.get("interview_plan_knowledge") or ""
            knowledge_block = SECTION_FEEDBACK_KNOWLEDGE_BLOCK.format(
                knowledge=cached_knowledge) if cached_knowledge else ""

            prompt = SECTION_FEEDBACK_PROMPT.format(
                section_name="interview plan",
                prev_version=prev_version_json,
                feedback=feedback,
                initial_review=initial_review,
                additional_info=additional_info,
                knowledge_block=knowledge_block,
                gold_standards_block="",
                investigation_type_block="",
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
                knowledge_json = synthesized.model_dump_json(
                    indent=2, exclude_none=True)
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
            concern_set=key_concerns if key_concerns else KeyConcernSet(
                concern_set=[]),
            document_set=doc_request if doc_request else DocRequestSet(
                document_set=[]),
            enquiry_set=additional_enquiries if additional_enquiries else AdditionalEnquiriesSet(
                enquiries_set=[]),
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

        selected_sections = state.get("selected_sections", [])
        artifact = build_form_final(
            claim_id, final_plan, selected_sections) if final_plan else {}

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
