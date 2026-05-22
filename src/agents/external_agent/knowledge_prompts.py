RETRIEVAL_TASKS = {
    "doc_requests": {
        "task": "Determine what are the documents to be requested given the provided investigation type",
        "stopping_criteria": "You have clearly put down all the documents required for external investigation for the provided investigation type"
    },
    "additional_enquiries": {
        "task": "Determine the additional enquiries required for external investigation given the provided investigation type",
        "stopping_criteria": "You have clearly put down all the additional enquiries required for external investigation for the provided investigation type"
    },
    # --- Commented out: interview plan retrieval tasks not yet active ---
    # "question_categories": {
    #     "task": """
    # Determine interview question categories for the given investigation type and extract all questions per category except for underwriting and financial history related
    # categories.
    #     For example, if the investigation type is 'Policy Exclusion | DUI investigation', you should call 'query_investigation_processes' to first assess the categories:
    #     - "List the category names of interview questions for a Policy Exclusion - DUI"
    #     Then, review the response and call 'query_investigation_processes' again with the following queries in parallel:
    #     - "Extract a list of all suggested interview questions in the category <insert category name> associated with Policy Exclusion DUI-related investigation, verbatim
    # stated in the context."
    # """,
    #     "stopping_criteria": "You have clearly stated all interview question categories(except underwriting and financial history) and all discovered categories have had all questions extracted verbatim"
    # },
    # "underwriting_financial": {
    #     "task": """
    # Determine whether underwriting matters and/or financial history questions should be asked for the given investigation type, and if so, extract.
    #     For example, if the investigation type is 'Policy Exclusion | DUI investigation', you should call 'query_investigation_processes' with the following queries in parallel:
    #     - Extract a list of all suggested interview questions for Underwriting Matters/Canvassing associated with Policy Exclusion DUI-related investigation, verbatim as it is
    # stated in the context.
    #     - Extract a list of all suggested interview questions for Financial History associated with Policy Exclusion DUI-related investigation, verbatim as it is stated in the
    # context.
    #
    #  - There can be investigation types for which there will be no questions related to Underwriting Matters/Canvassing and Financial History so do not create any categories
    # """,
    #     "stopping_criteria": "You have determined whether underwriting and financial history questions apply and extracted them if so"
    # },
}


KNOWLEDGE_RETRIEVAL_TASK_PROMPT = """
<TASK>
You are retrieving knowledge for a particular task.
Your goal is COMPLETE whwen you have extracted the required information for the task.
Here is your task:
{task}
</TASK>

<TOOLS>
You have access to three main tools:
1. 'query_investigation_processes' -> fraud-specific textbooks with investigation methodologies
2. 'search_complete' -> indicate that search is complete and present results
3. 'think_tool' -> for reflection and strategic planning during search
**CRITICAL: Use think_tool after each search to reflect on results and plan next steps.**
</TOOLS>

<INSTRUCTIONS>
1. **Be specific** - Phrase your searches specifically to the particular task
2. **After each search, use the think_tool to pause and assess** - Do I have enough to information?
</INSTRUCTIONS>

<STOP_WHEN>
{stopping_criteria}
</STOP_WHEN>

<OUTPUT>
Compile all search queries and answers as follows:
{format}
Do NOT output any extra commentary outside this JSON. Only return this.
</OUTPUT>
-----------------------------------------------------------
The identified investigation type is:
Note: it will be presented as <investigation type> | <sub-type if present>
<INVESTIGATION_TYPE>
{investigation_type}
</INVESTIGATION_TYPE>
"""


KNOWLEDGE_RETRIEVAL_SYSTEM_PROMPT = """
You are a fraud knowledge-retrieval assistant. You will receive an investigation type and your goal is to retrieve relevant knowledge using your tools.
"""


