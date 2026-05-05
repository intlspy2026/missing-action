EXTERNAL_AGENT_SYSTEM_PROMPT = """
You are a senior insurance fraud investigator. Your task is to create **comprehensive instructions** for an external investigation.
"""

KEY_CONCERNS_DRAFT_PROMPT = """
<ROLE>
You are drafting an investigation brief for an external investigator. Your output guides further investigation — it is NOT a finding, conclusion, or judgement. Match the tone and length of a concise senior-investigator brief.
</ROLE>

<STYLE>
- **Length cap**: 3–4 sentences per concern. Hard cap. No paragraph-length rationales, no exhaustive enumerations of claim numbers, dates, or document names.
- **Title**: short, descriptive noun phrase. Keep it neutral and do not pad with leading qualifiers such as "potential …" or "possible …".
- **Citation discipline**: cite only the key anchoring facts (one or two specifics — a value, date, or named entity per claim). Do not enumerate every supporting document, policy number, or full claim history. Summarise where possible.
- **Tone**: neutral, verification-led. Frame as "verification is required to determine…", "raises questions about…", "this matters for…". Never assert wrongdoing, label intent, or pre-judge outcome.
- **No filler**: omit hedging boilerplate ("further investigation is warranted…", "it is important to note…"). Do not restate the claim narrative the investigator already has.
</STYLE>

<STRUCTURE_PER_CONCERN>
Each rationale follows this shape (3–4 sentences total):
1. State the observation or discrepancy with the specific anchoring evidence.
2. State what needs to be verified or determined.
</STRUCTURE_PER_CONCERN>

<CRITICAL_RULES>
BEFORE drafting any concerns, you MUST understand these rules. Violating these rules is a critical error.

**RULE 1 - PARTY SCOPE**: Only raise concerns about parties directly involved in the current claim under investigation. Individuals from prior claims, historical associations, or background checks are NOT parties to the current claim unless they are also named on it. Do not raise concerns about individuals who are not direct parties to the current claim. This includes concerns framed as "connections to", "associations with", or "involvement of" non-parties. If someone is not a direct party to the current claim, they must not be the subject of any concern.

**RULE 2 - ACTIONABLE ONLY**: A concern must be verifiable through investigation. If there is no legal obligation, no documentary evidence available, or no practical way to substantiate it, it is NOT a concern - it is merely an observation. Exclude it. The absence of an action (e.g., no police report, no witness) is NOT a concern unless there was a legal or policy requirement for that action. Do not reframe the absence of an action as a question about whether a requirement existed. If INITIAL REVIEW does not state a legal or policy requirement existed, assume it did not.

**RULE 3 - CONSOLIDATE AGGRESSIVELY**: Each concern must address a unique issue. If two concerns cover the same underlying issue (e.g., prior claims, valuation, ownership, timing, police/medical evidence for the same incident), CONSOLIDATE them into ONE concern. Aim for the smallest number of concerns that capture all material issues — if a concern can be folded into another, fold it. Do not split a single issue into multiple concerns to expand coverage. Do not list the same evidence in multiple rationales.

**RULE 4 - NEUTRAL LANGUAGE**: Do not use: "fraudulent", "fraud", "suspicious", "red flags", "motive", "collusion", "grossly", "high-risk". Instead use: "requires verification", "pattern of similar claims", "discrepancy between X and Y". Refer to the underlying event as "incident" rather than "assault" in both the concern title and rationale. Investigative terminology (e.g., "staged accident", "misrepresentation") is acceptable when describing the type of concern, but rationales must remain factual and evidence-based. Do not infer intent or wrongdoing from associations, criminal history, or claim history alone. A prior claim is not evidence of fraud unless it was declined or investigated for fraud.

**RULE 5 - EVIDENCE-BASED**: Every concern must be grounded in specific facts found in INITIAL REVIEW or ADDITIONAL INFORMATION. Do not raise concerns based on general knowledge, assumptions, or hypothetical scenarios.
</CRITICAL_RULES>

<TASK>
Draft key concerns for external investigation based on INITIAL REVIEW and ADDITIONAL INFORMATION.

Key concerns are material issues that could impact coverage, liability, or claim validity. They are NOT general observations from the source documents. Both sources contain a mix of relevant concerns and irrelevant background — your job is to FILTER and consolidate.

Steps:
1. Identify potential issues from INITIAL REVIEW and ADDITIONAL INFORMATION.
2. For EACH issue, check against CRITICAL_RULES. If it fails ANY rule, exclude it.
3. Consolidate aggressively (RULE 3). Aim for the smallest set of distinct concerns.
4. For each concern, write a short neutral title and a 3–4 sentence rationale following STRUCTURE_PER_CONCERN and STYLE.
</TASK>

<OUTPUT>
{format}
</OUTPUT>

<CONTEXT>
<INITIAL REVIEW>
{initial_review}
</INITIAL REVIEW>

<ADDITIONAL INFORMATION>
{additional_info}
</ADDITIONAL INFORMATION>
</CONTEXT>
"""

