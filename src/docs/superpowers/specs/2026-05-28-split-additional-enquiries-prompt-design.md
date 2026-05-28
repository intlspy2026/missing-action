# Split Additional Enquiries Draft Prompt Into Two

**Date:** 2026-05-28
**Status:** Approved

## Motivation

The current `ADDITIONAL_ENQUIRIES_DRAFT_PROMPT` is a single monolithic prompt that does everything in one LLM call:
1. Relevance filtering of methodology-driven enquiries
2. Case-specific contextualisation
3. Narrative-driven enquiry derivation from the claimant's incident account
4. Theme-based aggregation
5. Final formatting/output

This mirrors the earlier document request flow, which was already split into:
- `DOC_REQUEST_RELEVANCE_PROMPT` — relevance filtering
- `DOC_REQUEST_SME_PROMPT` — SME-standard wording application

Splitting enables focused prompts, easier debugging, and aligns with the document request pattern.

## Design

### Two-prompt split

**Prompt 1 — `ADDITIONAL_ENQUIRIES_RELEVANCE_PROMPT`**: Methodology-driven relevance filter + case contextualisation
- Takes INVESTIGATION PROCESSES knowledge
- Filters: relevance check against case facts, conditional qualifiers, party scope, external scope only
- Contextualises: rewrites template enquiries with case-specific names, dates, locations
- Does NOT derive narrative enquiries, does NOT aggregate by theme
- Output: flat `AdditionalEnquiriesSet` — one entry per relevant methodology enquiry

**Prompt 2 — `ADDITIONAL_ENQUIRIES_FINAL_PROMPT`**: Narrative derivation + merge + aggregation + final polish
- Takes `{prev_version}` (prompt 1 output) + INITIAL REVIEW claimant narrative
- Derives narrative-driven field enquiries from the claimant's incident account
- Dedup: checks narrative-derived against methodology-derived, merges overlapping ones
- Theme-based aggregation: collapses both sources into ~one enquiry per theme
- Applies neutral language, removes filler
- Output: final concise `AdditionalEnquiriesSet`

### Rule redistribution

| Rule | Current prompt | Prompt 1 (Relevance) | Prompt 2 (Final) |
|------|---------------|---------------------|-------------------|
| RULE 1 — Source restriction | Both sources | (a) INVESTIGATION PROCESSES only | (a) PREVIOUS VERSION + (b) narrative |
| RULE 2 — Party scope | Yes | Yes | Yes |
| RULE 3 — Contextualise | Yes (methodology) | Yes | No (already done by prompt 1) |
| RULE 4 — External scope only | Yes | Yes | Yes |
| RULE 5 — Relevance filter | Yes | Yes | No (already done by prompt 1 for methodology; replaced by Narrative Guardrails for narrative) |
| RULE 6 — Neutral language | Yes | Yes | Yes |
| NARRATIVE GUARDRAILS | N/A | N/A | New — source, scope, and dedup rules for narrative derivation |

### Graph changes

`external_agent_graph.py` — `generate_enquiries_async` (line 1435):

**Before:** Single LLM call:
```
RETRIEVE knowledge → ADDITIONAL_ENQUIRIES_DRAFT_PROMPT → parsed → HITL review
```

**After:** Two LLM calls:
```
RETRIEVE knowledge → ADDITIONAL_ENQUIRIES_RELEVANCE_PROMPT (call 1) → prev_version
                  → ADDITIONAL_ENQUIRIES_FINAL_PROMPT (call 2, with prev_version) → parsed → HITL review
```

Import change: `ADDITIONAL_ENQUIRIES_DRAFT_PROMPT` → `ADDITIONAL_ENQUIRIES_RELEVANCE_PROMPT, ADDITIONAL_ENQUIRIES_FINAL_PROMPT`

## Affected Files

### Must modify
1. `prompt_manager/external_agent_prompts.py`
   - Remove: `ADDITIONAL_ENQUIRIES_DRAFT_PROMPT` (lines 309-404)
   - Add: `ADDITIONAL_ENQUIRIES_RELEVANCE_PROMPT` (before line 406)
   - Add: `ADDITIONAL_ENQUIRIES_FINAL_PROMPT` (before line 406)

2. `external_agent_graph.py`
   - Line 22: Update import from `ADDITIONAL_ENQUIRIES_DRAFT_PROMPT` to `ADDITIONAL_ENQUIRIES_RELEVANCE_PROMPT, ADDITIONAL_ENQUIRIES_FINAL_PROMPT`
   - Lines 1519-1540: Replace single LLM call with two-call flow (relevance → prev_version → final → parsed)

### Optional follow-up
- `NARRATIVE_DOC_REQUEST_DRAFT_PROMPT` could be merged into the same pattern if desired

## Spec Self-Review

- **Placeholder scan:** No TBDs or TODOs. All rules, tasks, and variables are specified.
- **Internal consistency:** Rule redistribution table confirms no gaps or overlaps. Prompt 1's output schema (`AdditionalEnquiriesSet`) is the same as prompt 2's, ensuring seamless chaining.
- **Scope check:** Focused on splitting one prompt. Graph changes are minimal (1 import change, ~15 lines of logic). No schema or output format changes.
- **Ambiguity check:** No ambiguities. Both prompts clearly state what they do and don't do.