# --- Commented out: replaced by per-section SECTION_KNOWLEDGE_REPORT_PROMPT ---
# KNOWLEDGE_REPORT_SYSTEM_PROMPT = """
# You are an insurance report drafting assistant. Your task is to synthesise retrieved knowledge into a structured report which contains all the searches for the provided investigation
# type .
# """
#
# KNOWLEDGE_REPORT_PROMPT = """
# <TASK>
# Using the provided retrieved knowledge, produce a structured report for the given investigation type.
#
# You MUST:
# - Use ONLY the provided knowledge.
# - Not introduce new content
# - Not paraphrase questions
# - Preserve wording of concerns raised.
# </TASK>
#
# <INPUTS>
# <INVESTIGATION_TYPE>
# {investigation_type}
# </INVESTIGATION_TYPE>
#
# <RETRIEVED_KNOWLEDGE>
# {knowledge_set}
# </RETRIEVED_KNOWLEDGE>
# </INPUTS>
#
# <OUTPUT>
# Compile your report into the following format:
# {format}
# Do NOT output any extra commentary outside this JSON. Only return this.
#
# </OUTPUT>
# """


SECTION_KNOWLEDGE_REPORT_SYSTEM_PROMPT = """
You are an insurance report drafting assistant. Your task is to synthesise retrieved knowledge into a structured report for a specific section of an external investigation.
"""

SECTION_KNOWLEDGE_REPORT_PROMPT = """
<TASK>
Using the provided retrieved knowledge, produce a structured report for the {section_name} section of an external investigation for the given investigation type.

You MUST:
- Use ONLY the provided knowledge.
- Not introduce new content.
- Not paraphrase — preserve original wording.
- Extract ALL relevant items for this section.
</TASK>

<INPUTS>
<INVESTIGATION_TYPE>
{investigation_type}
</INVESTIGATION_TYPE>

<RETRIEVED_KNOWLEDGE>
{knowledge_set}
</RETRIEVED_KNOWLEDGE>
</INPUTS>

<OUTPUT>
{format}
Do NOT output any extra commentary outside this JSON. Only return this.
</OUTPUT>
"""


# ------------------------------------------------------------------------------
# Chunk-based parser prompts (delta-table path)
# Used by _retrieve_section_chunks_async to convert raw textbook chunks into
# structured DocRequestSet / AdditionalEnquiriesSet, bypassing the RAG endpoint.
# ------------------------------------------------------------------------------

DOC_REQUEST_PARSER_SYSTEM_PROMPT = """
You are an extractor and data transformation assistant.

Your task is to extract all document request items from the textbook that relate to the given investigation type (and sub-type) and convert them into structured JSON.

# Instructions
1. **Identify the stop marker first.** Scan the chunk for a blurb that introduces conditional follow-up documents — e.g., *"If further concerns arise from the initial review and/or interview, IROs can request further documents..."*. If found, mark its position. ALL content from that position to the end of the chunk is OUT OF SCOPE, including any document lists or section headings (e.g. the investigation type name repeated) that appear below it — they are sub-content of the excluded block, NOT a resumption. If no such blurb exists, the entire chunk is in scope.
2. Locate the Document Requests section(s) for the given investigation type/sub-type, considering only content ABOVE the stop marker.
   - The investigation type may include a sub-type separated by "|". If a sub-type is given, extract ONLY items relevant to that sub-type.
   - For example, for "Policy Exclusions | DUI", extract only DUI-related documents even if the textbook also lists items for other Policy Exclusions sub-types.
   - If no sub-type is given, extract every document item under the investigation type.
3. Extract each in-scope document item into structured JSON:
   - `doc_type`: the item name, verbatim.
   - `doc_details`: any inline qualifiers, parenthetical notes, or nested sub-bullets associated with that item. If the item has nested sub-bullets in the textbook (e.g., "Signed authorities for the following: <list of authorities>"), fold those sub-bullets into `doc_details` as a single coherent string. Empty string if the textbook has no qualifier.
   - Maintain the order given in the textbook.

# Rules
- Preserve item names verbatim. Fix only obvious truncation or typos.
- Extract ALL in-scope items (above the stop marker). Missing in-scope items will make the response incomplete.
- Do NOT extract preamble prose (e.g., "Documents are requested from all policy holders…", "The list below is not exhaustive…") — only the document items themselves.
- Do NOT add new items or infer items not in the textbook.
- Output valid JSON ONLY.
"""


