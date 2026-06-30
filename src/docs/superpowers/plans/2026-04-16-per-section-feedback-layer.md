# Per-Section Feedback Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a HITL feedback loop after each section generation so users can review, provide feedback, and accept each section sequentially before final assembly.

**Architecture:** Replace parallel fan-out with fixed sequential chain. Each section generator gains accept/feedback/draft branching at entry. A single `SECTION_FEEDBACK_PROMPT` handles regeneration for all sections. Routing uses `pending_step` to target feedback to the correct section.

**Tech Stack:** LangGraph (Command routing, interrupt), Pydantic, LangChain output parsers

**Spec:** `docs/superpowers/specs/2026-04-16-per-section-feedback-layer-design.md`

---

### Task 1: Add `version` and `update_notes` to section set schemas

**Files:**
- Modify: `agents/external_agent/schemas.py:50-51` (KeyConcernSet)
- Modify: `agents/external_agent/schemas.py:59-60` (DocRequestSet)
- Modify: `agents/external_agent/schemas.py:68-69` (AdditionalEnquiriesSet)
- Modify: `agents/external_agent/schemas.py:41-42` (InterviewQuestionSets)

- [ ] **Step 1: Add version and update_notes to all four section set schemas**

In `agents/external_agent/schemas.py`, update each schema:

```python
class InterviewQuestionSets(BaseModel):
    question_sets: List[InterviewQuestion]
    version: int = 1
    update_notes: Optional[str] = None
```

```python
class KeyConcernSet(BaseModel):
    concern_set: List[KeyConcern]
    version: int = 1
    update_notes: Optional[str] = None
```

```python
class DocRequestSet(BaseModel):
    document_set: List[DocRequest]
    version: int = 1
    update_notes: Optional[str] = None
```

```python
class AdditionalEnquiriesSet(BaseModel):
    enquiries_set: List[AdditionalEnquiries]
    version: int = 1
    update_notes: Optional[str] = None
```

- [ ] **Step 2: Verify no breakage**

Run: `python -c "from agents.external_agent.schemas import KeyConcernSet, DocRequestSet, AdditionalEnquiriesSet, InterviewQuestionSets; print('OK')"`

Expected: `OK` — defaults mean existing code that doesn't pass version/update_notes still works.

- [ ] **Step 3: Commit**

```bash
git add agents/external_agent/schemas.py
git commit -m "feat: add version and update_notes to section set schemas"
```

---

### Task 2: Add `SECTION_FEEDBACK_PROMPT` to prompts

**Files:**
- Modify: `agents/external_agent/prompt_manager/external_agent_prompts.py` (add new prompt, keep old `INTERVIEW_PLAN_FEEDBACK_PROMPT` for now)

- [ ] **Step 1: Add SECTION_FEEDBACK_PROMPT**

Add the following at the end of `agents/external_agent/prompt_manager/external_agent_prompts.py` (after `INTERVIEW_PLAN_FEEDBACK_PROMPT`):

```python
SECTION_FEEDBACK_PROMPT = """
<TASK>
**YOUR TASK**
Revise the PREVIOUS VERSION of the {section_name} by:

1. Prioritising and applying the FEEDBACK exactly as provided.
2. Making the **minimum necessary changes** to address the FEEDBACK.
3. Preserving structure, tone, and formatting unless FEEDBACK requires otherwise.
4. Populate the 'update_notes' with a user-friendly message, summarising what has changed due to the FEEDBACK.
5. Increment the 'version' field by 1 from the PREVIOUS VERSION.

If FEEDBACK is ambiguous, interpret it conservatively and document the intent through improved clarity rather than added scope.
</TASK>

<OUTPUT>
{{format}}
</OUTPUT>

<CONTEXT>
You are revising an existing set of {section_name} based on reviewer FEEDBACK.

<PREVIOUS VERSION>
{{prev_version}}
</PREVIOUS VERSION>

<FEEDBACK>
{{feedback}}
</FEEDBACK>

Here is the supporting context for the case (for reference only - do not re-interpret unless required by feedback):

The INITIAL REVIEW includes notes on the claim, policy and relevant details from searches conducted for the case being investigated.
<INITIAL REVIEW>
{{initial_review}}
</INITIAL REVIEW>

The ADDITIONAL INFORMATION includes additional notes on the claim, which can include police reports, engineer reports, incident reports, or other evidence.
<ADDITIONAL INFORMATION>
{{additional_info}}
</ADDITIONAL INFORMATION>
{knowledge_block}
</CONTEXT>
"""

SECTION_FEEDBACK_KNOWLEDGE_BLOCK = """
Here is the INVESTIGATION PROCESSES to guide you:
<INVESTIGATION PROCESSES>
{knowledge}
</INVESTIGATION PROCESSES>
"""
```