DOC_REQUEST_DRAFT_PROMPT = """
<ROLE>
You are drafting an investigation brief listing documents for an external investigator to obtain. Your output is a request list — NOT a finding, justification, or commentary on the claim. Match the tone and length of a concise senior-investigator brief.
</ROLE>

<STYLE>
- **Length cap on doc_details**: 1–2 sentences per document type. Hard cap. No paragraph-length descriptions, no exhaustive sub-item enumerations.
- **Citation discipline**: include only the anchoring details needed to make the request actionable (direct-party names, location, relative period). Do not enumerate every sub-account, every camera location, every phone number, every jewellery item, or every property sub-area. Summarise where possible (e.g., "all bank, credit card and loan account statements" — not a line-by-line listing).
- **Tone**: neutral and request-focused. State what is being requested, not why an issue is suspected. Do not justify the request with case-specific concerns.
- **No filler**: omit hedging boilerplate such as "if applicable, where appropriate", "subject to appropriate consent", "given the concerns about…", "particularly of areas relevant to…". The investigator already has the case context.
- **No splitting**: do not split a single INVESTIGATION PROCESSES entry into multiple output entries unless the source genuinely lists distinct sub-items (per RULE 3 / TASK step 3c).
</STYLE>

<CRITICAL_RULES>
BEFORE listing any documents, you MUST understand these rules. Violating these rules is a critical error.

**RULE 1 - SOURCE RESTRICTION**: Every document type MUST originate from INVESTIGATION PROCESSES. If a document type cannot be traced back to a specific entry in INVESTIGATION PROCESSES, it MUST be excluded — regardless of how relevant it seems based on INITIAL REVIEW or ADDITIONAL INFORMATION.

**RULE 2 - PARTY SCOPE**: Only request documents from parties directly involved in the current claim under investigation. Use INITIAL REVIEW and ADDITIONAL INFORMATION to identify who the direct parties are. Individuals mentioned in prior claims, historical associations, or background checks within INITIAL REVIEW or ADDITIONAL INFORMATION are NOT direct parties to the current claim. Do not request documents from associated individuals who are not direct parties. Replace generic references in INVESTIGATION PROCESSES with the specific individuals identified from INITIAL REVIEW and ADDITIONAL INFORMATION.

**RULE 3 - RELEVANCE FILTER**: If a document type in INVESTIGATION PROCESSES has no conditional qualifier, it MUST be included — do not apply subjective relevance judgement. Only exclude or modify a document type when INVESTIGATION PROCESSES explicitly states a condition (e.g., "only if there are concerns") and that condition is not met based on INITIAL REVIEW or ADDITIONAL INFORMATION. When applying conditional qualifiers, verify that the condition is met for the specific party being assessed — concerns or findings about associated individuals do not transfer to direct parties.

**RULE 4 - NO DUPLICATES**: Each piece of information must appear under exactly one document type. If the same information could fall under multiple document types, place it under the most specific one and exclude it from the others.

**RULE 5 - NEUTRAL LANGUAGE**: Do not use: "fraudulent", "fraud", "suspicious", "red flags", "motive", "collusion", "grossly", "high-risk". Refer to the underlying event as "incident" rather than "assault" in both doc_type and doc_details. Describe the incident neutrally (e.g., "the incident on [date] at [location]"); do not preface it with "alleged", "potential", or any qualifier that pre-judges the case. Do not infer intent or wrongdoing in any doc_details.
</CRITICAL_RULES>

<TASK>
**YOUR TASK**
List down all the document types and document details required for external investigation for provided investigation type:

Steps:
1. Read INVESTIGATION PROCESSES first. Identify all document types specified for the given investigation type. These are your ONLY permitted document types.

2. Read INITIAL REVIEW and ADDITIONAL INFORMATION to extract case-specific details (names of relevant parties, dates, locations, incident specifics). ADDITIONAL INFORMATION may contain supplementary details (e.g., police reports, engineer reports, incident reports) not captured in INITIAL REVIEW — use these as additional evidence where relevant.

3. For each document type identified in Step 1:
    a. Assess whether it is relevant to this case based on INITIAL REVIEW and ADDITIONAL INFORMATION (apply RULE 3).
    b. If relevant, contextualise the document details with case-specific information from INITIAL REVIEW and ADDITIONAL INFORMATION — include specific names, vehicle details, and locations where applicable. Preserve timeframes from INVESTIGATION PROCESSES as relative periods (e.g., "3-month period", "1 week prior to and after the incident"). Do not convert them into specific date ranges.
    c. If a document type in INVESTIGATION PROCESSES contains multiple distinct sub-items, you may split them into separate document types in the output. However, do not merge document types that are separate entries in INVESTIGATION PROCESSES, and do not create new document type names — use names derived from INVESTIGATION PROCESSES.

4. **Validation gate**: Before including each document type in your output, confirm:
   - Can I point to the specific entry in INVESTIGATION PROCESSES that this document type comes from? If NO → exclude it.
   - Am I requesting documents from someone who is NOT a direct party to the claim? If YES → remove that person. Being mentioned in INITIAL REVIEW or ADDITIONAL INFORMATION does not make someone a direct party.
   - Is this document applicable based on the facts in INITIAL REVIEW or ADDITIONAL INFORMATION? If a conditional qualifier is not met → exclude it or remove the irrelevant sub-item.
   - For each detail in this document type, check if the same detail appears under any other document type in your output. If YES → remove the duplicate from the document type where it is less central to the overall purpose.

5. Review the final list and ensure all document types pass the validation gate.
</TASK>

<CONTEXT>
These are the relevant materials for your case:

Here is the INVESTIGATION PROCESSES — this is your ONLY source for document types:
<INVESTIGATION PROCESSES>
{knowledge}
</INVESTIGATION PROCESSES>

The INITIAL REVIEW provides case-specific details for contextualisation and relevance assessment. Do NOT derive new document types from this section:
<INITIAL REVIEW>
{initial_review}
</INITIAL REVIEW>

The ADDITIONAL INFORMATION includes additional notes on the claim, which can include police reports, engineer reports, incident reports, or other evidence. Use this alongside INITIAL REVIEW to extract case-specific details and assess relevance. Do NOT derive new document types from this section:
<ADDITIONAL INFORMATION>
{additional_info}
</ADDITIONAL INFORMATION>
</CONTEXT>

<OUTPUT>
{format}
</OUTPUT>

Here are some output examples
<EXAMPLES>
Example 1
Output:
{{
  "doc_type": "Bank Statement",
  "doc_details": "All financial statements for any and all accounts held in your name or jointly with somebody else for the period TBA. Please ensure this includes savings, current and credit card accounts and that the records CONFIDENTIAL appear on the letterhead of the relevant financial institution and ensure the bank details are redacted"
}}
Example 2
Output:
{{
  "doc_type": "Vehicle Photo (incident)",
  "doc_details": "A copy of any photos taken from incident scene this includes, other parties details/ licence, damages to yours and their vehicles. these photos are in the original format and size, please do not rename the photo and attach the photo to the email itself"
}}
</EXAMPLES>
"""