DOC_REQUEST_PARSER_PROMPT = """
# Output Format
Use this schema:
{format}

# Here is the textbook information
<TEXTBOOK>
{chunks}
</TEXTBOOK>

# Proceed to extract the document items for investigation type:
<INVESTIGATION TYPE>
{investigation_type}
</INVESTIGATION TYPE>
"""


ENQUIRIES_PARSER_SYSTEM_PROMPT = """
You are an extractor and data transformation assistant.

Your task is to extract all additional enquiry items from the textbook that relate to the given investigation type (and sub-type) and convert them into structured JSON.

# Instructions
1. Locate the Additional Enquiries section(s) in the textbook for the given investigation type/sub-type.
   - The investigation type may include a sub-type separated by "|". If a sub-type is given, extract ONLY items relevant to that sub-type.
   - If no sub-type is given, extract every enquiry item under the investigation type.
2. Extract each enquiry item into structured JSON:
   - `enquiry`: the enquiry directive or topic, verbatim.
   - `enquiry_detail`: any nested sub-bullets, suggested questions, or qualifiers associated with that enquiry. If the item has nested sub-bullets (e.g., "Canvass the vehicle details and use: <list of details to establish>"), fold the sub-bullets into `enquiry_detail` as a single coherent string. Empty string if the textbook has no qualifier.
   - Maintain the order given in the textbook.

# Rules
- Preserve enquiry text verbatim. Fix only obvious truncation or typos.
- Extract ALL relevant items. Missing items will make the response incomplete.
- Do NOT extract preamble prose (e.g., "Include all additional enquiries to be completed by the External Agent.") — only the enquiry items themselves.
- Do NOT add new items or infer items not in the textbook.
- Output valid JSON ONLY.
"""


ENQUIRIES_PARSER_PROMPT = """
# Output Format
Use this schema:
{format}

# Here is the textbook information
<TEXTBOOK>
{chunks}
</TEXTBOOK>

# Proceed to extract the enquiry items for investigation type:
<INVESTIGATION TYPE>
{investigation_type}
</INVESTIGATION TYPE>
"""


# Generic dedup prompt — used for both document requests and additional enquiries.
# Parameterised by {item_type} (e.g., "documents", "enquiries") and {items} block.
DEDUP_PROMPT = """
You are reviewing {item_type} for semantic duplication.

You will receive a list of {item_type}. Each item has:
- item_id
- text

Your task is to identify duplicate or near-duplicate items.

CRITICAL RULE:
Only identify duplicates ACROSS DIFFERENT item_set_id values.

- You must NOT remove or mark duplicates within the same item_set_id.
- Even if two items within the same set are identical, ignore them.

DUPLICATE DEFINITION:
A duplicate means:
- both items refer to materially the same thing, AND
- the removed item adds no additional investigative value.

Do NOT mark items as duplicates merely because they:
- relate to the same topic
- use similar wording
- could be requested or asked together

If an item introduces a different detail, document, person, timeframe, or evidentiary angle, it is NOT a duplicate.

If unsure, KEEP BOTH.

OUTPUT RULES:
- For each duplicate group:
  - choose ONE canonical_item_id to retain
  - list duplicate_item_ids to remove
- Only include groups where the duplicates span DIFFERENT item_set_id values.

Return valid JSON only in this format:

{{
  "duplicate_groups": [
    {{
      "canonical_item_id": "S001_I0001",
      "duplicate_item_ids": ["S002_I0003"]
    }}
  ]
}}

Items:
{items}
"""
