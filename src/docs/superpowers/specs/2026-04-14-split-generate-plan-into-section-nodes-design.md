# Split generate_plan into Per-Section Nodes

## Summary

Refactor the external agent's monolithic `generate_plan` node into 4 independent section nodes, each responsible for its own knowledge retrieval, synthesis, and draft generation. Users select which sections to generate (key concerns always runs).

## Current State

- `initialise_query` -> `retrieve_knowledge` -> `generate_plan` -> `online_evaluation` -> `finalise_plan`
- `retrieve_knowledge` runs all retrieval tasks in parallel, synthesizes into one `KnowledgeReport`
- `generate_plan` generates 3 sections sequentially (key concerns, doc request, additional enquiries) in one node
- Interview plan section is commented out
- `online_evaluation` node is referenced but never defined
- `InterviewPlanState` is a leftover name from the interview plans agent
- `utils.py` is empty but imported from (broken)

## Target State

### Graph Flow

```
initialise_query -> [conditional fan-out via Send() based on selected_sections]
                     -> generate_key_concerns (always)
                     -> generate_doc_request (if selected)      -> assemble_plan -> finalise_plan
                     -> generate_enquiries (if selected)
                     -> generate_interview_plan (if selected)
```

### State Schema

Rename `InterviewPlanState` to `ExternalAgentState`.

Changes:
- Add `selected_sections: List[Literal["doc_request", "additional_enquiries", "interview_plan"]]` — user chooses which sections to generate. Key concerns always runs regardless.
- Add per-section output fields: `key_concerns`, `doc_request`, `additional_enquiries`, `interview_plan`
- Add `external_agent_plan: Optional[ExternalAgentPlan]` for final assembled output
- Remove `knowledge: Optional[KnowledgeReport]` — no longer a single knowledge blob
- Remove `online_eval: Optional[Dict[str, Any]]` — online evaluation discarded
- Remove `interview_plans: Optional[InterviewQuestionSets]` — replaced by per-section fields

### Per-Section Node Pattern

Each section node (except key concerns) follows this pattern:

1. **Retrieve** — call `_retrieve_section_knowledge()` helper with section-specific `RETRIEVAL_TASKS` entry. Returns `KnowledgeSet` (list of raw Q&A pairs).
2. **Synthesize** — call LLM with generic `SECTION_KNOWLEDGE_REPORT_PROMPT`, using `PydanticOutputParser` with the section's existing schema (e.g. `DocRequestSet`) as format. Structures raw Q&A into section schema.
3. **Draft** — call LLM with section-specific draft prompt (e.g. `DOC_REQUEST_DRAFT_PROMPT`) using synthesized knowledge + `initial_review`. Outputs section schema.
4. **Return** — `Command(goto="assemble_plan", update={"doc_request": parsed, ...})`

`generate_key_concerns` skips steps 1-2 (no knowledge retrieval — uses only `initial_review`).

### Retrieval Helper

Extract from `retrieve_knowledge_async` into a reusable helper:

```python
async def _retrieve_section_knowledge(
    state: "ExternalAgentState",
    task_key: str,
    task_def: dict,
    llm_with_tools,
    knowledge_endpoint: str,
) -> KnowledgeSet:
    """
    Run ONE retrieval task for a single section.
    Loops over investigation_types from state.
    Reuses _run_retrieval_task internally.
    Returns raw KnowledgeSet (no report synthesis).
    """
```

`_run_retrieval_task` and `_run_tool_call_async` remain unchanged.

### Knowledge Prompts

New generic synthesis prompt (replaces `KNOWLEDGE_REPORT_PROMPT`):

```python
SECTION_KNOWLEDGE_REPORT_PROMPT = """
<TASK>
Using the provided retrieved knowledge, produce a structured report
for the {section_name} section of an external investigation.
You MUST:
- Use ONLY the provided knowledge.
- Not introduce new content.
- Not paraphrase - preserve original wording.
- Extract ALL relevant items for this section.
</TASK>
<INPUTS>
<INVESTIGATION_TYPE>{investigation_type}</INVESTIGATION_TYPE>
<RETRIEVED_KNOWLEDGE>{knowledge_set}</RETRIEVED_KNOWLEDGE>
</INPUTS>
<OUTPUT>
{format}
Do NOT output any extra commentary outside this JSON.
</OUTPUT>
"""
```