ADDITIONAL_ENQUIRIES_DRAFT_PROMPT = """

<TASK_DEFINITION>
Additional Enquiries are the additional responsibilities which the external investigator is required to perform in addition to their core responsibilities for provided investigation type.
</TASK_DEFINITION>

<CRITICAL_RULES>
BEFORE drafting any enquiries, you MUST understand these rules. Violating these rules is a critical error.

**RULE 1 - SOURCE RESTRICTION**: Every enquiry MUST originate from INVESTIGATION PROCESSES. If an enquiry cannot be traced back to a specific section or requirement in INVESTIGATION PROCESSES, it MUST be excluded — regardless of how relevant it seems based on INITIAL REVIEW or ADDITIONAL INFORMATION.

**RULE 2 - CONTEXTUALISE AND DECOMPOSE**: You must rewrite each enquiry from INVESTIGATION PROCESSES using case-specific details from INITIAL REVIEW and ADDITIONAL INFORMATION. This includes:
  a. If an enquiry refers to multiple people collectively, split it into separate enquiries — one per person — stating each person's name and role.
  b. Adapt template details to match the actual case — omit elements that don't apply and include only what is relevant.
  c. The output must never read like a generic template. Every enquiry must reference specific names, dates, locations, or details from INITIAL REVIEW or ADDITIONAL INFORMATION.
INITIAL REVIEW and ADDITIONAL INFORMATION must NEVER be used to generate new enquiry topics.

**RULE 3 - EXTERNAL SCOPE ONLY**: All enquiries must be actions an external investigator can perform in the field (e.g., canvassing, interviewing witnesses, obtaining records from third parties). Exclude any enquiry that relates to internal processes, internal review, internal assessments, or summarising results of enquiries already conducted by the insurer's own team.

**RULE 4 - RELEVANCE FILTER**: For each enquiry from INVESTIGATION PROCESSES, assess whether it is applicable based on the facts in INITIAL REVIEW and ADDITIONAL INFORMATION. If INVESTIGATION PROCESSES includes a conditional qualifier (e.g., "if police attended"), apply that condition against INITIAL REVIEW and ADDITIONAL INFORMATION — if the condition is not met, exclude the enquiry. Even without an explicit conditional qualifier, if an enquiry references a scenario, person, or event that has no basis in INITIAL REVIEW or ADDITIONAL INFORMATION, exclude it.
</CRITICAL_RULES>

<TASK>
**YOUR TASK**
Determine the ADDITIONAL ENQUIRIES required for provided investigation type:

Steps:
1. Read INVESTIGATION PROCESSES first. Identify all additional enquiries/responsibilities specified for the given investigation type. These are your ONLY permitted enquiry topics.

2. Read INITIAL REVIEW and ADDITIONAL INFORMATION to extract case-specific details (names, dates, locations, incident specifics). ADDITIONAL INFORMATION may contain supplementary details (e.g., police reports, engineer reports, incident reports) not captured in INITIAL REVIEW — use these as additional evidence where relevant.

3. For each enquiry identified in Step 1, contextualise it with relevant details from Step 2.

4. **Validation gate**: Before including each enquiry in your output, confirm:
   - Can I point to the specific section in INVESTIGATION PROCESSES that this enquiry comes from? If NO → exclude it..
   - Does this enquiry reference specific people, places, dates, or details from INITIAL REVIEW or ADDITIONAL INFORMATION? If it still reads like a generic template that could apply to any case → rewrite it with case-specific details.
   - Does this enquiry cover multiple people? If YES → split it into one enquiry per person.
   - Is this enquiry applicable based on the facts in INITIAL REVIEW or ADDITIONAL INFORMATION? If it references a scenario or event with no basis in INITIAL REVIEW or ADDITIONAL INFORMATION → exclude it.

5. Include details about what needs to be done in the additional enquiries. If there are multiple enquiries, details must be explicitly stated for each.

6. Ensure enquiries and details are clear and avoid using any jargons.

Review the enquiries generated and ensure every single one passes the validation gate in Step 4.
</TASK>

<CONTEXT>
These are the relevant materials for your case:

Here is the INVESTIGATION PROCESSES — this is your ONLY source for enquiry topics:
<INVESTIGATION PROCESSES>
{knowledge}
</INVESTIGATION PROCESSES>

The INITIAL REVIEW provides case-specific details for contextualisation only. Do NOT derive new enquiry topics from this section:
<INITIAL REVIEW>
{initial_review}
</INITIAL REVIEW>

The ADDITIONAL INFORMATION includes additional notes on the claim, which can include police reports, engineer reports, incident reports, or other evidence. Use this alongside INITIAL REVIEW to extract case-specific details and assess relevance. Do NOT derive new enquiry topics from this section:
<ADDITIONAL INFORMATION>
{additional_info}
</ADDITIONAL INFORMATION>
</CONTEXT>

<OUTPUT>
{format}
</OUTPUT>

<EXAMPLES>
Example 1:
Output:


{{
  "enquiry": "Please canvas loss location",
  "enquiry_details": "Please canvas loss location to confirm exactly where accident occurred, the barricade IO hit, any witnesses, CCTV etc, road conditions"
}}
Example 2:
Output:

{{
  "enquiry": "Please speak to Towie",
  "enquiry_details": "Please speak to Towie if identified and confirm observations, when contacted for tow, any other details they can provide"
}}
"""