Note: `section_name` and `knowledge_block` use single braces (pre-formatted before `.format()` call). The remaining placeholders (`format`, `prev_version`, `feedback`, `initial_review`, `additional_info`) use double braces because `.format()` fills `section_name` and `knowledge_block` first, then a second `.format()` fills the rest. Alternatively, all can be single-brace if formatted in one call — see Task 4 for the actual usage.

**Update:** Actually, to keep it simple and consistent with existing prompts, use single braces for everything and format in one `.format()` call. The `knowledge_block` will be pre-built as a string before being passed:

```python
SECTION_FEEDBACK_PROMPT = """
<TASK>
**YOUR TASK**
Revise the PREVIOUS VERSION of the {section_name} by:

1. Prioritising and applying the FEEDBACK exactly as provided.
2. Making the **minimum necessary changes** to address the FEEDBACK.
3. Preserving structure, tone, and formatting unless FEEDBACK requires otherwise.
4. Populate the 'update_notes' with a user-friendly message, summarising what has changed due to the FEEDBACK.
5. Increment the 'version' field by 1 from the PREVIOUS VERSION.

If FEEDBACK is ambiguous, interpret it conservatively and document the intent through improved clarity rather than added scope.
</TASK>

<OUTPUT>
{format}
</OUTPUT>

<CONTEXT>
You are revising an existing set of {section_name} based on reviewer FEEDBACK.

<PREVIOUS VERSION>
{prev_version}
</PREVIOUS VERSION>

<FEEDBACK>
{feedback}
</FEEDBACK>

Here is the supporting context for the case (for reference only - do not re-interpret unless required by feedback):

The INITIAL REVIEW includes notes on the claim, policy and relevant details from searches conducted for the case being investigated.
<INITIAL REVIEW>
{initial_review}
</INITIAL REVIEW>

The ADDITIONAL INFORMATION includes additional notes on the claim, which can include police reports, engineer reports, incident reports, or other evidence.
<ADDITIONAL INFORMATION>
{additional_info}
</ADDITIONAL INFORMATION>
{knowledge_block}
</CONTEXT>
"""
```

Where `knowledge_block` is either an empty string `""` (for key_concerns) or the formatted knowledge section:

```python
SECTION_FEEDBACK_KNOWLEDGE_BLOCK = """
Here is the INVESTIGATION PROCESSES to guide you:
<INVESTIGATION PROCESSES>
{knowledge}
</INVESTIGATION PROCESSES>
"""
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from agents.external_agent.prompt_manager.external_agent_prompts import SECTION_FEEDBACK_PROMPT, SECTION_FEEDBACK_KNOWLEDGE_BLOCK; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agents/external_agent/prompt_manager/external_agent_prompts.py
git commit -m "feat: add SECTION_FEEDBACK_PROMPT for per-section regeneration"
```

---

### Task 3: Add `_next_section` helper and update routing functions

**Files:**
- Modify: `agents/external_agent/external_agent_graph.py:138-172` (_route_from_pending_step, _resolve_hitl_artifact)

- [ ] **Step 1: Add `_next_section` helper**

Add this function inside `get_graph()`, after `_resolve_hitl_artifact` (after line 172):

```python
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

        # Find where current section sits in the order
        if current == "key_concerns":
            remaining = order
        elif current == "doc_request":
            remaining = order[1:]
        elif current == "additional_enquiries":
            remaining = order[2:]
        else:
            # interview_plan or unknown — nothing left
            return "assemble_plan"

        for section_key, node_name in remaining:
            if section_key in selected_sections:
                return node_name

        return "assemble_plan"
```

- [ ] **Step 2: Update `_route_from_pending_step`**

Replace the existing function (lines 138-151) with:

```python
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
```

- [ ] **Step 3: Update `_resolve_hitl_artifact`**

Replace the existing function (lines 153-172) with:

```python
    def _resolve_hitl_artifact(state: "ExternalAgentState", pending_step: str, incoming_artifact: dict | None) -> Any:
        """
        If the frontend didn't send an artifact (common for feedback-only resumes),
        fall back to the last generated output stored in state for the relevant step.
        """
        incoming_artifact = incoming_artifact or {}

        step_to_state_key = {
            "key_concerns_review": "key_concerns",
            "doc_request_review": "doc_request",
            "enquiries_review": "additional_enquiries",
            "interview_plan_review": "interview_plan",
            "plan_review": "external_agent_plan",
        }

        state_key = step_to_state_key.get(pending_step)
        if state_key:
            if incoming_artifact:
                return incoming_artifact
            return state.get(state_key)

        # For init/unknown, nothing sensible to fall back to
        return incoming_artifact
```

