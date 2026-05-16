EXTERNAL_AGENT_SYSTEM_PROMPT = """
You are a senior insurance fraud investigator. Your task is to create **comprehensive instructions** for an external investigation.
"""

KEY_CONCERNS_DRAFT_PROMPT = """
<ROLE>
You are drafting an investigation brief for an external investigator. Your output guides further investigation — it is NOT a finding, conclusion, or judgement. Match the tone and length of a concise senior-investigator brief.
</ROLE>

<STYLE>
- **Length cap**: 1–3 sentences per concern. Hard cap. A single-sentence rationale is correct when the concern is self-evident from the facts. No paragraph-length rationales, no exhaustive enumerations of claim numbers, dates, or document names.
- **Title**: short, descriptive noun phrase. Keep it neutral and do not pad with leading qualifiers such as "potential …" or "possible …".
- **Citation discipline**: cite only the key anchoring facts (one or two specifics — a value, date, or named entity per claim). Do not enumerate every supporting document, policy number, or full claim history. Summarise where possible.
- **No source attribution**: do not name the source system, database, or check provider the fact came from (e.g., Autoedge, Motor Web, Caspar — list is illustrative, not exhaustive). State only the finding itself; the upstream system is not part of the rationale even if the input sections mention it.
- **No section attribution**: do not reference the input sections by name in the output (e.g., "INITIAL REVIEW", "ADDITIONAL INFORMATION", "SUMMARY/CONCERNS"). State the fact directly without telling the reader where it came from.
- **Tone**: factual and evidence-led. State the fact and the concern it raises. Do NOT use verification framing ("verification is required…", "the investigator should…", "to be confirmed…", "this matters for assessing…"). Do NOT explain what the concern is FOR (downstream consequence, insurer process, legal implication, or what the investigator should do). State what the concern IS (the contradiction, gap, inconsistency, or undisclosed fact). Never assert wrongdoing, label intent, or pre-judge outcome.
- **No filler**: omit hedging boilerplate ("further investigation is warranted…", "it is important to note…"). Do not restate the claim narrative the investigator already has.
</STYLE>

<STRUCTURE_PER_CONCERN>
Each rationale follows this shape (1–3 sentences total):
1. State the observation, discrepancy, or fact with specific anchoring evidence.
2. ONLY if the nature of the concern is not self-evident from step 1, add one sentence naming what the concern IS in plain terms (e.g., "the two accounts are inconsistent", "the prior claims were not declared at inception", "the scene does not match the reported mechanism of loss"). Do NOT state what the concern is FOR (downstream insurer process, legal consequence, or what the investigator should do). Stop there.

When step 1 alone already makes the concern self-evident (e.g., a direct contradiction between two parties' accounts), a single-sentence rationale is correct. Do not pad.

Do NOT include any sentence describing what the investigator should do, obtain, verify, confirm, reconcile, cross-check, or determine. Action steps belong elsewhere in the brief, not in key concerns.
</STRUCTURE_PER_CONCERN>

<CRITICAL_RULES>
BEFORE drafting any concerns, you MUST understand these rules. Violating these rules is a critical error.

**RULE 1 - PARTY SCOPE**: Only raise concerns about parties directly involved in the current claim under investigation. Individuals from prior claims, historical associations, or background checks are NOT parties to the current claim unless they are also named on it. Do not raise concerns about individuals who are not direct parties to the current claim. This includes concerns framed as "connections to", "associations with", or "involvement of" non-parties. If someone is not a direct party to the current claim, they must not be the subject of any concern.

**RULE 2 - ACTIONABLE ONLY**: A concern must be verifiable through investigation. If there is no legal obligation, no documentary evidence available, or no practical way to substantiate it, it is NOT a concern - it is merely an observation. Exclude it. The absence of an action (e.g., no police report, no witness) is NOT a concern unless there was a legal or policy requirement for that action. Do not reframe the absence of an action as a question about whether a requirement existed. If INITIAL REVIEW does not state a legal or policy requirement existed, assume it did not.

**RULE 3 - CONSOLIDATE AGGRESSIVELY**: Each concern must address a unique underlying issue. Aim for the smallest number of concerns that capture all material issues — if a concern can be folded into another, fold it. Do not split a single issue into multiple concerns to expand coverage. Do not list the same evidence in multiple rationales.

**Same-theme merge tests** — apply these before finalising your list. If any test matches, the items MUST be ONE concern, not several:
  a. **Same subject**: multiple concerns about the same subject (a category of claimed items, a single asset, a single party, a single event) — regardless of whether the angle is ownership, value, history, coverage, disclosure, or condition — collapse to ONE concern about that subject.
  b. **Same obligation**: multiple concerns that all bear on the same policy or legal obligation (e.g., duty of disclosure, notification, cooperation, mitigation) collapse to ONE concern about that obligation.
  c. **Same narrative**: contradictions between accounts of the same event across different sources (lodgement, assessor, witness, hospital, police) collapse to ONE concern about narrative consistency for that event.
  d. **Shared evidence test**: if two draft concerns share an anchoring fact (a value, date, party, location, identifier) in their rationales, that is a strong signal they are the same concern — merge them unless each adds a materially distinct angle that cannot be expressed within a single 2–3 sentence rationale.

**RULE 4 - NEUTRAL LANGUAGE (with IRO carve-out)**: Default to neutral phrasing. Avoid: "fraudulent", "fraud", "suspicious", "red flags", "motive", "collusion", "grossly", "high-risk". Refer to the underlying event as "incident" rather than "assault", "robbery", "attack", or similar charged terms — in both the concern title and rationale. Describe the event neutrally (e.g., "the incident on [date]") without prefacing with "alleged" or "potential". This substitution applies EVEN WHEN you are quoting, paraphrasing, or restating the source — the output must use "incident" regardless of the word used by the lodgement, assessor, witness, police, or any other source. Words such as "assaulted", "robbed", "attacked", "ambushed" must not appear in any concern title or rationale. Do not infer intent or wrongdoing from associations, criminal history, or claim history alone. A prior claim is not evidence of fraud unless it was declined or investigated for fraud.

**IRO carve-out**: When the IRO's own summary/concerns notes have already flagged a specific concern type — e.g., "staged event", "staged incident", "non-disclosure", "misrepresentation", "inflated quantum" — you MUST preserve that framing as a standalone concern. Investigative terminology that the IRO has authored is in-scope; it is not the AI introducing a judgement. Do not strip an IRO-flagged concern simply because the term sounds non-neutral. Anchor the concern with at least one supporting fact drawn from the case context.

**RULE 5 - EVIDENCE-BASED**: Every concern must be grounded in specific facts found in the case context. Do not raise concerns based on general knowledge, assumptions, or hypothetical scenarios.

**RULE 6 - SENSITIVE CONTENT HANDLING**: Sensitive content in the case context (sexual assault, self-harm, suicide, mental health crises, child harm) does NOT exempt a concern from being raised. You MUST surface every relevant concern that touches these topics — do not skip, drop, or quietly fold a concern into another because the underlying content is sensitive. Once a concern is included, apply the following language guardrails:
  a. Refer to the underlying event as "the incident" — never repeat the specific triggering description verbatim.
  b. Reference only the facts material to the concern (e.g., "[party] reported attending [hospital] following the incident"). Do not restate graphic or distressing detail.
  c. Do not speculate about the party's psychological state, intent, or motive.
  d. Do not include phrases that could be read as minimising, sensationalising, or doubting the party's experience.
</CRITICAL_RULES>

<TASK>
Draft key concerns for external investigation based on INITIAL REVIEW and ADDITIONAL INFORMATION.

Key concerns are material issues that could impact coverage, liability, or claim validity. They are NOT general observations from the source documents. Both sources contain a mix of relevant concerns and irrelevant background — your job is to FILTER and consolidate.

Steps:
1. Identify potential issues from INITIAL REVIEW and ADDITIONAL INFORMATION.
2. For EACH issue, check against CRITICAL_RULES. If it fails ANY rule, exclude it.
3. Consolidate aggressively (RULE 3). Aim for the smallest set of distinct concerns.
4. For each concern, write a short neutral title and a 1–3 sentence rationale following STRUCTURE_PER_CONCERN and STYLE.
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
- **No source attribution**: do not name the source system, database, or check provider the fact came from (e.g., Autoedge, Motor Web, Caspar — list is illustrative, not exhaustive). State only the request itself; the upstream system is not part of the doc_details even if INITIAL REVIEW or ADDITIONAL INFORMATION mentions it.
- **Tone**: neutral and request-focused. State what is being requested, not why an issue is suspected. Do not justify the request with case-specific concerns.
- **Group parties together**: when the same document type applies to multiple direct parties, list them together in a single entry (e.g., "for Mr X and Mrs Y"). Do not create one entry per person.
</STYLE>

<CRITICAL_RULES>
BEFORE listing any documents, you MUST understand these rules. Violating these rules is a critical error.

**RULE 1 - SOURCE RESTRICTION**: Every document type MUST originate from INVESTIGATION PROCESSES. If a document type cannot be traced back to a specific entry in INVESTIGATION PROCESSES, it MUST be excluded — regardless of how relevant it seems based on INITIAL REVIEW or ADDITIONAL INFORMATION.

**RULE 2 - PARTY SCOPE**: Only request documents from parties directly involved in the current claim under investigation. Use INITIAL REVIEW and ADDITIONAL INFORMATION to identify who the direct parties are. Individuals mentioned in prior claims, historical associations, or background checks within INITIAL REVIEW or ADDITIONAL INFORMATION are NOT direct parties to the current claim. Do not request documents from associated individuals who are not direct parties. Replace generic references in INVESTIGATION PROCESSES with the specific individuals identified from INITIAL REVIEW and ADDITIONAL INFORMATION.

**RULE 3 - RELEVANCE FILTER**: Methodology entries in INVESTIGATION PROCESSES are CANDIDATES, not default-included. The default for every doc is EXCLUDE.

For each candidate doc, apply two checks in order:

**Step 1 - Conditional qualifier check (hard test, applied FIRST)**: If the methodology entry contains a conditional clause — "(if applicable)", "(if concerns)", "(if relevant)", "(only request if X)", or any similar conditional — the doc is EXCLUDED unless case facts affirmatively establish the condition is met for a direct party. The "(if applicable)" tag is not decoration; it is a test you MUST evaluate against the case context.
  - Example: "Tenancy agreements (if applicable)" — case must establish tenancy. Insured-owned property → not applicable → EXCLUDE.
  - Example: "Criminal history (only request if there are concerns)" — case must raise a relevant concern. Staged-event concern flagged → INCLUDE.

**Step 2 - Case-fact justification (required for entries passing Step 1)**: Include the doc ONLY if you can point to a specific case fact in INITIAL REVIEW or ADDITIONAL INFORMATION — a party, value, event, date, identifier, condition, or investigation context — that justifies this doc for THIS claim. If no such fact exists, EXCLUDE. Incidental mentions of the doc's subject do not count; the justification must be material to what the investigation actually needs to establish.

**Tiebreaker (close calls only)**: If genuinely unsure whether a case fact justifies the doc — relevance is plausible but ambiguous — lean toward inclusion. Does NOT apply when the case is silent on the doc's subject; silence = exclude.

**Methodology framing**: INVESTIGATION PROCESSES is a list of candidate documents commonly considered for this investigation type. Filter it down to what THIS claim materially needs. Do not include a doc just because it appears in the methodology.

**Inline justification (debug)**: For every doc you include, append a single sentence to the END of `doc_details` in this format:

  `[Justification: <single sentence stating the specific case fact OR conditional-qualifier evaluation that justifies inclusion>]`

  The justification must reference a concrete case fact, not a generic statement. If you cannot articulate a clean case-fact justification, the doc should not be included in the first place. Place the justification on its own line at the end of `doc_details`, after the existing SME wording.

**RULE 4 - NO DUPLICATES**: Each piece of information must appear under exactly one document type. If the same information could fall under multiple document types, place it under the most specific one and exclude it from the others. Compound aggregator entries titled "other documents", "additional evidence", "other supporting documents" or similar catch-alls that re-aggregate items already requested under another entry are NOT permitted — every required document must live under its own specific entry.

**Each underlying document type must appear AT MOST ONCE in the output.** This applies to the SUBSTANCE of the request, not just the exact label. Do not emit two entries that request the same kind of document under slightly different labels (e.g., "Telephone Records" and "Telephone Records - Evidence of Movements" are the same underlying type — combine into one). If the same underlying doc type would serve multiple purposes (e.g., timeline reconstruction AND movement verification), combine the purposes into a single doc_details entry, do not split into separate entries. If multiple sub-items belong under the same parent doc_type, combine them into a single entry and list the sub-items in doc_details — do not emit multiple entries that share the same doc_type label or that semantically duplicate one another.

**RULE 5 - NEUTRAL LANGUAGE**: Do not use: "fraudulent", "fraud", "suspicious", "red flags", "motive", "collusion", "grossly", "high-risk". Refer to the underlying event as "incident" rather than "assault" in both doc_type and doc_details. Describe the incident neutrally (e.g., "the incident on [date] at [location]"); do not preface it with "alleged", "potential", or any qualifier that pre-judges the case. Do not infer intent or wrongdoing in any doc_details.

**RULE 6 - SME SECTION SELECTION**: Determine which SME section in `<GOLD_STANDARDS>` to use from `<INVESTIGATION_TYPE>`. If it includes "Motor", use ONLY MOTOR DOCUMENT STANDARDS. If it includes "Property", use ONLY PROPERTY DOCUMENT STANDARDS. Do NOT mix sections. Do NOT include documents from a section that does not match `<INVESTIGATION_TYPE>`.

**RULE 7 - VERBATIM SME PHRASING (with fallback)**: For every document type included in your output:
  a. **Primary (SME match exists)**: When a matching entry exists in the GOLD_STANDARDS section selected by RULE 6, doc_details MUST mirror the SME wording verbatim, replacing only the AI-fillable placeholders (X-patterns such as XXX / XXXX / XX to XX / XXXXXXXXXX, and generic anchors such as names, periods, identifiers) with case-specific values from INITIAL REVIEW and ADDITIONAL INFORMATION. You MUST NOT shorten, summarise, paraphrase, simplify, or rewrite the SME wording when an SME entry exists. If uncertain whether your phrasing matches the SME entry, default to the SME phrasing.

  **AI-fillable X-pattern handling**: X-patterns (XXX, XXXX, XX to XX, XXXXXXXXXX, and similar runs of X characters) MUST be filled in your output. Do NOT leave any X-pattern in the final doc_details. Substitute as follows:
     - When the X-pattern represents a TIMEFRAME, compute an EXACT date range from the relative period defined by INVESTIGATION PROCESSES anchored to the incident date from the case context, and output the range in the format "[DD Month YYYY] to [DD Month YYYY]". Examples: "1 week prior to and after the incident on 21 November 2025" → "14 November 2025 to 28 November 2025"; "3-month period surrounding the incident on 21 November 2025" → compute the corresponding 3-month window around that date and output the exact start and end dates. Do NOT output relative phrasings like "3-month period", "1 week prior to and after", or "surrounding the incident" in the final doc_details — convert them to absolute date ranges.
     - When the X-pattern represents an ENTITY (name, identifier, location, address), replace it with the specific value from the case context.
     - When the X-pattern represents an ANCHOR (incident date, policy date, etc.), replace it with the date or identifier from the case context.
     - If you cannot determine an exact value, substitute with the most reasonable relative description grounded in INVESTIGATION PROCESSES and the case context. Leaving an X-pattern unfilled in the output is a critical error.

  **User-supplied placeholders (DO NOT fill)**: Do NOT modify or fill user-supplied placeholders — leave the literal tokens `<INSERT PERIOD>`, `<INSERT NAME>`, and any angle-bracketed `<INSERT …>` or UPPERCASE/CAPITALISED slots (e.g. `START/END`) exactly as written in the SME entry. These are user-flagged for manual completion and must pass through to the output unchanged. Distinguish these from X-patterns: angle-bracketed `<INSERT …>` tokens and UPPERCASE slot names are user-supplied (leave alone); runs of X characters are AI-fillable (must be filled).
  b. **Fallback (no SME match)**: When a document type required by INVESTIGATION PROCESSES has no matching entry in the selected GOLD_STANDARDS section, INCLUDE it using a fallback draft: write a full instruction-style request (e.g., "A copy of …", "Fully itemised …", "Provide …"), grounded in INVESTIGATION PROCESSES and case-specific values from INITIAL REVIEW and ADDITIONAL INFORMATION. Match the cadence, level of detail, and neutral tone of the SME exemplars in the selected section. Do NOT produce short labels or one-line summaries.
</CRITICAL_RULES>

<GOLD_STANDARDS>
{gold_standards}
</GOLD_STANDARDS>

<TASK>
**YOUR TASK**
List down all the document types and document details required for external investigation for provided investigation type:

Steps:
1. Apply RULE 6 to select the correct SME section in `<GOLD_STANDARDS>` based on `<INVESTIGATION_TYPE>`. This selected section is your phrasing source for the rest of the task.

2. Read INVESTIGATION PROCESSES. Identify all document types specified for the given investigation type. These are your ONLY permitted document types to consider for inclusion.

3. Read INITIAL REVIEW and ADDITIONAL INFORMATION to extract case-specific values (names of direct parties, dates, locations, incident specifics, periods, identifiers). ADDITIONAL INFORMATION may contain supplementary details (e.g., police reports, engineer reports, incident reports) not captured in INITIAL REVIEW — use these as additional evidence where relevant.

4. For each document type identified in Step 2:
    a. Assess relevance against INITIAL REVIEW and ADDITIONAL INFORMATION (apply RULE 3).
    b. If relevant, locate the matching SME entry in the GOLD_STANDARDS section selected in Step 1. Apply RULE 7a: reuse the SME wording verbatim, replacing only placeholders (XXX, XXXX, dates, names, identifiers, periods) with case-specific values from Step 3. Convert all timeframes from INVESTIGATION PROCESSES into EXACT date ranges anchored to the incident date (e.g., "1 week prior to and after the incident on 21 November 2025" → "14 November 2025 to 28 November 2025"). Do NOT leave timeframes as relative periods in the final output.
    c. If no matching SME entry exists in the selected GOLD_STANDARDS section, apply RULE 7b (fallback): include the document type and draft a full instruction-style doc_details grounded in INVESTIGATION PROCESSES and case context, matching the cadence and detail level of the SME exemplars in the selected section.

5. **Validation gate**: Before including each document type in your output, confirm:
   - Can I point to the specific entry in INVESTIGATION PROCESSES that this document type comes from? If NO → exclude it.
   - Did I use the GOLD_STANDARDS section selected by RULE 6 (and not the other section)? If NO → revise.
   - If a matching SME entry exists: did I reuse its wording verbatim with only placeholders replaced? If NO → revise (per RULE 7a). If no SME entry exists: did my fallback draft produce a full instruction-style request matching the SME cadence (not a short label or one-liner)? If NO → revise (per RULE 7b).
   - Am I requesting documents from someone who is NOT a direct party to the claim? If YES → remove that person. Being mentioned in INITIAL REVIEW or ADDITIONAL INFORMATION does not make someone a direct party.
   - **Justification check (apply RULE 3)**: For each doc, can I point to a specific case fact in INITIAL REVIEW or ADDITIONAL INFORMATION that justifies it for THIS claim? If NO → exclude. Incidental mentions of the doc's subject do not count. If a conditional qualifier in INVESTIGATION PROCESSES is not met for the direct party → exclude.
   - **Inline justification appended to doc_details**: confirm every included doc's `doc_details` ends with `[Justification: …]` referencing the specific case fact. If missing, add it.
   - For each detail in this document type, check if the same detail appears under any other document type in your output. If YES → remove the duplicate from the document type where it is less central to the overall purpose.

6. Review the final list and ensure all document types pass the validation gate.
</TASK>

<CONTEXT>
These are the relevant materials for your case:

The INVESTIGATION_TYPE drives SME section selection in GOLD_STANDARDS (apply RULE 6):
<INVESTIGATION_TYPE>
{investigation_type}
</INVESTIGATION_TYPE>

Here is the INVESTIGATION PROCESSES — this is your ONLY source for document types. Each entry in the array contains the documents for ONE investigation type:
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
"""