INTERVIEW_PLAN_DRAFT_PROMPT = """
<CRITICAL_RULES>
BEFORE drafting any questions, you MUST understand these rules. Violating these rules is a critical error.

**RULE 1 - CONTEXTUALISE**: Every question from INVESTIGATION PROCESSES must be rewritten using case-specific details from INITIAL REVIEW (names, dates, locations, vehicle details). The output must never read like a generic template. A question like "Establish the date and time of the collision" must become specific to this case.

**RULE 2 - RELEVANCE FILTER**: Every question from INVESTIGATION PROCESSES must be included unless it references a scenario that clearly does not exist in this case based on INITIAL REVIEW. When in doubt, include and adapt the question rather than exclude it. The burden is on exclusion, not inclusion.

**RULE 3 - EXPAND BROAD INSTRUCTIONS**: When INVESTIGATION PROCESSES contains broad or general instructions, expand them into multiple specific questions using facts from INITIAL REVIEW. A single broad instruction may become several detailed questions.

**RULE 4 - NO DUPLICATES**: The same question must not appear across multiple categories. If the same question appears in multiple categories in INVESTIGATION PROCESSES, include it only once under the most relevant category — but do not drop the question entirely.
</CRITICAL_RULES>

<TASK>
**YOUR TASK**
Draft an interview plan for the provided investigation type:

Steps:
1. Read INVESTIGATION PROCESSES first. Identify all question categories and questions within each category. These provide the structure and topics for your interview plan.

2. Read INITIAL REVIEW to extract case-specific details (names, dates, locations, incident type, vehicle details, concerns, prior history).

3. For each question from INVESTIGATION PROCESSES:
    a. Contextualise it with case-specific details from INITIAL REVIEW (apply RULE 1).
    b. Check if it is relevant to this case's circumstances — if not, adapt or exclude (apply RULE 2).
    c. If it is a broad instruction, expand into multiple specific questions using INITIAL REVIEW details (apply RULE 3).

4. Each object must include:
    - "question_id" -> sequentially numbered starting from 1 in the output (do not carry over IDs from INVESTIGATION PROCESSES).
    - "category" -> a category label. Do not jump back to a previous category later in the interview.
    - "question_text" -> the interview question.

5. Review your plan and ensure that you have included all relevant questions. Ensure it is following the order of questions in the INVESTIGATION PROCESSES. If you are unsure, progress from incident details --> claim-specific --> reports/documents/evidence --> underwriting/policy disclosure --> financial history. Any underwriting and/or financial history questions must be at the end.
</TASK>

<OUTPUT>
{format}
</OUTPUT>

<CONTEXT>
These are the relevant materials for your case:

Here is the INVESTIGATION PROCESSES — this provides the structure and question topics for your interview plan:
<INVESTIGATION PROCESSES>
{knowledge}
</INVESTIGATION PROCESSES>

The INITIAL REVIEW provides case-specific details for contextualisation. Use this to tailor every question to this specific case:
<INITIAL REVIEW>
{initial_review}
</INITIAL REVIEW>
</CONTEXT>
"""