- [ ] **Step 4: Commit**

```bash
git add agents/external_agent/external_agent_graph.py
git commit -m "feat: add _next_section helper and update HITL routing for per-section feedback"
```

---

### Task 4: Refactor section generators with accept/feedback/draft branching

**Files:**
- Modify: `agents/external_agent/external_agent_graph.py:11-16` (imports)
- Modify: `agents/external_agent/external_agent_graph.py:624-660` (generate_key_concerns)
- Modify: `agents/external_agent/external_agent_graph.py:662-729` (generate_doc_request)
- Modify: `agents/external_agent/external_agent_graph.py:731-798` (generate_enquiries)
- Modify: `agents/external_agent/external_agent_graph.py:800-879` (generate_interview_plan)

- [ ] **Step 1: Update imports**

Add `SECTION_FEEDBACK_PROMPT` and `SECTION_FEEDBACK_KNOWLEDGE_BLOCK` to the import from `external_agent_prompts`:

```python
from agents.external_agent.prompt_manager.external_agent_prompts import (
    EXTERNAL_AGENT_SYSTEM_PROMPT,
    KEY_CONCERNS_DRAFT_PROMPT,
    DOC_REQUEST_DRAFT_PROMPT,
    ADDITIONAL_ENQUIRIES_DRAFT_PROMPT,
    INTERVIEW_PLAN_DRAFT_PROMPT,
    SECTION_FEEDBACK_PROMPT,
    SECTION_FEEDBACK_KNOWLEDGE_BLOCK,
)
```

- [ ] **Step 2: Refactor `generate_key_concerns`**

Replace the function (lines 624-660) with:

```python
    def generate_key_concerns(state: "ExternalAgentState") -> Command:
        runtime, writer, messages = _get_ctx(state)

        decision = state.get("hitl_decision")
        hitl_artifact = state.get("hitl_artifact") or {}
        feedback = decision.task_summary if decision and decision.intent == "feedback" else ""
        selected_sections = state.get("selected_sections", []) or []

        # --- Accept path: persist and move to next section ---
        if decision and decision.intent == "accept":
            # Use artifact if user edited, otherwise keep existing
            if hitl_artifact and isinstance(hitl_artifact, dict):
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
        artifact = parsed.model_dump(exclude_none=True)
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
```

- [ ] **Step 3: Refactor `generate_doc_request_async`**

Replace the async function (lines 662-721) with:

```python
    async def generate_doc_request_async(state: "ExternalAgentState") -> Command:
        runtime, writer, messages = _get_ctx(state)

        decision = state.get("hitl_decision")
        hitl_artifact = state.get("hitl_artifact") or {}
        feedback = decision.task_summary if decision and decision.intent == "feedback" else ""
        selected_sections = state.get("selected_sections", []) or []

        # --- Accept path ---
        if decision and decision.intent == "accept":
            if hitl_artifact and isinstance(hitl_artifact, dict):
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

        # --- Feedback path ---
        if feedback:
            prev_output = state.get("doc_request")
            prev_version_json = prev_output.model_dump_json(indent=2, exclude_none=True) if prev_output else "{}"

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Revising document requests based on feedback..."))

            knowledge_block = ""
            # Re-use synthesized knowledge if available (retrieve again for context)
            knowledge_endpoint = runtime.context["resources_endpoint_name"]
            raw_knowledge = await _retrieve_section_knowledge(
                task_key="doc_requests",
                task_def=RETRIEVAL_TASKS["doc_requests"],
                state=state,
                knowledge_endpoint=knowledge_endpoint,
            )
            investigation_types = state.get("investigation_type", []) or []
            synthesized = _synthesize_section_knowledge(
                section_name="document requests",
                knowledge_set=raw_knowledge,
                investigation_types=investigation_types,
                output_schema=DocRequestSet,
            )
            knowledge_json = synthesized.model_dump_json(indent=2, exclude_none=True)
            knowledge_block = SECTION_FEEDBACK_KNOWLEDGE_BLOCK.format(knowledge=knowledge_json)

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

            prompt = DOC_REQUEST_DRAFT_PROMPT.format(
                initial_review=initial_review,
                knowledge=synthesized.model_dump_json(indent=2, exclude_none=True),
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
        artifact = parsed.model_dump(exclude_none=True)
        text = "Document requests drafted. Please review and provide feedback or accept."
        hitl_task = prepare_hitl_task(
            agent_name=EXTERNAL_AGENT_NAME,
            text=text,
            context="User must review document requests and either accept, edit+submit, or provide feedback.",
            state={} if use_checkpointer else {
                **state, "messages": messages + [AIMessage(text)]},
            artifact=artifact,
        )

        return Command(
            goto="route_interrupt",
            update={
                "doc_request": parsed,
                "pending_step": "doc_request_review",
                "hitl_task": hitl_task,
                "hitl_decision": None,
                "hitl_artifact": None,
                "messages": messages + [AIMessage("Document requests drafted. Awaiting review.")],
            },
        )
```