Usage per section — the format parameter uses existing schemas directly:
- Doc request: `PydanticOutputParser(pydantic_object=DocRequestSet)`
- Enquiries: `PydanticOutputParser(pydantic_object=AdditionalEnquiriesSet)`
- Interview plan: `PydanticOutputParser(pydantic_object=InterviewQuestionSets)`

No new schemas needed.

### Graph Wiring

```python
graph = (
    StateGraph(ExternalAgentState)
    .add_node("initialise_query", initialise_query)
    .add_node("generate_key_concerns", generate_key_concerns)
    .add_node("generate_doc_request", generate_doc_request)
    .add_node("generate_enquiries", generate_enquiries)
    .add_node("generate_interview_plan", generate_interview_plan)
    .add_node("assemble_plan", assemble_plan)
    .add_node("finalise_plan", finalise_plan)
    .add_node("route_interrupt", route_interrupt)
    .add_edge(START, "initialise_query")
    .add_conditional_edges("initialise_query", route_sections)
    .add_edge("generate_key_concerns", "assemble_plan")
    .add_edge("generate_doc_request", "assemble_plan")
    .add_edge("generate_enquiries", "assemble_plan")
    .add_edge("generate_interview_plan", "assemble_plan")
    .add_edge("assemble_plan", "finalise_plan")
    .add_edge("finalise_plan", END)
)
```

`route_sections` returns a list of `Send()` calls based on `selected_sections` state field. Key concerns is always included.

### assemble_plan Node

Simple node that reads per-section state keys and assembles `ExternalAgentPlan`:

```python
def assemble_plan(state: "ExternalAgentState") -> Command:
    plan = ExternalAgentPlan(
        concern_set=state.get("key_concerns"),
        document_set=state.get("doc_request"),
        enquiry_set=state.get("additional_enquiries"),
        # interview_plan=state.get("interview_plan"),
        version=1,
        created_at=datetime.utcnow().isoformat(),
    )
    return Command(goto="finalise_plan", update={"external_agent_plan": plan, ...})
```

Only includes sections that were selected and generated.

## What Gets Commented Out

| Item | File | Action |
|---|---|---|
| `KnowledgeReport` class | `schemas.py` | Comment out |
| `InterviewPlanState` | `schemas.py` | Rename to `ExternalAgentState` |
| `KNOWLEDGE_REPORT_PROMPT` | `knowledge_prompts.py` | Comment out |
| `KNOWLEDGE_REPORT_SYSTEM_PROMPT` | `knowledge_prompts.py` | Comment out |
| `retrieve_knowledge` node function | `external_agent_graph.py` | Comment out |
| `retrieve_knowledge_async` node function | `external_agent_graph.py` | Comment out |
| `generate_plan` monolithic node | `external_agent_graph.py` | Replace with 4 section nodes |
| `online_evaluation` references | `external_agent_graph.py` | Remove |
| `from agents.external_agent.utils import ...` | `external_agent_graph.py` | Comment out (utils.py is empty) |
| `InterviewPlan` class | `schemas.py` | Comment out (unused) |
| `InterviewStrategy` class | `schemas.py` | Comment out (unused) |

## Files Changed

| File | Scope |
|---|---|
| `schemas.py` | Rename state, add `selected_sections` + per-section fields, comment out unused schemas |
| `external_agent_graph.py` | Split nodes, add retrieval helper, new graph wiring, fix imports, comment out old nodes |
| `knowledge_prompts.py` | Add `SECTION_KNOWLEDGE_REPORT_PROMPT`, comment out old report prompt |
| `external_agent_prompts.py` | No changes |

## Out of Scope

- Feedback path (HITL feedback/re-generation) — to be discussed separately
- Interview plan retrieval tasks — currently commented out in `RETRIEVAL_TASKS`, will uncomment when ready
- `online_evaluation` — discarded entirely
