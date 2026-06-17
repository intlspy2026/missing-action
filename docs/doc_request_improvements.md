# Document Request Improvements

## Issue 1: Narrative-driven document extraction from Initial Review

**Problem:** Document requests were derived exclusively from INVESTIGATION PROCESSES (methodology), missing documents the claimant's own incident account implicitly requires. For example, if the claimant stated they received texts confirming the appointment, text message records should be requested — but weren't. These are concrete records from the claimant's narrative, fundamentally different from interview topics (party statements, version-of-events, etc.).

**Resolution:** Added a separate narrative-driven document extraction step:

- A dedicated `NARRATIVE_DOC_REQUEST_DRAFT_PROMPT` extracts document types from the claimant's incident account in INITIAL REVIEW
- Capped at 1-2 document types maximum with concise 1-3 line `doc_details`
- Concrete Records rule: party statements about their own account are interview topics, not doc requests — only concrete, obtainable documents are extracted
- Results are cross-checked against methodology-driven docs to prevent duplication
- Heading guidance added so the model can locate the claimant narrative under varied section labels (Claim Lodgement, Loss Description, Circumstances, etc.)

---

## Issue 2: Redundant document types with no factual hook

**Problem:** Work rosters, toll statements, criminal history, insurance claims history, and rideshare receipts were being requested simply because the investigation methodology listed them — regardless of whether the case facts justified them. For example, work rosters appearing when the incident had no employment connection, or insurance history being requested for an insured with zero prior claims.

**Resolution:** Two-layer defense:

### Layer 1: Python pre-filter (`strip_hard_exclusions`)

A deterministic pre-filter in `external_agent_graph.py` runs before the LLM ever sees the methodology data:

- Uses word-boundary regex matching to prevent false positives (e.g., `"work"` matching `"WorkBench"` system name in Initial Review)
- Checks `initial_review` + `additional_info` for case-fact hook keywords per doc type
- No factual hook found → doc type is stripped from INVESTIGATION PROCESSES entirely
- Handles catch-all entries with sub-items individually
- Logs all stripped doc types for debugging

### Layer 2: Prompt-level RULE 3 (INCLUDE-ONLY)

The `DOC_REQUEST_RELEVANCE_PROMPT` enforces a strict include-only relevance filter:

- **Default-exclude framing:** Every document type starts as EXCLUDED, moved to INCLUDED only with a factual hook
- **HARD EXCLUSIONS checklist:** Explicit per-type conditions for work rosters, insurance history, criminal history, rideshare receipts, toll statements, tenancy, and contract of sale
- **CORE METHODOLOGY ITEMS exemption:** Financial statements and bank records always included for fraud investigations
- **Validation gate:** Per-item relevance checking against narrative content (not investigation type label)
- **Sub-item filtering:** Catch-all entries assessed sub-item by sub-item; empty after filtering → excluded entirely

---

## Issue 3: Contents-theft templates applied to building-damage claims

**Problem:** Methodology templates for Policy Exclusion / malicious damage can include contents-theft items such as mobile-phone IMEI records and standalone purchase receipts. When the actual claim concerns building fixtures (e.g., metal piping, screen doors), these items are irrelevant. At the same time, phone records were being excluded too narrowly even when they were needed to confirm the exact sequence of events, and tenancy-specific records (entry/exit condition reports) were not being derived from the narrative.

**Resolution:** Added prompt-level rules in `DOC_REQUEST_RELEVANCE_PROMPT` and `NARRATIVE_DOC_REQUEST_DRAFT_PROMPT`:

- **Mobile Phone Related Documents:** Included only when a mobile phone or similar device is claimed as stolen, damaged, or otherwise part of the loss.
- **Standalone receipt of purchase:** Included only for individual consumer contents (electronics, jewellery, furniture, appliances). Excluded for building fixtures, structural components, plumbing, metal piping, and security fixtures. Evidence of ownership for such items is sought under the existing "Evidence of Ownership" entry.
- **Phone records:** Included when the exact circumstances, sequence of events, or timing around the date of loss need confirmation — for example, communications with tenants, property managers, friends, or other parties regarding access, move-out, or discovery of damage.
- **Tenancy transition narrative rule:** When the claimant's narrative states tenants moved into or out of the insured property close to the date of loss, derive a request for the entry/exit condition report or tenant inspection report for that tenancy change.
- Regression test fixture added in `tests/agents/external_agent/test_doc_request_prompts.py`.