- [ ] **Step 4: Refactor `generate_enquiries_async`**

Replace the async function (lines 731-790) with:

```python
    async def generate_enquiries_async(state: "ExternalAgentState") -> Command:
        runtime, writer, messages = _get_ctx(state)

        decision = state.get("hitl_decision")
        hitl_artifact = state.get("hitl_artifact") or {}
        feedback = decision.task_summary if decision and decision.intent == "feedback" else ""
        selected_sections = state.get("selected_sections", []) or []

        # --- Accept path ---
        if decision and decision.intent == "accept":
            if hitl_artifact and isinstance(hitl_artifact, dict):
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

        # --- Feedback path ---
        if feedback:
            prev_output = state.get("additional_enquiries")
            prev_version_json = prev_output.model_dump_json(indent=2, exclude_none=True) if prev_output else "{}"

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Revising additional enquiries based on feedback..."))

            knowledge_endpoint = runtime.context["resources_endpoint_name"]
            raw_knowledge = await _retrieve_section_knowledge(
                task_key="additional_enquiries",
                task_def=RETRIEVAL_TASKS["additional_enquiries"],
                state=state,
                knowledge_endpoint=knowledge_endpoint,
            )
            investigation_types = state.get("investigation_type", []) or []
            synthesized = _synthesize_section_knowledge(
                section_name="additional enquiries",
                knowledge_set=raw_knowledge,
                investigation_types=investigation_types,
                output_schema=AdditionalEnquiriesSet,
            )
            knowledge_json = synthesized.model_dump_json(indent=2, exclude_none=True)
            knowledge_block = SECTION_FEEDBACK_KNOWLEDGE_BLOCK.format(knowledge=knowledge_json)

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

            prompt = ADDITIONAL_ENQUIRIES_DRAFT_PROMPT.format(
                initial_review=initial_review,
                knowledge=synthesized.model_dump_json(indent=2, exclude_none=True),
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
        artifact = parsed.model_dump(exclude_none=True)
        text = "Additional enquiries drafted. Please review and provide feedback or accept."
        hitl_task = prepare_hitl_task(
            agent_name=EXTERNAL_AGENT_NAME,
            text=text,
            context="User must review additional enquiries and either accept, edit+submit, or provide feedback.",
            state={} if use_checkpointer else {
                **state, "messages": messages + [AIMessage(text)]},
            artifact=artifact,
        )

        return Command(
            goto="route_interrupt",
            update={
                "additional_enquiries": parsed,
                "pending_step": "enquiries_review",
                "hitl_task": hitl_task,
                "hitl_decision": None,
                "hitl_artifact": None,
                "messages": messages + [AIMessage("Additional enquiries drafted. Awaiting review.")],
            },
        )
```

- [ ] **Step 5: Refactor `generate_interview_plan_async`**

Replace the async function (lines 800-871) with:

