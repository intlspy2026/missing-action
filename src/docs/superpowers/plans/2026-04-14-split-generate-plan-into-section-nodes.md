# Split generate_plan into Per-Section Nodes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the monolithic `generate_plan` node into 4 independent per-section nodes (key concerns, doc request, additional enquiries, interview plan), each with its own knowledge retrieval and synthesis.

**Architecture:** Replace `retrieve_knowledge` → `generate_plan` with a conditional fan-out from `initialise_query` to per-section nodes that each retrieve their own knowledge, synthesize it, and draft their section output. A new `assemble_plan` node collects results before `finalise_plan`. LangGraph `Send()` handles parallel dispatch based on user-selected sections.

**Tech Stack:** LangGraph, Pydantic, LangChain, asyncio

---

### Task 1: Update schemas.py — Rename state and update fields

**Files:**
- Modify: `agents/external_agent/schemas.py`

- [x] **Step 1: Comment out unused schemas**

Comment out `InterviewStrategy`, `InterviewObjective`, `InterviewPlan`, `KnowledgeReport`, `InterviewPlanStruct`, and the duplicate `SmartInvestigatorAgentState`.

- [x] **Step 2: Rename InterviewPlanState to ExternalAgentState and update fields**

New state class:

```python
class ExternalAgentState(MessagesState):
    """State for the external agent investigation instructions system."""
    # Case context
    claim_id: str
    brand: str
    initial_review: str
    additional_info: Optional[str] = None
    lob: str
    investigation_type: List[str]
    investigation_scope: str

    # User-selected sections (key_concerns always generated regardless)
    selected_sections: List[Literal["doc_request", "additional_enquiries", "interview_plan"]]

    # Per-section outputs
    key_concerns: Optional[KeyConcernSet] = None
    doc_request: Optional[DocRequestSet] = None
    additional_enquiries: Optional[AdditionalEnquiriesSet] = None
    interview_plan: Optional[InterviewQuestionSets] = None

    # Final assembled output
    external_agent_plan: Optional[ExternalAgentPlan] = None

    # HITL / control flow
    artifact: dict[str, Any]
    resume: bool
    pending_step: Optional[str] = None
    hitl_decision: Optional[HITLDecision] = None
    hitl_artifact: Optional[dict[str, Any]] = None
    hitl_task: Optional[str] = None
```

Key changes vs old `InterviewPlanState`:
- Added `selected_sections` for user selection of which sections to generate
- Replaced `knowledge: Optional[KnowledgeReport]` with per-section output fields
- Replaced `interview_plans` with `external_agent_plan`
- Removed `online_eval`

- [x] **Step 3: Commit**

---

### Task 2: Update knowledge_prompts.py — Add section synthesis prompt

**Files:**
- Modify: `agents/external_agent/prompt_manager/knowledge_prompts.py`

- [x] **Step 1: Comment out KNOWLEDGE_REPORT_SYSTEM_PROMPT and KNOWLEDGE_REPORT_PROMPT**

These are replaced by the new per-section synthesis prompt.

- [x] **Step 2: Add SECTION_KNOWLEDGE_REPORT_SYSTEM_PROMPT and SECTION_KNOWLEDGE_REPORT_PROMPT**

Single generic template that works for all sections — the `{format}` parameter from `PydanticOutputParser` differentiates the output structure:

```python
SECTION_KNOWLEDGE_REPORT_SYSTEM_PROMPT = """
You are an insurance report drafting assistant. Your task is to synthesise retrieved knowledge into a structured report for a specific section of an external investigation.
"""

SECTION_KNOWLEDGE_REPORT_PROMPT = """
<TASK>
Using the provided retrieved knowledge, produce a structured report for the {section_name} section of an external investigation for the given investigation type.

You MUST:
- Use ONLY the provided knowledge.
- Not introduce new content.
- Not paraphrase — preserve original wording.
- Extract ALL relevant items for this section.
</TASK>

<INPUTS>
<INVESTIGATION_TYPE>{investigation_type}</INVESTIGATION_TYPE>
<RETRIEVED_KNOWLEDGE>{knowledge_set}</RETRIEVED_KNOWLEDGE>
</INPUTS>

<OUTPUT>
{format}
Do NOT output any extra commentary outside this JSON. Only return this.
</OUTPUT>
"""
```

Usage per section — uses existing schemas directly (no new wrapper schemas):
- Doc request: `PydanticOutputParser(pydantic_object=DocRequestSet)`
- Enquiries: `PydanticOutputParser(pydantic_object=AdditionalEnquiriesSet)`
- Interview plan: `PydanticOutputParser(pydantic_object=InterviewQuestionSets)`

