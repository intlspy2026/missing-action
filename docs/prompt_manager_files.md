# Prompt Manager Files

## `external_agent_prompts.py` (689 lines)

All LLM prompt templates for the external agent workflow.

### Document requests (3-call pipeline)
1. **`DOC_REQUEST_RELEVANCE_PROMPT`** — Filters methodology document templates using the include-only gate (RULE 3): a document is included only if it is core to the investigation type or supported by a specific fact in the case narrative. Applies source restriction, deduplication, and scope rules.
2. **`DOC_REQUEST_SME_PROMPT`** — Applies SME-quality phrasing and gold standards to the filtered document types. Rewrites generic template wording into crisp, professional request language.
3. **`NARRATIVE_DOC_REQUEST_DRAFT_PROMPT`** — Derives 0-2 additional document types from the claimant's first-hand incident account narrative. Targets concrete, obtainable records implied by the narrative (receipts, bookings, communications, medical records). Includes the Causal Explanation rule for deriving documents from explanations that imply a verifiable external entity.

### Additional enquiries (2-call pipeline)
1. **`ADDITIONAL_ENQUIRIES_RELEVANCE_PROMPT`** — Filters methodology enquiry templates by relevance to case facts. Excludes enquiries whose target entity is not named in INITIAL REVIEW or ADDITIONAL INFORMATION. Contextualises surviving enquiries with case-specific names, dates, and locations. Does NOT aggregate — each passing template produces one output entry.
2. **`ADDITIONAL_ENQUIRIES_FINAL_PROMPT`** — Takes filtered/contextualised enquiries from Prompt 1, derives narrative-driven enquiries from the claimant's incident account, merges both sources, aggregates by underlying theme, and applies final polish with neutral language. Includes RULE 0 which returns empty if PREVIOUS VERSION is empty.

### Other section prompts
- **`KEY_CONCERNS_DRAFT_PROMPT`** — Drafts the investigation brief's key concerns from IRO analysis, policy details, and background checks.
- **`INTERVIEW_PLAN_DRAFT_PROMPT`** — Generates a PEACE-model interview plan structured around the investigation type's question topics.
- **`INTERVIEW_PLAN_FEEDBACK_PROMPT`** — Revises the interview plan based on reviewer feedback.
- **`INTERVIEW_DOC_REQUEST_PROMPT`** — Drafts interview-specific document requests.

### Shared
- **`EXTERNAL_AGENT_SYSTEM_PROMPT`** — Senior insurance fraud investigator role.
- **`SECTION_FEEDBACK_PROMPT`** — Generic feedback revision prompt reused by all sections (key concerns, doc requests, additional enquiries, interview plan). Supports knowledge block, gold standards block, and investigation type block injection via include-or-omit slots.
- **`SECTION_FEEDBACK_KNOWLEDGE_BLOCK`** — Wraps INVESTIGATION PROCESSES content in XML tags for injection into feedback context.

## `knowledge_prompts.py` (188 lines)

Parser prompts for extracting structured methodology from the textbook and synthesising retrieved knowledge.

### Methodology extraction
- **`DOC_REQUEST_PARSER_SYSTEM_PROMPT`** / **`DOC_REQUEST_PARSER_PROMPT`** — Extracts document request methodology items from the textbook for a given investigation type and optional sub-type. Matches investigation type first, then filters by sub-type if specified. Returns structured JSON with `doc_type` and `doc_details` per item.
- **`ENQUIRIES_PARSER_SYSTEM_PROMPT`** / **`ENQUIRIES_PARSER_PROMPT`** — Extracts additional enquiry methodology items from the textbook for a given investigation type and optional sub-type. Hardcoded to return empty for NDM subtypes (Criminal History, Demolition, Claim and Insurance History, Use of Property) that have no additional enquiries.

### Multi-investigation-type deduplication
- **`DEDUP_PROMPT`** — When a case has multiple investigation types, doc request knowledge may contain the same document type across multiple types. This prompt deduplicates: if a document type appears identically across two or more investigation types, it is collapsed into a single entry appended to the output without duplicating it per type.

### Knowledge synthesis
- **`SECTION_KNOWLEDGE_REPORT_SYSTEM_PROMPT`** / **`SECTION_KNOWLEDGE_REPORT_PROMPT`** — Synthesises retrieved knowledge chunks from the delta table into a structured report for a specific section (e.g., interview plan question categories, underwriting/financial context).

## `standards.py` (110 lines)

SME-authored gold standard document request phrasing, split by LOB (Motor / Property).

- **`MOTOR_DOC_REQUEST_GOLD_STANDARDS`** — Canonical phrasing for Motor claim document requests (e.g., photographs of vehicle, CTP/insurance certificates, finance/lease documents, motor sport/racetrack evidence).
- **`PROPERTY_DOC_REQUEST_GOLD_STANDARDS`** — Canonical phrasing for Property claim document requests (e.g., photographs of property, property manager correspondence, business records, booking schedules).
- Each has a pre-wrapped **`_BLOCK`** variant (`MOTOR_DOC_REQUEST_GOLD_STANDARDS_BLOCK`, `PROPERTY_DOC_REQUEST_GOLD_STANDARDS_BLOCK`) for injection into the feedback prompt's include-or-omit `{gold_standards_block}` slot. Draft prompts reference the raw constant via their own `<GOLD_STANDARDS>` tag.
