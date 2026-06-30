# Per-Section Feedback Layer Design

## Problem

The external agent generates sections (key concerns, doc requests, additional enquiries, interview plan) in parallel with no user review between them. The frontend will present each section on a separate screen where the user can provide feedback before moving to the next. Once all sections are assembled, feedback is no longer possible.

## Design

### Execution Flow

Replace parallel fan-out with a fixed sequential chain. Each section generates output, pauses for user review via HITL, and only proceeds to the next section on accept.

```
dispatch_sections
  → generate_key_concerns → route_interrupt (pending_step="key_concerns_review")
    → accept → generate_doc_request → route_interrupt (pending_step="doc_request_review")
      → accept → generate_enquiries → route_interrupt (pending_step="enquiries_review")
        → accept → generate_interview_plan → route_interrupt (pending_step="interview_plan_review")
          → accept → assemble_plan → finalise_plan → END
```

Sections not in `selected_sections` are skipped. Key concerns always runs (first in chain, unconditional).

### Per-Section Function Logic

Each `generate_X` function checks `hitl_decision` at entry and branches into three paths:

**Accept path:**
- Persist output from `hitl_artifact` (if user edited the structured output) or keep existing state output
- Clear `hitl_decision`, `hitl_artifact`, `pending_step`
- Route to the next selected section, or `assemble_plan` if this is the last section

**Feedback path:**
- Read `prev_version` from existing state field (e.g., `state.get("key_concerns")`)
- Increment version: `version = prev_version + 1`
- Call LLM with `SECTION_FEEDBACK_PROMPT` using previous output + user feedback
- Store updated output back to state
- Route to `route_interrupt` with same `pending_step` for re-review

**No decision (first run):**
- Draft from scratch using existing generation logic
- Set `version=1` on output
- Route to `route_interrupt` with appropriate `pending_step` for first review

### "Next section" routing

Each section function needs a helper or inline logic to determine the next node after accept. Logic:

```
key_concerns → if "doc_request" in selected_sections: generate_doc_request
               elif "additional_enquiries" in selected_sections: generate_enquiries
               elif "interview_plan" in selected_sections: generate_interview_plan
               else: assemble_plan

doc_request → if "additional_enquiries" in selected_sections: generate_enquiries
              elif "interview_plan" in selected_sections: generate_interview_plan
              else: assemble_plan

enquiries → if "interview_plan" in selected_sections: generate_interview_plan
            else: assemble_plan

interview_plan → assemble_plan
```

A shared helper `_next_section(current, selected_sections) -> str` encapsulates this.

### Routing Changes

**`route_sections`** — removed. `dispatch_sections` gets a direct edge to `generate_key_concerns`.

**`_route_from_pending_step`** — new mappings:
- `"key_concerns_review"` → `"generate_key_concerns"`
- `"doc_request_review"` → `"generate_doc_request"`
- `"enquiries_review"` → `"generate_enquiries"`
- `"interview_plan_review"` → `"generate_interview_plan"`

**`_resolve_hitl_artifact`** — new cases for each section's `pending_step`, falling back to existing state output.

**Graph edges** — replace conditional fan-out with sequential edges:
```python
.add_edge("dispatch_sections", "generate_key_concerns")
.add_edge("generate_key_concerns", "assemble_plan")    # removed (now dynamic via Command)
.add_edge("generate_doc_request", "assemble_plan")      # removed (now dynamic via Command)
.add_edge("generate_enquiries", "assemble_plan")         # removed (now dynamic via Command)
.add_edge("generate_interview_plan", "assemble_plan")    # removed (now dynamic via Command)
```

Since routing is now fully dynamic via `Command(goto=...)`, the static edges to `assemble_plan` are replaced by the logic inside each section function. The only static edge needed is `dispatch_sections → generate_key_concerns`.

### SECTION_FEEDBACK_PROMPT

Single parameterized prompt replacing `INTERVIEW_PLAN_FEEDBACK_PROMPT`. Handles all sections.

Parameters:
- `section_name` — human-readable name (e.g., "document requests", "key concerns")
- `prev_version` — JSON of previous section output
- `feedback` — user's feedback text from `hitl_decision.task_summary`
- `initial_review` — case context
- `additional_info` — additional case context
- `knowledge` — section-specific synthesized knowledge (empty string for key_concerns)
- `format` — pydantic output parser format instructions (per-section schema)

The knowledge block is conditionally included — if empty, that section of the prompt is omitted.

Core instructions (carried over from `INTERVIEW_PLAN_FEEDBACK_PROMPT`):
1. Prioritise and apply FEEDBACK exactly as provided
2. Make minimum necessary changes
3. Preserve structure and tone
4. Populate `update_notes` summarising what changed
5. Increment version
6. If feedback is ambiguous, interpret conservatively

### Schema Changes

Add `version` and `update_notes` fields to each section set schema:

- `KeyConcernSet`: add `version: int = 1`, `update_notes: Optional[str] = None`
- `DocRequestSet`: add `version: int = 1`, `update_notes: Optional[str] = None`
- `AdditionalEnquiriesSet`: add `version: int = 1`, `update_notes: Optional[str] = None`
- `InterviewQuestionSets`: add `version: int = 1`, `update_notes: Optional[str] = None`

`ExternalAgentPlan` already has `version` and `update_notes` — no change needed there.

### State Changes

No new state fields required. Existing fields cover all needs:
- `pending_step` — carries section identifier (e.g., `"doc_request_review"`)
- `hitl_decision` — carries intent + feedback text
- `hitl_artifact` — carries user-edited structured output
- Per-section output fields (`key_concerns`, `doc_request`, etc.) — hold previous version for feedback prompt

## Files to Change

1. **`external_agent_graph.py`**
   - Modify each `generate_X` function: add accept/feedback/draft branching
   - Add `_next_section()` helper
   - Update `_route_from_pending_step()` with new mappings
   - Update `_resolve_hitl_artifact()` with per-section fallbacks
   - Replace `route_sections` fan-out with sequential chain
   - Update graph edges

2. **`external_agent_prompts.py`**
   - Add `SECTION_FEEDBACK_PROMPT`
   - Remove or deprecate `INTERVIEW_PLAN_FEEDBACK_PROMPT`

3. **`schemas.py`**
   - Add `version` and `update_notes` to `KeyConcernSet`, `DocRequestSet`, `AdditionalEnquiriesSet`, `InterviewQuestionSets`