- [x] **Step 3: Commit**

---

### Task 3: Update external_agent_graph.py — Imports and helper functions

**Files:**
- Modify: `agents/external_agent/external_agent_graph.py`

- [x] **Step 1: Fix imports**

Key changes:
- Uncommented `external_agent_prompts` import (was commented out but prompts were used)
- Added `Send` from `langgraph.types`
- Imported `SECTION_KNOWLEDGE_REPORT_*` prompts
- Imported `ExternalAgentState` instead of `InterviewPlanState`
- Commented out broken `utils.py` import (file is empty)
- Commented out unused schema imports (`InterviewStrategy`, `InterviewPlan`, `KnowledgeReport`)
- Commented out `online_eval` import

- [x] **Step 2: Add `_retrieve_section_knowledge` helper**

Extracted from `retrieve_knowledge_async` — runs ONE retrieval task for a single section, looping over investigation types:

```python
async def _retrieve_section_knowledge(
    task_key: str,
    task_def: dict,
    state: "ExternalAgentState",
    knowledge_endpoint: str,
) -> KnowledgeSet:
```

Reuses `_run_retrieval_task` and `_run_tool_call_async` (unchanged).

- [x] **Step 3: Add `_synthesize_section_knowledge` helper**

Takes raw `KnowledgeSet` and structures it into section-specific schema using `SECTION_KNOWLEDGE_REPORT_PROMPT`:

```python
def _synthesize_section_knowledge(
    section_name: str,
    knowledge_set: KnowledgeSet,
    investigation_types: list[str],
    output_schema,
) -> Any:
```

- [x] **Step 4: Commit**

---

### Task 4: Update external_agent_graph.py — Comment out old nodes, update HITL helpers

**Files:**
- Modify: `agents/external_agent/external_agent_graph.py`

- [x] **Step 1: Comment out `retrieve_knowledge_async` and `retrieve_knowledge`**

Replaced by per-section `_retrieve_section_knowledge` helper.

- [x] **Step 2: Comment out `generate_plan`**

Replaced by 4 per-section generate nodes.

- [x] **Step 3: Update `_resolve_hitl_artifact` to use ExternalAgentState**

Changed type hint, updated `plan_review` branch to read from `external_agent_plan`.

- [x] **Step 4: Update all `"InterviewPlanState"` type hints to `"ExternalAgentState"`**

In `route_interrupt`, `initialise_query`, `finalise_plan`, and all helper functions.

- [x] **Step 5: Commit**

---

### Task 5: Update external_agent_graph.py — Add 4 section nodes and assemble_plan

**Files:**
- Modify: `agents/external_agent/external_agent_graph.py`

- [x] **Step 1: Add `generate_key_concerns` node**

No knowledge retrieval — just uses `initial_review` + `additional_info` with `KEY_CONCERNS_DRAFT_PROMPT`. Outputs `KeyConcernSet`.

- [x] **Step 2: Add `generate_doc_request` node**

Pattern: retrieve (`doc_requests` task) → synthesize (`DocRequestSet`) → draft (`DOC_REQUEST_DRAFT_PROMPT`). Has async version + sync wrapper.

- [x] **Step 3: Add `generate_enquiries` node**

Pattern: retrieve (`additional_enquiries` task) → synthesize (`AdditionalEnquiriesSet`) → draft (`ADDITIONAL_ENQUIRIES_DRAFT_PROMPT`). Has async version + sync wrapper.

- [x] **Step 4: Add `generate_interview_plan` node**

Pattern: retrieve (task key `interview_plan`, gracefully handles missing task def) → synthesize (`InterviewQuestionSets`) → draft (`INTERVIEW_PLAN_DRAFT_PROMPT`). Has async version + sync wrapper. NOTE: retrieval tasks for interview plan are still commented out in `RETRIEVAL_TASKS`.

- [x] **Step 5: Add `assemble_plan` node**

Reads per-section state keys (`key_concerns`, `doc_request`, `additional_enquiries`, `interview_plan`), assembles into `ExternalAgentPlan`. Uses empty defaults for unselected sections.

- [x] **Step 6: Commit**

---

### Task 6: Update external_agent_graph.py — Routing, finalise_plan, and graph wiring

**Files:**
- Modify: `agents/external_agent/external_agent_graph.py`

- [x] **Step 1: Add `route_sections` function**

Returns list of `Send()` calls based on `selected_sections`. Key concerns always included.

```python
def route_sections(state: "ExternalAgentState") -> list[Send]:
    sends = [Send("generate_key_concerns", state)]
    selected = state.get("selected_sections", []) or []
    if "doc_request" in selected:
        sends.append(Send("generate_doc_request", state))
    if "additional_enquiries" in selected:
        sends.append(Send("generate_enquiries", state))
    if "interview_plan" in selected:
        sends.append(Send("generate_interview_plan", state))
    return sends
```

