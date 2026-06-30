# Plan: Financial Statements (Business) variant selection in DOC_REQUEST_SME_PROMPT

## Goal
When INSURED TYPE is "business", the SME prompt must match any "Financial Statements"
PREVIOUS VERSION entry to the "Financial Statements (Business)" gold standard, not the
normal "Financial Statements" entry. Currently it locks onto the exact-name normal match.

## Root cause
1. Business variant selection was buried as a sub-bullet inside RULE 3a (a verbatim-wording
   rule), so it read as a footnote and ran after the LLM had already locked the exact-name hit.
2. The `<INSURED TYPE>` context rendered as `business ("business" or "individual")` — the
   parenthetical made the value look ambiguous.

## Changes (file: src/agents/external_agent/prompt_manager/external_agent_prompts.py)

### Change 1 — Extract a standalone RULE 3a and renumber the 3-series
New structure (siblings, matching how they are already referenced):
- RULE 3a — Financial Statements Business Variant (NEW, standalone, placed BEFORE the verbatim rule)
- RULE 3b — Verbatim SME Phrasing (was RULE 3 / a. Primary)
- RULE 3c — Fallback (was RULE 3 / b. Fallback)
- RULE 3d — Placeholder Filling Exception (was RULE 3c)

RULE 3c (placeholder exception) stays a real exception (only one business doc exists) — its
framing is unchanged apart from the number.

### Change 2 — Fix ambiguous INSURED TYPE context block
Remove the `("business" or "individual")` parenthetical so the value renders unambiguously.

---

## Exact edits

### Edit 1 — RULE 2.5 gold-standard-match reference
BEFORE:
```
- **Gold standard match (RULE 3a)**: doc_type MUST use the gold standard entry name
```
AFTER:
```
- **Gold standard match (RULE 3b)**: doc_type MUST use the gold standard entry name
```

### Edit 2 — RULE 2.5 fallback reference
BEFORE:
```
- **Fallback (RULE 3b, no match)**: doc_type is the PREVIOUS VERSION doc_type.
```
AFTER:
```
- **Fallback (RULE 3c, no match)**: doc_type is the PREVIOUS VERSION doc_type.
```