```python
    async def generate_interview_plan_async(state: "ExternalAgentState") -> Command:
        runtime, writer, messages = _get_ctx(state)

        decision = state.get("hitl_decision")
        hitl_artifact = state.get("hitl_artifact") or {}
        feedback = decision.task_summary if decision and decision.intent == "feedback" else ""
        selected_sections = state.get("selected_sections", []) or []

        # --- Accept path ---
        if decision and decision.intent == "accept":
            if hitl_artifact and isinstance(hitl_artifact, dict):
                try:
                    accepted = InterviewQuestionSets(**hitl_artifact)
                except Exception:
                    accepted = state.get("interview_plan")
            else:
                accepted = state.get("interview_plan")

            # interview_plan is always last → assemble_plan
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

        # --- Feedback path ---
        if feedback:
            prev_output = state.get("interview_plan")
            prev_version_json = prev_output.model_dump_json(indent=2, exclude_none=True) if prev_output else "{}"

            writer(prepare_thinking_message(
                EXTERNAL_AGENT_NAME, "Revising interview plan based on feedback..."))

            # Retrieve knowledge (may be empty if not configured)
            task_key = "interview_plan"
            task_def = RETRIEVAL_TASKS.get(task_key)
            knowledge_block = ""
            if task_def:
                knowledge_endpoint = runtime.context["resources_endpoint_name"]
                raw_knowledge = await _retrieve_section_knowledge(
                    task_key=task_key,
                    task_def=task_def,
                    state=state,
                    knowledge_endpoint=knowledge_endpoint,
                )
                if raw_knowledge.knowledge:
                    investigation_types = state.get("investigation_type", []) or []
                    synthesized = _synthesize_section_knowledge(
                        section_name="interview plan",
                        knowledge_set=raw_knowledge,
                        investigation_types=investigation_types,
                        output_schema=InterviewQuestionSets,
                    )
                    knowledge_json = synthesized.model_dump_json(indent=2, exclude_none=True)
                    knowledge_block = SECTION_FEEDBACK_KNOWLEDGE_BLOCK.format(knowledge=knowledge_json)

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
        artifact = parsed.model_dump(exclude_none=True)
        text = "Interview plan drafted. Please review and provide feedback or accept."
        hitl_task = prepare_hitl_task(
            agent_name=EXTERNAL_AGENT_NAME,
            text=text,
            context="User must review interview plan and either accept, edit+submit, or provide feedback.",
            state={} if use_checkpointer else {
                **state, "messages": messages + [AIMessage(text)]},
            artifact=artifact,
        )

        return Command(
            goto="route_interrupt",
            update={
                "interview_plan": parsed,
                "pending_step": "interview_plan_review",
                "hitl_task": hitl_task,
                "hitl_decision": None,
                "hitl_artifact": None,
                "messages": messages + [AIMessage("Interview plan drafted. Awaiting review.")],
            },
        )
```

- [ ] **Step 6: Commit**

```bash
git add agents/external_agent/external_agent_graph.py
git commit -m "feat: add accept/feedback/draft branching to all section generators"
```

---

### Task 5: Update graph edges — sequential chain

**Files:**
- Modify: `agents/external_agent/external_agent_graph.py:996-1038` (route_sections, graph definition)

- [ ] **Step 1: Remove `route_sections` and update `dispatch_sections`**

The `route_sections` function (lines 996-1011) is no longer needed. Remove it entirely.

Update `dispatch_sections` (lines 613-618) to go directly to `generate_key_concerns`:

```python
    def dispatch_sections(state: "ExternalAgentState") -> Command:
        """Thin node that kicks off sequential section generation."""
        return Command(
            goto="generate_key_concerns",
            update={
                "hitl_decision": None,
                "hitl_artifact": None,
            },
        )
```

- [ ] **Step 2: Update graph definition**

Replace the graph definition (lines ~1017-1038) with:

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
        .add_edge("dispatch_sections", "generate_key_concerns")
        .add_edge("assemble_plan", "finalise_plan")
        .add_edge("finalise_plan", END)
    )

    return graph
```

Note: The edges from section generators to `route_interrupt`/next section/`assemble_plan` are handled dynamically via `Command(goto=...)` inside each function. The old `.add_conditional_edges("dispatch_sections", route_sections)` and static edges from sections to `assemble_plan` are removed.

- [ ] **Step 3: Verify syntax**

Run: `python -c "from agents.external_agent.external_agent_graph import get_graph; print('Graph loads OK')"`

This will fail if there are import errors or syntax issues. It may fail on missing LLM config — that's expected. The goal is to catch Python syntax errors.

- [ ] **Step 4: Commit**

```bash
git add agents/external_agent/external_agent_graph.py
git commit -m "feat: replace parallel fan-out with sequential section chain"
```

---

### Task 6: Clean up — remove old `INTERVIEW_PLAN_FEEDBACK_PROMPT` import comment

**Files:**
- Modify: `agents/external_agent/external_agent_graph.py:20` (commented import)

- [ ] **Step 1: Update commented import to reference new prompt**

Replace the commented import line:
```python
# from agents.external_agent.prompt_manager.external_agent_prompts import INTERVIEW_DOC_REQUEST_PROMPT, INTERVIEW_PLAN_FEEDBACK_PROMPT
```

With:
```python
# from agents.external_agent.prompt_manager.external_agent_prompts import INTERVIEW_DOC_REQUEST_PROMPT
```

The `INTERVIEW_PLAN_FEEDBACK_PROMPT` is now superseded by `SECTION_FEEDBACK_PROMPT` (which is actively imported).

- [ ] **Step 2: Commit**

```bash
git add agents/external_agent/external_agent_graph.py
git commit -m "chore: clean up stale INTERVIEW_PLAN_FEEDBACK_PROMPT import comment"
```