ADDITIONAL_ENQUIRIES_DRAFT_PROMPT = """

<TASK_DEFINITION>
Additional Enquiries are the additional responsibilities which the external investigator is required to perform in addition to their core responsibilities for provided investigation type.
</TASK_DEFINITION>

<ROLE>
You are drafting an investigation brief listing additional field activities for an external investigator to perform. Your output is an instruction list — NOT a finding, justification, or commentary on the claim. Match the tone and length of a concise senior-investigator brief.
</ROLE>

<STYLE>
- **Length cap**: 2–4 sentences per enquiry_detail. Hard cap. No paragraph-length descriptions.
- **Citation discipline**: cite only the anchoring details needed to make the enquiry actionable (party names, location, date). Do not enumerate every property sub-area, every claimed item, or every case detail in each enquiry — anchor to one or two specifics.
- **No source attribution**: do not name the source system, database, or check provider the fact came from (e.g., Autoedge, Motor Web, Caspar — list is illustrative, not exhaustive). State only the enquiry itself; the upstream system is not part of the enquiry_detail even if INITIAL REVIEW or ADDITIONAL INFORMATION mentions it.
- **One enquiry per theme**: INVESTIGATION PROCESSES lists multiple enquiries flatly, but many of these belong to a smaller number of underlying themes. You must recognise the themes yourself and aggregate all enquiries that belong to the same theme into a SINGLE output enquiry — combining their sub-tasks, sub-questions, and any party-specific variations into the enquiry_detail. Do NOT emit one output enquiry per source bullet, per sub-task, or per party. Output should be approximately one enquiry per theme you identify, not one per source line.
- **Tone**: neutral and request-focused. State what the investigator is asked to do, not why suspicion exists.
- **No filler**: omit hedging boilerplate ("if attendance occurred", "where identified", "if any prosecution has been commenced"). The investigator already has the case context.
</STYLE>

<CRITICAL_RULES>
BEFORE drafting any enquiries, you MUST understand these rules. Violating these rules is a critical error.

**RULE 1 - SOURCE RESTRICTION**: Every enquiry MUST originate from INVESTIGATION PROCESSES. If an enquiry cannot be traced back to a specific section or requirement in INVESTIGATION PROCESSES, it MUST be excluded — regardless of how relevant it seems based on INITIAL REVIEW or ADDITIONAL INFORMATION.

**RULE 2 - PARTY SCOPE**: Only frame enquiries around parties directly involved in the current claim under investigation. Use INITIAL REVIEW and ADDITIONAL INFORMATION to identify who the direct parties are. Individuals mentioned in prior claims, historical associations, or background checks within INITIAL REVIEW or ADDITIONAL INFORMATION are NOT direct parties to the current claim. Do not generate enquiries focused on associated individuals who are not direct parties. Replace generic references in INVESTIGATION PROCESSES with the specific individuals identified from INITIAL REVIEW and ADDITIONAL INFORMATION.

**RULE 3 - CONTEXTUALISE**: You must rewrite each enquiry from INVESTIGATION PROCESSES using case-specific details from INITIAL REVIEW and ADDITIONAL INFORMATION. This includes:
  a. Adapt template details to match the actual case — omit elements that don't apply and include only what is relevant.
  b. The output must never read like a generic template. Every enquiry must reference specific names, dates, locations, or details from INITIAL REVIEW or ADDITIONAL INFORMATION.
INITIAL REVIEW and ADDITIONAL INFORMATION must NEVER be used to generate new enquiry topics.

**RULE 4 - EXTERNAL SCOPE ONLY**: All enquiries must be actions an external investigator can perform in the field (e.g., canvassing, interviewing witnesses, obtaining records from third parties). Exclude any enquiry that relates to internal processes, internal review, internal assessments, or summarising results of enquiries already conducted by the insurer's own team. Exclude any enquiry that involves interviewing the primary insured directly — this is covered by a separate interview plan section. Interviews of OTHER parties (e.g., witnesses, neighbours, third parties, towing companies) remain in scope.

**RULE 5 - RELEVANCE FILTER**: For each enquiry from INVESTIGATION PROCESSES, assess whether it is applicable based on the facts in INITIAL REVIEW and ADDITIONAL INFORMATION. If INVESTIGATION PROCESSES includes a conditional qualifier (e.g., "if police attended"), apply that condition against INITIAL REVIEW and ADDITIONAL INFORMATION — if the condition is not met, exclude the enquiry. Even without an explicit conditional qualifier, if an enquiry references a scenario, person, or event that has no basis in INITIAL REVIEW or ADDITIONAL INFORMATION, exclude it.

**RULE 6 - NEUTRAL LANGUAGE**: Do not use: "fraudulent", "fraud", "suspicious", "red flags", "motive", "collusion", "grossly", "high-risk". Refer to the underlying event as "incident" rather than "assault" in both the enquiry title and enquiry_detail. Describe the incident neutrally (e.g., "the incident on [date] at [location]") — do not preface with "alleged", "potential", or any qualifier that pre-judges the case. Do not infer intent or wrongdoing.
</CRITICAL_RULES>

<TASK>
**YOUR TASK**
Determine the ADDITIONAL ENQUIRIES required for provided investigation type:

Steps:
1. Read INVESTIGATION PROCESSES first. Identify all additional enquiries/responsibilities specified for the given investigation type. These are your ONLY permitted enquiry topics.

2. Read INITIAL REVIEW and ADDITIONAL INFORMATION to extract case-specific details (names, dates, locations, incident specifics). ADDITIONAL INFORMATION may contain supplementary details (e.g., police reports, engineer reports, incident reports) not captured in INITIAL REVIEW — use these as additional evidence where relevant.

3. For each enquiry identified in Step 1, contextualise it with relevant details from Step 2.

4. Include details about what needs to be done in the additional enquiries. If there are multiple enquiries, details must be explicitly stated for each.

5. Ensure enquiries and details are clear and avoid using any jargons.
</TASK>

<CONTEXT>
These are the relevant materials for your case:

Here is the INVESTIGATION PROCESSES — this is your ONLY source for enquiry topics. Each entry in the array contains the enquiries for ONE investigation type:
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
{gold_standards_block}
{investigation_type_block}
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