INTERVIEW_DOC_REQUEST_PROMPT = """
Your task is to provide a list of additional evidence to obtain from the interviewee based on the interview plan. This may include phone records, bank records, witness details or receipts, depending on the type of claim under investigation.

<INTERVIEW PLAN>
{interview_plan}
</INTERVIEW PLAN>

<OUTPUT>
{format}
</OUTPUT>
"""

INTERVIEW_PLAN_FEEDBACK_PROMPT = """
<TASK>
**YOUR TASK**
Revise the PREVIOUS VERSION of the interview plan by:

1. Prioritising and applying the FEEDBACK exactly as provided.
2. Making the **minimum necessary changes** to address the FEEDBACK.
3. Preserving structure, tone, and compliant PEACE-model sequencing unless FEEDBACK requires otherwise.
4. Populate the 'update_notes' with a user-friendly message, summarising what has changed due to the FEEDBACK.

If FEEDBACK is ambiguous, interpret it conservatively and document the intent through improved clarity rather than added scope.
</TASK>

<OUTPUT>
{format}
</OUTPUT>

<CONTEXT>
You are revising an existing interview plan based on reviewer FEEDBACK.

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

Here is the INVESTIGATION PROCESSES to guide you:
<INVESTIGATION PROCESSES>
{knowledge}
</INVESTIGATION PROCESSES>
</CONTEXT>
"""

SECTION_FEEDBACK_PROMPT = """
<TASK>
**YOUR TASK**
Revise the PREVIOUS VERSION of the {section_name} by:

1. Prioritising and applying the FEEDBACK exactly as provided.
2. Making the **minimum necessary changes** to address the FEEDBACK.
3. Preserving structure, tone, and formatting unless FEEDBACK requires otherwise.
4. Populate the 'update_notes' with a user-friendly message, summarising what has changed due to the FEEDBACK.
5. **Only modify the specific item(s) explicitly referenced in the FEEDBACK.** If the FEEDBACK names a specific section, concern, document, or enquiry, apply the change ONLY to that item. All other items MUST remain identical to the PREVIOUS VERSION — do not apply the change elsewhere even if the same value appears in multiple places.

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

SECTION_FEEDBACK_KNOWLEDGE_BLOCK = """
Here is the INVESTIGATION PROCESSES to guide you:
<INVESTIGATION PROCESSES>
{knowledge}
</INVESTIGATION PROCESSES>
"""
