# Restructure DOC_REQUEST_DRAFT_PROMPT around SME gold standards

## Goal
Make the SME-provided gold standards the canonical source of doc-request phrasing. Remove conflicting STYLE rules that force shortening/summarising. Wire `investigation_type` through both draft and feedback paths so the Motor-vs-Property section-selection rule has an anchor.

## Files touched
- `agents/external_agent/prompt_manager/standards.py`
- `agents/external_agent/prompt_manager/external_agent_prompts.py`
- `agents/external_agent/external_agent_graph.py`

---

## A. `standards.py`
- [ ] Replace the TODO placeholder in `DOC_REQUEST_GOLD_STANDARDS` with the SME-pasted content verbatim (General Instructions + Section-Selection Rule + Motor + Property catalogs + embedded Critical Enforcement Rules at the bottom).
- [ ] Keep the embedded "CRITICAL ENFORCEMENT RULES" inside the SME block — they're SME-owned content. Outer `<CRITICAL_RULES>` will reference them by pointer rather than duplicate.

## B. `external_agent_prompts.py` — `DOC_REQUEST_DRAFT_PROMPT`
- [ ] Add `{investigation_type}` template variable. Render in `<CONTEXT>` as `<INVESTIGATION_TYPE>{investigation_type}</INVESTIGATION_TYPE>` above INVESTIGATION PROCESSES.
- [ ] Restructure `<STYLE>` block. Remove items that conflict with SME phrasing:
  - REMOVE: 1–2 sentence cap on `doc_details`.
  - REMOVE: "Citation discipline ... summarise where possible (e.g., 'all bank, credit card and loan account statements' — not a line-by-line listing)".
  - REMOVE: "Illustrative vs distinct" rule.
  - REMOVE: "No filler" rule (conflicts with SME phrasings like "or in which you had access to").
  - KEEP: "No source attribution", "Tone", "Group parties together".
- [ ] Restructure `<TASK>` steps:
  - NEW Step 1: Determine SME section to use from `{investigation_type}`. If "Motor" → use only MOTOR DOCUMENT STANDARDS; if "Property" → use only PROPERTY DOCUMENT STANDARDS. Do not mix.
  - Existing Step 1 becomes Step 2 (read INVESTIGATION PROCESSES, identify permitted doc types).
  - Existing Step 2 becomes Step 3 (read INITIAL REVIEW + ADDITIONAL INFORMATION for case-specific values).
  - Replace existing Step 3 with new wording: "For each permitted document type, locate the matching SME entry in the selected GOLD_STANDARDS section. Reuse SME wording verbatim, replacing only placeholders (XXX/dates/names/identifiers/periods) with case-specific values. Do NOT shorten, summarise, paraphrase, or simplify. If no matching SME entry exists in the selected section, EXCLUDE the document type."
  - Existing Step 4 (validation gate) gains one bullet: "Did I locate a matching SME gold-standard entry and reuse its wording verbatim with only placeholders replaced? If NO → exclude or revise."
- [ ] Add one pointer to `<CRITICAL_RULES>`: "Comply with the additional enforcement rules embedded in `<GOLD_STANDARDS>`."

## C. `external_agent_prompts.py` — `SECTION_FEEDBACK_PROMPT`
- [ ] Add `{investigation_type_block}` placeholder, alongside the existing `{gold_standards_block}` and `{knowledge_block}` slots. Conditional include — empty string for sections that don't need it.

## D. `external_agent_graph.py`
- [ ] Doc-request draft path (line ~916): pass `investigation_type=", ".join(investigation_types)` to `DOC_REQUEST_DRAFT_PROMPT.format(...)`.
- [ ] Doc-request feedback path (line ~876): pass `investigation_type_block=f"<INVESTIGATION_TYPE>{', '.join(investigation_types)}</INVESTIGATION_TYPE>"`.
- [ ] All other `SECTION_FEEDBACK_PROMPT.format(...)` call sites (key_concerns, additional_enquiries, interview_plan — lines 778, 1010, 1140): pass `investigation_type_block=""`.

## E. Smoke check
- [ ] Render `DOC_REQUEST_DRAFT_PROMPT` end-to-end with a mock state to confirm no missing template vars.
- [ ] Render `SECTION_FEEDBACK_PROMPT` for doc-request feedback path and one non-doc-request path (e.g., key_concerns) to confirm both work.

## Out of scope (deferred)
- Investigation-tool endpoint fail-fast change (the prior question — left for later).
- Stream-writer UX for endpoint-down errors.