- [x] **Step 2: Add `dispatch_sections` node and update `initialise_query` routing**

`dispatch_sections` is a thin node that triggers conditional fan-out. `initialise_query` now routes to `dispatch_sections` instead of `retrieve_knowledge`. Also extracts `selected_sections` from HITL artifact.

- [x] **Step 3: Update `finalise_plan`**

Reads from `external_agent_plan` instead of `interview_plans`. Removed `online_eval` references. Simplified artifact to dict until `build_form_final` is implemented in `utils.py`.

- [x] **Step 4: Replace graph definition**

```python
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
    .add_conditional_edges("dispatch_sections", route_sections)
    .add_edge("generate_key_concerns", "assemble_plan")
    .add_edge("generate_doc_request", "assemble_plan")
    .add_edge("generate_enquiries", "assemble_plan")
    .add_edge("generate_interview_plan", "assemble_plan")
    .add_edge("assemble_plan", "finalise_plan")
    .add_edge("finalise_plan", END)
)
```

Note: old graph definition was dead code (after a `return` in `finalise_plan`).

- [x] **Step 5: Commit**

---

### Task 7: Fix external_agent_prompts.py — f-string bug and additional_info

**Files:**
- Modify: `agents/external_agent/prompt_manager/external_agent_prompts.py`

- [x] **Step 1: Fix ADDITIONAL_ENQUIRIES_DRAFT_PROMPT f-string bug**

Changed `f"""` to `"""` on line 125. The f-string prefix caused `{knowledge}`, `{initial_review}`, `{format}` to be evaluated at import time instead of at `.format()` call time.

- [x] **Step 2: Add `{additional_info}` to KEY_CONCERNS_DRAFT_PROMPT**

Added `<ADDITIONAL INFORMATION>` section to the `<CONTEXT>` block. Updated RULE 5, task description, steps, and rationale requirements to reference ADDITIONAL INFORMATION as a supplementary evidence source alongside INITIAL REVIEW.

- [x] **Step 3: Commit**

---

### Task 8: Verify — review for consistency

**Files:**
- Review: all modified files

- [x] **Step 1: Check for stale references**

Searched for `InterviewPlanState`, `KnowledgeReport`, `online_eval`, `retrieve_knowledge`, `generate_plan` — all remaining references are in comments only.

- [x] **Step 2: Verify prompt placeholders match .format() calls**

- `KEY_CONCERNS_DRAFT_PROMPT`: `{format}`, `{initial_review}`, `{additional_info}` — matches `generate_key_concerns`
- `DOC_REQUEST_DRAFT_PROMPT`: `{knowledge}`, `{initial_review}`, `{format}` — matches `generate_doc_request`
- `ADDITIONAL_ENQUIRIES_DRAFT_PROMPT`: `{knowledge}`, `{initial_review}`, `{format}` — matches `generate_enquiries`
- `INTERVIEW_PLAN_DRAFT_PROMPT`: `{knowledge}`, `{initial_review}`, `{format}` — matches `generate_interview_plan`

---

## Summary of Changes

| File | What Changed |
|---|---|
| `schemas.py` | Renamed `InterviewPlanState` → `ExternalAgentState`, added `selected_sections` + per-section fields, commented out `KnowledgeReport`, `InterviewStrategy`, `InterviewPlan`, `InterviewPlanStruct` |
| `knowledge_prompts.py` | Added `SECTION_KNOWLEDGE_REPORT_PROMPT`, commented out `KNOWLEDGE_REPORT_PROMPT` + `KNOWLEDGE_REPORT_SYSTEM_PROMPT` |
| `external_agent_graph.py` | Split `generate_plan` into 4 section nodes + `assemble_plan`, added `_retrieve_section_knowledge` + `_synthesize_section_knowledge` helpers, added `dispatch_sections` + `route_sections` fan-out, updated `finalise_plan`, fixed imports, commented out old nodes |
| `external_agent_prompts.py` | Fixed f-string bug in `ADDITIONAL_ENQUIRIES_DRAFT_PROMPT`, added `{additional_info}` to `KEY_CONCERNS_DRAFT_PROMPT` |

## Out of Scope

- Feedback path (HITL feedback/re-generation) — to be discussed separately
- Interview plan retrieval tasks — currently commented out in `RETRIEVAL_TASKS`, uncomment when ready
- `online_evaluation` — discarded entirely
- `utils.py` — empty, `build_form_info` / `build_form_final` need implementation
