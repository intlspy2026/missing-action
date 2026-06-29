# Additional Enquiries — STYLE-Based Merge Design

## Problem

The co-location merge / field-visit test added to both the RELEVANCE and FINAL prompts has not improved merge accuracy. The LLM fails to recognise that contextualised entries at the same location belong together because after independent contextualisation they reference different names and details, breaking the text-level match that the test depends on.

## Solution

Remove the explicit co-location merge (field-visit test) from both calls entirely. Replace it with a STYLE-level "one enquiry per theme" instruction in Call 1, while keeping the existing same-theme merge tests (RULE 6 in CRITICAL RULES) unchanged in Call 2.

## Changes

### Call 1 — ADDITIONAL_ENQUIRIES_RELEVANCE_PROMPT

**STYLE section**: Add a merge instruction:

> `- **One enquiry per theme**: INVESTIGATION PROCESSES lists multiple enquiries flatly, but many belong to the same investigative theme. Recognise the themes and aggregate all enquiries that belong to the same theme into a single output enquiry — combining their sub-tasks into enquiry_detail. Do NOT output one entry per methodology line where mergeable themes exist. Do NOT merge entries targeting fundamentally different respondent categories (e.g., a formal interview of a specific named party vs. a general canvass for unknown witnesses) — these require different types of engagement even if at the same location.`

**TASK Step 5**: Remove entirely (the field-visit test + examples). TASK steps go from 1-5 to 1-4.

### Call 2 — ADDITIONAL_ENQUIRIES_FINAL_PROMPT

**TASK Step 5b**: Replace field-visit test with reference to RULE 6:

> `5. **Aggregate by theme** — apply RULE 6 (AGGREGATE BY THEME) to the pooled list:
>    a. Pool ALL enquiries (methodology + narrative-derived) into a single list.
>    b. Apply RULE 6 including the same-theme merge tests. Merge every group that shares a theme into ONE entry combining all sub-tasks into enquiry_detail.
>    c. Entries at DIFFERENT locations stay separate. Entries targeting fundamentally different respondent categories (e.g., interviewing a specific named party vs. canvassing for general witnesses) stay separate even if at the same location — these require different types of engagement.
>    d. If no entries merge, no aggregation is needed — output as-is.
>    e. Output MUST be one enquiry per theme, not one per source line.`

**RULE 5c** (dedup guardrail) and **RULE 6 tests (a-d)** (same goal, overlapping purpose, shared subject, same named individual): No changes — remain in CRITICAL RULES.

### Unchanged

- Call 1 CRITICAL RULES (RULE 1-6)
- Call 2 CRITICAL RULES (RULE 0-5, RULE 6 preambles + tests a-d)
- DUI CCTV exception in both prompts
- FEEDBACK prompt
- Output format / schema

## Rationale

- The old single-prompt approach worked with a STYLE-level "one enquiry per theme" instruction — no hard merge tests needed
- Removing the field-visit test eliminates the text-matching trap where the LLM fails to merge because contextualised entries don't share exact location/person names
- Call 2's same-theme tests (a-d) are retained because they test for investigative-goal alignment, not location matching — the LLM can reason about whether entries serve the same purpose
- Call 1's STYLE merge gives the LLM flexibility to group methodology entries without being forced through a narrow test

## Files Changed

- `src/agents/external_agent/prompt_manager/external_agent_prompts.py`: 2 edits (Call 1 STYLE + remove Step 5; Call 2 Step 5b)