### Edit 3a — Insert new RULE 3a; convert RULE 3 header + "a. Primary" into RULE 3b
BEFORE:
```
**RULE 3 - VERBATIM SME PHRASING (with fallback)**: For every document type in PREVIOUS VERSION:
a. **Primary (SME match exists)**: When a matching entry exists in the provided GOLD_STANDARDS, doc_details MUST mirror the SME wording verbatim. Leave ALL
```
AFTER:
```
**RULE 3a - FINANCIAL STATEMENTS BUSINESS VARIANT (applies when INSURED TYPE is "business")**:
When INSURED TYPE is "business" and PREVIOUS VERSION contains any "Financial Statements" entry, you MUST match it to the "Financial Statements (Business)" gold standard entry — NOT the normal "Financial Statements" entry. "Financial Statements" and "Financial Statements (Business)" are the same document class; the choice between them is decided by INSURED TYPE only, never by name similarity to the PREVIOUS VERSION doc_type. This rule overrides exact-name matching. When INSURED TYPE is "individual", match the normal "Financial Statements" entry.

**RULE 3b - VERBATIM SME PHRASING (SME match exists)**: For every document type in PREVIOUS VERSION, when a matching entry exists in the provided GOLD_STANDARDS, doc_details MUST mirror the SME wording verbatim. Leave ALL
```
(The following continuation lines "   placeholders unchanged — ..." / "   as written in the
SME entry..." / "   wording when an SME entry exists..." remain as wrapped text under RULE 3b.)

### Edit 3b — Remove the buried business-variant block; fix negative-example rule ref
BEFORE (delete this entire block):
```
    **Business variant selection (MANDATORY when insured type is "business")**:
    When insured type is "business", you MUST search the GOLD_STANDARDS for a business-specific variant of the matched document class before locking in the match. A business-specific variant is identified by "(Business)" suffix or "Business" in the entry name (e.g. "Financial Statements (Business)" is the business variant of "Financial Statements"). If a business variant exists, you MUST select it — do NOT select the normal variant.

    When insured type is "individual", select the normal variant.

    Example: PREVIOUS VERSION has "Financial Statements", INSURED TYPE is "business".
    Both "Financial Statements" and "Financial Statements (Business)" exist in GOLD_STANDARDS — they are the same document class.
    CORRECT: match to "Financial Statements (Business)" — then apply RULE 3c to fill placeholders.
    WRONG: match to "Financial Statements" — this is the individual variant, not for business insured type.

    Currently, "Financial Statements" and "Financial Statements (Business)" are paired variants. When insured type is "business", any PREVIOUS VERSION entry matching this document class MUST be matched to "Financial Statements (Business)".

    Negative example: "Evidence to confirm movements" describes an investigative purpose, not a document class — no gold standard match. Use RULE 3b for purpose-based doc_types that do not name a specific document class matching a gold standard entry.
```
AFTER (keep only the negative example, with ref updated to RULE 3c):
```
    Negative example: "Evidence to confirm movements" describes an investigative purpose, not a document class — no gold standard match. Use RULE 3c for purpose-based doc_types that do not name a specific document class matching a gold standard entry.
```

### Edit 3c — Match-rule internal fallback ref
BEFORE:
```
Do NOT fall back to RULE 3b for entries that are sub-types or variants of an existing gold standard entry.
```
AFTER:
```
Do NOT fall back to RULE 3c for entries that are sub-types or variants of an existing gold standard entry.
```

### Edit 3d — Renumber "b. Fallback" into standalone RULE 3c
BEFORE:
```
b. **Fallback (no SME match)**: When a document type has no matching entry in the provided GOLD_STANDARDS, INCLUDE it using a fallback draft: write a full
   instruction-style request (e.g., "A copy of _", "Fully itemised _", "Provide _"), grounded in the PREVIOUS VERSION doc_details and case context. Match the
    cadence and neutral tone of the SME exemplars. Do NOT produce short labels or one-line summaries. MUST NOT list as examples any document type that has a
    standalone entry in GOLD_STANDARDS (e.g., work rosters, timesheets, rideshare receipts, toll records, police documents, medical records). Those pass or
    fail on their own relevance — re-listing them in a fallback entry's doc_details bypasses the methodology.
```
AFTER:
```
**RULE 3c - FALLBACK (no SME match)**: When a document type has no matching entry in the provided GOLD_STANDARDS, INCLUDE it using a fallback draft: write a full instruction-style request (e.g., "A copy of _", "Fully itemised _", "Provide _"), grounded in the PREVIOUS VERSION doc_details and case context. Match the cadence and neutral tone of the SME exemplars. Do NOT produce short labels or one-line summaries. MUST NOT list as examples any document type that has a standalone entry in GOLD_STANDARDS (e.g., work rosters, timesheets, rideshare receipts, toll records, police documents, medical records). Those pass or fail on their own relevance — re-listing them in a fallback entry's doc_details bypasses the methodology.
```

### Edit 4 — RULE 3c -> RULE 3d (placeholder exception); "RULE 3a requires" -> "RULE 3b requires"
BEFORE:
```
**RULE 3c - PLACEHOLDER FILLING EXCEPTION**: RULE 3a requires ALL placeholders to pass through verbatim. However, for the following THREE specific gold standard entries ONLY, you MUST fill the indicated placeholder with case-specific information from the context:
```
AFTER:
```
**RULE 3d - PLACEHOLDER FILLING EXCEPTION**: RULE 3b requires ALL placeholders to pass through verbatim. However, for the following THREE specific gold standard entries ONLY, you MUST fill the indicated placeholder with case-specific information from the context:
```

### Edit 5 — TASK Step 2 (matching pass)
BEFORE:
```
   For each PREVIOUS VERSION entry, identify its gold standard match (or note "no match" for RULE 3b fallback). When multiple variants exist for the same document class, apply the business variant selection in RULE 3a's match rule. Build a mental list. DO NOT produce any JSON output yet.
```
AFTER:
```
   For each PREVIOUS VERSION entry, identify its gold standard match (or note "no match" for RULE 3c fallback). When INSURED TYPE is "business" and the entry is a "Financial Statements" class entry, apply RULE 3a to select the "Financial Statements (Business)" variant. Build a mental list. DO NOT produce any JSON output yet.
```

### Edit 6 — TASK Step 4a
BEFORE:
```
   a. Gold standard match → apply RULE 3a (verbatim SME wording, with business variant selection if applicable). For "Signed Authorities", "Witness Contact Details (Known)", and "Financial Statements (Business)", apply RULE 3c (fill placeholders from context) instead of RULE 3a (verbatim). Apply RULE 2.5 (gold standard name + timeframe from PREVIOUS VERSION doc_details if present).
```
AFTER:
```
   a. Gold standard match → apply RULE 3a first (Financial Statements business variant selection, when INSURED TYPE is "business"), then apply RULE 3b (verbatim SME wording). For "Signed Authorities", "Witness Contact Details (Known)", and "Financial Statements (Business)", apply RULE 3d (fill placeholders from context) instead of RULE 3b (verbatim). Apply RULE 2.5 (gold standard name + timeframe from PREVIOUS VERSION doc_details if present).
```

### Edit 7 — TASK Step 4b
BEFORE:
```
   b. No match → apply RULE 3b (full instruction-style fallback grounded in PREVIOUS VERSION doc_details and case context) + RULE 2.5 (use PREVIOUS VERSION doc_type if no gold standard name).
```
AFTER:
```
   b. No match → apply RULE 3c (full instruction-style fallback grounded in PREVIOUS VERSION doc_details and case context) + RULE 2.5 (use PREVIOUS VERSION doc_type if no gold standard name).
```

### Edit 8 — Validation checklist (placeholder ref)
BEFORE:
```
    - Verbatim SME wording (or RULE 3c placeholder filling for the 3 exception types)?
```
AFTER:
```
    - Verbatim SME wording (or RULE 3d placeholder filling for the 3 exception types)?
```
(The next validation line "(RULE 3a)?" already points at the business rule and now stays RULE 3a — no change.)

### Edit 9 — Context: BUSINESS NAME ref
BEFORE:
```
The BUSINESS NAME for Financial Statements (Business) insertion (RULE 3c):
```
AFTER:
```
The BUSINESS NAME for Financial Statements (Business) insertion (RULE 3d):
```

### Edit 10 — Context: DIRECTOR NAME ref
BEFORE:
```
The DIRECTOR NAME for Financial Statements (Business) insertion (RULE 3c):
```
AFTER:
```
The DIRECTOR NAME for Financial Statements (Business) insertion (RULE 3d):
```

### Edit 11 — Context: INSURED TYPE block (Change 2 — remove ambiguous parenthetical)
BEFORE:
```
The INSURED TYPE determines business-specific gold standard matching (RULE 3a business variant selection):
<INSURED TYPE>
{insured_type} ("business" or "individual")
</INSURED TYPE>
```
AFTER:
```
The INSURED TYPE for this case (drives RULE 3a — Financial Statements business variant selection):
<INSURED TYPE>
{insured_type}
</INSURED TYPE>
```

---

## Verification after applying
1. `grep -n "RULE 3" src/agents/external_agent/prompt_manager/external_agent_prompts.py`
   — within the SME prompt (lines ~249-383) every RULE 3 reference must be 3a/3b/3c/3d with
   the new meanings; no stale "RULE 3a" meaning verbatim, no "RULE 3c" meaning placeholder.
2. `grep -n "business variant selection\|Business variant selection" ...` — must appear only
   in the new RULE 3a and TASK Step 2, not inside the verbatim rule.
3. `grep -n '("business" or "individual")' ...` — must return nothing (parenthetical removed).
4. Confirm the DOC_REQUEST_FEEDBACK_PROMPT (separate, uses RULE A/B/C/D/F) is untouched.
5. Re-run the failing case: insured_type "business" + PREVIOUS VERSION "Financial Statements"
   must output doc_type "Financial Statements (Business)" with RULE 3d placeholders filled.

## Notes
- No code/data-flow change needed: insured_type is already derived ("yes" -> "business") and
  passed at external_agent_graph.py:1416; both gold-standard variants are already in
  standards.py. This is a prompt-only fix.
- RULE 3d (placeholder exception) framing is intentionally kept as an exception (only one
  business document exists), per user guidance.
