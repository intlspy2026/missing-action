# Prompt Manager Files

## `external_agent_prompts.py` (689 lines)
All LLM prompt templates for the external agent workflow: `KEY_CONCERNS_DRAFT_PROMPT`, doc requests pipeline (`DOC_REQUEST_RELEVANCE_PROMPT` → `DOC_REQUEST_SME_PROMPT` → `NARRATIVE_DOC_REQUEST_DRAFT_PROMPT`), additional enquiries pipeline (`ADDITIONAL_ENQUIRIES_RELEVANCE_PROMPT` → `ADDITIONAL_ENQUIRIES_FINAL_PROMPT`), plus shared `SECTION_FEEDBACK_PROMPT`, `SECTION_FEEDBACK_KNOWLEDGE_BLOCK`, and `EXTERNAL_AGENT_SYSTEM_PROMPT`.

## `knowledge_prompts.py` (188 lines)
Parser prompts for extracting structured methodology from the textbook: `DOC_REQUEST_PARSER_SYSTEM_PROMPT`/`PROMPT` and `ENQUIRIES_PARSER_SYSTEM_PROMPT`/`PROMPT` with investigation-type/sub-type matching. Also includes `SECTION_KNOWLEDGE_REPORT_*` prompts for synthesising retrieved knowledge and `DEDUP_PROMPT` for deduplication.

## `standards.py` (110 lines)
SME-authored gold standard document request phrasing, LOB-split: `MOTOR_DOC_REQUEST_GOLD_STANDARDS` and `PROPERTY_DOC_REQUEST_GOLD_STANDARDS`, each with a pre-wrapped `_BLOCK` variant for the feedback prompt's include-or-omit slot.
