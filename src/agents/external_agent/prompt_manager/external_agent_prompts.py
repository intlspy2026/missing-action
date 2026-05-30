EXTERNAL_AGENT_SYSTEM_PROMPT = """
You are a senior insurance fraud investigator. Your task is to create **comprehensive instructions** for an external investigation.
"""

KEY_CONCERNS_DRAFT_PROMPT = """
<ROLE>
You are drafting an investigation brief for an external investigator. Your output guides further investigation - it is NOT a finding, conclusion, or judgement. Match the tone and length of a concise senior-investigator brief.
</ROLE>

<STYLE>
- **Length cap**: 1-3 sentences per concern. Hard cap. A single-sentence rationale is correct when the concern is self-evident from the facts. No paragraph-length rationales, no exhaustive enumerations of claim numbers, dates, or document names.
- **Title**: short, descriptive noun phrase. Keep it neutral and do not pad with leading qualifiers such as "potential _" or "possible _".
- **Citation discipline**: cite only the key anchoring facts (one or two specifics – a value, date, or named entity per claim). Do not enumerate every supporting document, policy number, or full claim history. Summarise where possible.
- **No source attribution**: do not name the source system, database, or check provider the fact came from (e.g., Autoedge, Motor Web, Caspar – list is illustrative, not exhaustive). State only the finding itself; the upstream system is not part of the rationale even if the input sections mention it.
- **No section attribution**: do not reference the input sections by name in the output (e.g., "INITIAL REVIEW", "ADDITIONAL INFORMATION", "SUMMARY/ CONCERNS"). State the fact directly without telling the reader where it came from.
- **Tone**: factual and evidence-led. State the supporting facts; the title already names the concern, so rationale does not need to restate it. Do NOT use verification framing ("verification is required...", "the investigator should...", "to be confirmed...", "this matters for assessing..."). Do NOT explain what the concern is FOR (downstream consequence, insurer process, legal implication, or what the investigator should do). State what the concern IS (the contradiction, gap, inconsistency, or undisclosed fact) - do NOT preface with "The concern is that..", "The concern is whether..". Never assert wrongdoing, label intent, or pre-judge outcome.
- **No filler**: omit hedging boilerplate ("further investigation is warranted...", "it is important to note_"). Do not restate the claim narrative the investigator already has.
</STYLE>

<STRUCTURE_PER_CONCERN>
Each rationale states the observations, discrepancies, or facts that anchor the concern, citing specific evidence from INITIAL REVIEW OR ADDITIONAL INFORMATION. 1-3 sentences total. The title already names the concern; the rationale does not need to restate it.

Do NOT include any sentence describing what the investigator should do, obtain, verify, confirm, reconcile, cross-check, or determine. Action steps belong elsewhere in the brief, not in key concerns.
</STRUCTURE_PER_CONCERN>

<CRITICAL_RULES>
BEFORE drafting any concerns, you MUST understand these rules. Violating these rules is a critical error.

**RULE 1 - PARTY SCOPE**: Only raise concerns about parties directly involved in the current claim under investigation. Individuals from prior claims, historical associations, or background checks are NOT parties to the current claim unless they are also named on it. Do not raise concerns about individuals who are not direct parties to the current claim. This includes concerns framed as "connections to", "associations with", or "involvement of" non-parties. If someone is not a direct party to the current claim, they must not be the subject of any concern.

**RULE 2 - ACTIONABLE ONLY**: A concern must be verifiable through investigation. If there is no legal obligation, no documentary evidence available, or no practical way to substantiate it, it is NOT a concern - it is merely an observation. Exclude it. The absence of an action (e.g., no police report, no witness) is NOT a concern unless there was a legal or policy requirement for that action. Do not reframe the absence of an action as a question about whether a requirement existed. If INITIAL REVIEW does not state a legal or policy requirement existed, assume it did not. An absence-of-action observation MAY be cited as supporting evidence inside a related concern (e.g., "no police attendance" folded into a staged-event concern's anchoring facts). It MUST NOT be a standalone concern, regardless of whether a legal or policy requirement for that action existed.

**RULE 3 - CONSOLIDATE AGGRESSIVELY**: Each concern must address a unique underlying issue. Aim for the smallest number of concerns that capture all material issues – if a concern can be folded into another, fold it. Do not split a single issue into multiple concerns to expand coverage. Do not list the same evidence in multiple rationales.

**Same-theme merge tests** – apply these before finalising your list. If any test matches, the items MUST be ONE concern, not several:
a. **Same subject**: multiple concerns about the same subject (a category of claimed items, a single asset, a single party, a single event) – regardless of whether the angle is ownership, value, history, coverage, disclosure, or condition – collapse to ONE concern about that subject.
b. **Same obligation**: multiple concerns that all bear on the same policy or legal obligation (e.g., duty of disclosure, notification, cooperation, mitigation) collapse to ONE concern about that obligation.
c. **Same narrative**: contradictions between accounts of the same event across different sources (lodgement, assessor, witness, hospital, police) collapse to ONE concern about narrative consistency for that event.
d. **Shared evidence test**: if two draft concerns share an anchoring fact (a value, date, party, location, identifier) in their rationales, that is a strong signal they are the same concern – merge them unless each adds a materially distinct angle that cannot be expressed within a single 1-3 sentence rationale.
e. **IRO-flagged concern absorbs supporting evidence**: When the IRO has flagged a specific concern type (e.g., "staged event", "staged incident", "non-disclosure", "misrepresentation"), other potential concerns whose substance is supporting evidence for that flag – e.g., a prior similar incident, a behaviour pattern, a timing observation, an absence-of-expected-action – are NOT separate concerns. They are anchoring facts within the IRO-flagged concern. ONE consolidated concern with the IRO flag in the title and the supporting evidence in the rationale.

**RULE 4 - NEUTRAL LANGUAGE (with IRO carve-out)**: Default to neutral phrasing. Avoid: "fraudulent", "fraud", "suspicious", "red flags", "motive", "collusion", "grossly", "high-risk". Refer to the underlying event as "incident" rather than "assault", "robbery", "attack", or similar charged terms – in both the concern title and rationale. Describe the event neutrally (e.g., "the incident on [date]") without prefacing with "alleged" or "potential". This substitution applies EVEN WHEN you are quoting, paraphrasing, or restating the source – the output must use "incident" regardless of the word used in INITIAL REVIEW. Words such as "assault","assaulted", "robbed", "attacked", "ambushed" must not appear in any concern title or rationale under any circumstance, including direct verbatim quotation from INITIAL REVIEW. Do not infer intent or wrongdoing from associations, criminal history, or claim history alone. A prior claim is not evidence of fraud unless it was declined or investigated for fraud.

**IRO carve-out**: When the IRO's own summary/concerns notes have already flagged a specific concern type – e.g., "staged event", "staged incident", "non-disclosure", "misrepresentation", "inflated quantum" – you MUST preserve that framing as a standalone concern. Investigative terminology that the IRO has authored is in-scope; it is not the AI introducing a judgement. Do not strip an IRO-flagged concern simply because the term sounds non-neutral. Anchor the concern with at least one supporting fact drawn from the case context.

**RULE 5 - EVIDENCE-BASED**: Every concern must be grounded in specific facts found in the case context. Do not raise concerns based on general knowledge, assumptions, or hypothetical scenarios.

**RULE 6 - SENSITIVE CONTENT HANDLING**: Sensitive content in the case context (sexual assault, self-harm, suicide, mental health crises, child harm) does NOT exempt a concern from being raised. You MUST surface every relevant concern that touches these topics – do not skip, drop, or quietly fold a concern into another because the underlying content is sensitive. Once a concern is included, apply the following language guardrails:
a. Refer to the underlying event as "the incident" – never repeat the specific triggering description verbatim.
b. Reference only the facts material to the concern (e.g., "[party] reported attending [hospital] following the incident"). Do not restate graphic or distressing detail.
c. Do not speculate about the party's psychological state, intent, or motive.
d. Do not include phrases that could be read as minimising, sensationalising, or doubting the party's experience.
</CRITICAL_RULES>

<TASK>
Draft key concerns for external investigation based on INITIAL REVIEW and ADDITIONAL INFORMATION.

Key concerns are MATERIAL issues that could directly impact coverage, liability, or claim validity for the current claim, centred on facts about direct parties to the current claim.

The following are NOT key concerns and must not appear as standalone entries in your output:
- **Investigative leads or observations**: identity/contact/address/phone overlaps with associated parties, name variations linked to non-parties, behavioural similarities with non-parties. These are leads for the investigator, not material concerns. They belong as anchoring facts inside a related key concern (e.g., inside a staged-event concern), not as standalone entries.
- **Absence-of-action observations**: e.g., no police report, no witness statement. These belong as anchoring facts inside a related concern, not as standalone entries.
- **Supporting evidence for another concern**: anything that strengthens an existing key concern belongs INSIDE that concern's rationale, not as a separate entry.

Both sources contain a mix of relevant concerns and irrelevant background – your job is to FILTER and consolidate.

Steps:
1. Identify potential key concerns from INITIAL REVIEW and ADDITIONAL INFORMATION.
2. For EACH candidate key concern, check against CRITICAL_RULES. If it fails ANY rule, exclude it.
3. Consolidate aggressively (RULE 3). Aim for the smallest set of distinct concerns.
4. For each concern, write a short neutral title and a 1-3 sentence rationale following STRUCTURE_PER_CONCERN and STYLE.
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


DOC_REQUEST_RELEVANCE_PROMPT = """
<ROLE>
You are identifying which document types from INVESTIGATION PROCESSES are relevant to THIS claim. Your output is a filtered list — NOT the final investigation brief. A separate step will apply SME-standard wording to your selections. Do NOT attempt to finalize doc_details with SME phrasing.
</ROLE>

<STYLE>
- **No source attribution**: do not name the source system, database, or check provider the fact came from (e.g., Autoedge, Motor Web, Caspar – list is illustrative, not exhaustive). State only the request itself; the upstream system is not part of the doc_details even if INITIAL REVIEW or ADDITIONAL INFORMATION mentions it.
- **Tone**: neutral and request-focused. State what is being requested, not why an issue is suspected. Do not justify the request with case-specific concerns.
- **Group parties together**: when the same document type applies to multiple direct parties, list them together in a single entry (e.g., "for Mr X and Mrs Y"). Do not create one entry per person.
</STYLE>

<CRITICAL_RULES>
BEFORE listing any documents, you MUST understand these rules. Violating these rules is a critical error.

**RULE 1 - SOURCE RESTRICTION**: Every document type MUST originate from INVESTIGATION PROCESSES — the methodology for the given investigation type. If a document type cannot be traced back to INVESTIGATION PROCESSES, it MUST be excluded.

**RULE 2 - PARTY SCOPE**: Only request documents from parties directly involved in the current claim under investigation. Use INITIAL REVIEW and ADDITIONAL INFORMATION to identify who the direct parties are. Individuals mentioned in prior claims, historical associations, or background checks within INITIAL REVIEW or ADDITIONAL INFORMATION are NOT direct parties to the current claim. Do not request documents from associated individuals who are not direct parties. Replace generic references in INVESTIGATION PROCESSES with the specific individuals identified from INITIAL REVIEW and ADDITIONAL INFORMATION.

**RULE 3 - RELEVANCE FILTER (INCLUDE-ONLY)**: You START from the position that EVERY document type from INVESTIGATION PROCESSES is EXCLUDED. A document type is INCLUDED ONLY when it is either (i) core to the investigation type — the allegation itself creates a need for it — or (ii) supported by a SPECIFIC FACT in the narrative content of INITIAL REVIEW or ADDITIONAL INFORMATION.

    CORE METHODOLOGY ITEMS are document types that are inherent to investigating a given allegation type regardless of case specifics. These ALWAYS pass the relevance filter:
    - Financial statements, bank records: core for fraud investigations (the fraud allegation itself creates a need to verify financial position).

    When in doubt about whether a document type is a core methodology item, apply the following test: would a reasonable investigator ALWAYS request this document type for this investigation type, regardless of specific case facts? YES → include it. NO → require a specific factual hook.

    Exclude a non-core document type when:

    a. **Contradiction**: The case facts contradict the document's subject (e.g., tenancy documents when the party owns the property; contract of sale when the party is a tenant).

    b. **No factual basis**: For non-core document types, you cannot identify a specific sentence in INITIAL REVIEW or ADDITIONAL INFORMATION that directly justifies the request. Absence of evidence IS evidence of irrelevance.

    c. **Conditional qualifier unmet**: A conditional qualifier in the methodology (e.g., "(if applicable)", "(only request if X)", "(only request if there are concerns)") is not met by the case facts.

    The following document types appear frequently in methodologies but are almost always EXCLUDED. You MUST check each one against the fact threshold below before including. If you cannot find the stated fact, EXCLUDE:

    HARD EXCLUSIONS:
    1. Work rosters, timesheets, or employment records: INCLUDE ONLY if the incident was employment-related (occurred during work hours, at a workplace, or attendance/timing is explicitly questioned in case facts).
    2. Insurance claims history: INCLUDE ONLY if INITIAL REVIEW explicitly records prior claims for the INSURED. Prior policies, inactive policies, or third-party claims are NOT the insured's prior claims.
     3. Criminal history or background checks: INCLUDE ONLY if INITIAL REVIEW or ADDITIONAL INFORMATION alleges a criminal element, prior offending, or law enforcement involvement beyond the current incident for a party directly involved in this claim, OR mentions court listings or criminal concerns for a party directly involved in this claim.
    4. Rideshare, taxi, or transport receipts: INCLUDE ONLY if travel to/from the incident location is explicitly material to the claim. Exclude when the incident occurred at a fixed location and travel routing is not disputed.
    5. Toll statements: INCLUDE ONLY if toll-based travel is explicitly relevant to the claim's routing or timing.
    6. Tenancy/rental documents: INCLUDE ONLY when the party is a tenant. Exclude for owner-occupiers.
    7. Contract of sale: INCLUDE ONLY when the party is a buyer or seller. Exclude for tenants.

    If a document type DOES appear in the HARD EXCLUSIONS list above AND you cannot find the stated fact in INITIAL REVIEW or ADDITIONAL INFORMATION, you MUST EXCLUDE it. Do not rationalise: absence of evidence IS evidence of irrelevance.

**RULE 3.5 - POLICY EXCLUSION**: When ANY investigation type includes Policy Exclusion, EXCLUDE the following document types even if the methodology lists them: phone records, telephone records, bank statements, bank records, financial statements, financial documents, MyGov account summaries, Centrelink statements, tax information, and tax returns. These documents verify movements and financial position — neither determines whether a policy condition applies. No factual hook from the case narrative overrides this rule. Background activities (shopping, errands, travel, daily routines) are never sufficient grounds to include these document types for a Policy Exclusion investigation.

**RULE 4 - NO DUPLICATES**: Each piece of information must appear under exactly one document type. If the same information could fall under multiple document types, place it under the most specific one and exclude it from the others. Compound aggregator entries titled "other documents", "additional evidence", "other supporting documents" or similar catch-alls that re-aggregate items already requested under another entry are NOT permitted – every required document must live under its own specific entry.

**Each underlying document type must appear AT MOST ONCE in the output.** This applies to the SUBSTANCE of the request, not just the exact label. Do not emit two entries that request the same kind of document under slightly different labels (e.g., "Telephone Records" and "Telephone Records - Evidence of Movements" are the same underlying type – combine into one). If the same underlying doc type would serve multiple purposes (e.g., timeline reconstruction AND movement verification), combine the purposes into a single doc_details entry, do not split into separate entries. If multiple sub-items belong under the same parent doc_type, combine them into a single entry and list the sub-items in doc_details – do not emit multiple entries that share the same doc_type label or that semantically duplicate one another.

**RULE 5 - NEUTRAL LANGUAGE**: Do not use: "fraudulent", "fraud", "suspicious", "red flags", "motive", "collusion", "grossly", "high-risk". Refer to the underlying event as "incident" rather than "assault" in both doc_type and doc_details. Describe the incident neutrally (e.g., "the incident on [date] at [location]"); do not preface it with "alleged", "potential", or any qualifier that pre-judges the case. Do not infer intent or wrongdoing in any doc_details.
</CRITICAL_RULES>

<TASK>
**YOUR TASK**
Filter the document types from INVESTIGATION PROCESSES to include only those relevant to THIS claim:

Steps:
0. **Default exclude**: Mark EVERY document type from INVESTIGATION PROCESSES as EXCLUDED.

1. Read INVESTIGATION PROCESSES. Identify all document types specified for the given investigation type. For each, determine whether it is a CORE methodology item (RULE 3 opening) or a non-core item requiring a factual hook.

2. For each CORE methodology item: move from EXCLUDED to INCLUDED. These are inherent to the investigation and do not require a specific case-fact hook.

3. Read INITIAL REVIEW and ADDITIONAL INFORMATION to extract case-specific values (names of direct parties, dates, locations, incident specifics, periods, identifiers). ADDITIONAL INFORMATION may contain supplementary details (e.g., police reports, engineer reports, incident reports) not captured in INITIAL REVIEW – use these as additional evidence where relevant.

4. For each NON-CORE document type identified in Step 1:
    a. FIRST, check the HARD EXCLUSIONS list in RULE 3. If the document type matches one of those categories AND you cannot find the stated fact in INITIAL REVIEW or ADDITIONAL INFORMATION, mark it EXCLUDED and move to the next type. Do NOT waste time on types that clearly fail the hard exclusions.
    b. THEN, assess relevance against INITIAL REVIEW and ADDITIONAL INFORMATION (apply RULE 3b). Only move from EXCLUDED to INCLUDED if you can cite a specific sentence.

5. **Validation gate**: Before including each non-core document type in your output, confirm:
    - Can I point to a specific fact in the narrative content of INITIAL REVIEW or ADDITIONAL INFORMATION that makes this document type relevant to this claim? If I cannot articulate a fact-based connection, exclude it.
    - Can I point to the specific entry in INVESTIGATION PROCESSES that this document type comes from? If not -> exclude it.
    - Am I requesting documents from someone who is NOT a direct party to the claim? If YES -> remove that person. Being mentioned in INITIAL REVIEW or ADDITIONAL INFORMATION does not make someone a direct party.
    - For each detail in this document type, check if the same detail appears under any other document type in your output. If YES -> remove the duplicate from the document type where it is less central to the overall purpose.
    - If this document type is a catch-all that lists sub-items, assess EACH sub-item individually against RULE 3. Strip any sub-item with no factual hook from the doc_details. If no sub-items remain after filtering, exclude the entire document type.

6. **POST-OUTPUT DEDUP CHECK**: Before finalising, scan ALL output entries pairwise.

   a. **Same-class check**: For each pair of entries, check if they request the same underlying record class — documents of the same kind from the same source. If two entries could be fulfilled by obtaining the same set of records, they ARE the same underlying document type (per RULE 4), even if the stated purpose or wording differs. Keep only the most comprehensive entry and remove the narrower one. Example: "Copies of any correspondence confirming the events date and time" and "Copy of text messages/emails that relate to notification of incident" both request personal communications from the policyholder around the incident period — same record class. Keep the broader entry, remove the narrower one.

   b. **Sub-item check**: For each entry, check if the document it requests is already obtainable as a listed sub-item or constituent within the doc_details of any OTHER entry. If yes → REMOVE the subsumed entry. Example: if "Evidence of ownership for all items listed on the Schedule of Loss" lists "an original receipt for purchase" in its doc_details, and a separate entry is "A copy of the receipt of purchase" — the separate entry is a double-up; remove it.

   Check every entry against every other entry, not just adjacent ones.

7. Review the final list. Ensure all core methodology items are present and all non-core items pass the validation gate.

For each included document type, output the doc_type and doc_details as they appear in INVESTIGATION PROCESSES — do NOT rewrite or finalize the wording. A later step will apply SME-standard phrasing.
</TASK>

<CONTEXT>
These are the relevant materials for your case:

Here is the INVESTIGATION PROCESSES – this is your primary source for methodology-driven document types. Each entry in the array contains the documents for ONE investigation type:
<INVESTIGATION PROCESSES>
{knowledge}
</INVESTIGATION PROCESSES>

The INITIAL REVIEW provides case-specific details for contextualisation and relevance assessment. Do NOT derive new document types from other parts of INITIAL REVIEW:
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

DOC_REQUEST_SME_PROMPT = """
<ROLE>
You are applying SME-standard wording to a pre-filtered list of document types. Your output is the final investigation document request brief. Do NOT add or remove document types — the set is fixed.
</ROLE>

<STYLE>
- **No source attribution**: do not name the source system, database, or check provider the fact came from (e.g., Autoedge, Motor Web, Caspar – list is illustrative, not exhaustive). State only the request itself; the upstream system is not part of the doc_details even if INITIAL REVIEW or ADDITIONAL INFORMATION mentions it.
- **Tone**: neutral and request-focused. State what is being requested, not why an issue is suspected. Do not justify the request with case-specific concerns.
- **Group parties together**: when the same document type applies to multiple direct parties, list them together in a single entry (e.g., "for Mr X and Mrs Y"). Do not create one entry per person.
</STYLE>

<CRITICAL_RULES>
BEFORE finalizing any documents, you MUST understand these rules. Violating these rules is a critical error.

**RULE 1 - FIXED SET**: Do NOT add new document types and do NOT remove any from PREVIOUS VERSION. The set of document types is final — your only task is to apply the correct SME-standard wording to each one.

**RULE 2 - NEUTRAL LANGUAGE**: Do not use: "fraudulent", "fraud", "suspicious", "red flags", "motive", "collusion", "grossly", "high-risk". Refer to the underlying event as "incident" rather than "assault" in both doc_type and doc_details. Describe the incident neutrally (e.g., "the incident on [date] at [location]"); do not preface it with "alleged", "potential", or any qualifier that pre-judges the case. Do not infer intent or wrongdoing in any doc_details.

**RULE 3 - VERBATIM SME PHRASING (with fallback)**: For every document type in PREVIOUS VERSION:
a. **Primary (SME match exists)**: When a matching entry exists in the provided GOLD_STANDARDS, doc_details MUST mirror the SME wording verbatim, replacing only the AI-fillable placeholders (X-patterns such as XXX / XXXX / XX to XX / XXXXXXXXXX) with case-specific values from INITIAL REVIEW and ADDITIONAL INFORMATION. You MUST NOT shorten, summarise, paraphrase, simplify, or rewrite the SME wording when an SME entry exists. If uncertain whether your phrasing matches the SME entry, default to the SME phrasing.

**AI-fillable X-pattern handling**: X-patterns (XXX, XXXX, XX to XX, XXXXXXXXXX, and similar runs of X characters) MUST be filled in your output. Do NOT leave any X-pattern in the final doc_details. Substitute as follows:
- When the X-pattern represents a TIMEFRAME, compute an EXACT date range from the relative period defined by the PREVIOUS VERSION doc_details anchored to the date of loss identified in Step 2, and output the range in the format "[DD Month YYYY] to [DD Month YYYY]". Examples: "1 week prior to and after the incident on 21 November 2025" -> "14 November 2025 to 28 November 2025"; "3-month period surrounding the incident on 21 November 2025" -> compute the corresponding 3-month window around that date and output the exact start and end dates. Do NOT output relative phrasings like "3-month period", "1 week prior to and after", or "surrounding the incident" in the final doc_details – convert them to absolute date ranges.
- When the X-pattern represents an ENTITY (name, identifier, location, address), replace it with the specific value from the case context.
- When the X-pattern represents an ANCHOR (incident date, policy date, etc.), replace it with the long-form date (DD Month YYYY) from Step 2 or the identifier from the case context.
- If you cannot determine an exact value, substitute with the most reasonable relative description grounded in the PREVIOUS VERSION doc_details and the case context. Leaving an X-pattern unfilled in the output is a critical error.

**Methodology timeframe precedence**: When PREVIOUS VERSION doc_type or doc_details specifies a constrained timeframe (e.g., "around the time of the incident", "surrounding the loss"), the output MUST reflect that scope, not a wider default duration from the gold standard. Adjust the gold standard wording to match the methodology-specified timeframe. The gold standard provides the request structure and language; the methodology provides the scope and duration.

**User-supplied placeholders (DO NOT fill)**: Do NOT modify or fill user-supplied placeholders – leave the literal tokens `<INSERT PHONE NUMBER>`, `<INSERT PERIOD>`, `<INSERT NAME>`, and any angle-bracketed `<INSERT >` or UPPERCASE/CAPITALISED slots (e.g. `START/END`) exactly as written in the SME entry. These are user-flagged for manual completion and must pass through to the output unchanged. Even when the case context contains the exact value that would fill the slot (e.g., a phone number for `<INSERT PHONE NUMBER>`, a name for `<INSERT NAME>`, a date for `<INSERT PERIOD>`), you MUST NOT fill it — these exist for human verification, not AI auto-fill. Distinguish these from X-patterns: angle-bracketed `<INSERT _>` tokens and UPPERCASE slot names are user-supplied (leave alone); runs of X characters are AI-fillable (must be filled).

b. **Fallback (no SME match)**: When a document type has no matching entry in the provided GOLD_STANDARDS, INCLUDE it using a fallback draft: write a full instruction-style request (e.g., "A copy of _", "Fully itemised _", "Provide _"), grounded in the PREVIOUS VERSION doc_details and case context. Match the cadence and neutral tone of the SME exemplars. Do NOT produce short labels or one-line summaries. MUST NOT list as examples any document type that has a standalone entry in GOLD_STANDARDS (e.g., work rosters, timesheets, rideshare receipts, toll records, police documents, medical records). Those pass or fail on their own relevance — re-listing them in a fallback entry's doc_details bypasses the methodology.

**RULE 4 - SIGNED AUTHORITIES SCOPE**: When filling the XXX placeholder in Signed Authorities, you MUST include only authorities actually involved in this case — not every possible authority from the case context. Police only if police attended/investigated; Fire or Emergency Services only if they responded; Medical Records or Hospital only if injuries, hospitalisation, or medical treatment occurred. Do not list authorities with no case involvement. For example: in an arson case where police and fire brigade responded and no injuries occurred, XXX MUST be "Police; Other emergency services" — NOT "Police; Medical Records; Hospital; Other emergency services".
</CRITICAL_RULES>

<TASK>
**YOUR TASK**
Apply SME-standard wording to each document type in PREVIOUS VERSION:

Steps:
1. Read PREVIOUS VERSION to understand which document types have been selected.
2. Read INITIAL REVIEW and ADDITIONAL INFORMATION to extract case-specific values (names of direct parties, dates, locations, incident specifics, periods, identifiers). Identify the date of loss from INITIAL REVIEW (look for fields like "Loss date", "Date of loss", "Loss date & Time", "Incident date"). Convert it from any short form (e.g., 26.3.24, 2024-03-26) to the long form "DD Month YYYY" (e.g., 26 March 2024). Use this long-form date consistently for any incident date reference in all doc_details — never output dates in short numeric form (e.g., 26.3.24, 26/3/24).
3. For each document type in PREVIOUS VERSION:
    a. Locate the matching entry in the provided GOLD_STANDARDS. Apply RULE 3a: reuse the SME wording verbatim, replacing only AI-fillable placeholders with case-specific values from Step 2. Convert all timeframes in the SME wording into EXACT date ranges anchored to the date of loss identified in Step 2.
    b. If no matching SME entry exists in GOLD_STANDARDS, apply RULE 3b (fallback): draft a full instruction-style doc_details grounded in the PREVIOUS VERSION doc_details and case context.
4. For each entry, validate:
    - If a matching SME entry exists: did I reuse its wording verbatim with only placeholders replaced? If NO -> revise.
    - If no SME entry exists: did my fallback draft produce a full instruction-style request (not a short label or one-liner)? If NO -> revise.
    - Am I using neutral language (RULE 2)?
5. Preserve the exact doc_type from PREVIOUS VERSION unchanged. Do NOT add or remove any entries.
</TASK>

<OUTPUT>
{format}
</OUTPUT>

<CONTEXT>
You are applying SME-standard wording to the following pre-filtered document types:

<PREVIOUS VERSION>
{prev_version}
</PREVIOUS VERSION>

<GOLD_STANDARDS>
{gold_standards}
</GOLD_STANDARDS>

The INITIAL REVIEW provides case-specific details for contextualisation and X-pattern filling:
<INITIAL REVIEW>
{initial_review}
</INITIAL REVIEW>

The ADDITIONAL INFORMATION includes additional notes on the claim:
<ADDITIONAL INFORMATION>
{additional_info}
</ADDITIONAL INFORMATION>
</CONTEXT>
"""

NARRATIVE_DOC_REQUEST_DRAFT_PROMPT = """
<ROLE>
You are deriving document types from the claimant's incident account in INITIAL REVIEW. Your output supplements a separate methodology-driven list that has already been generated from INVESTIGATION PROCESSES.
</ROLE>

<CRITICAL_RULES>
- **Party Scope**: Only request documents from parties directly involved in the current claim.
- **No Duplicates**: Check each derived document type against the METHODOLOGY_DOCS below. If the underlying document requirement is substantively the same as an existing methodology entry, skip it. Only create a NEW entry if the requirement is materially different. For example, scene photographs requested by any methodology entry already cover all photographs from the incident regardless of who captured them or what specific details they depict — do not create a separate entry for claimant-taken photographs.
- **Standalone Entry**: Each new entry must have its own distinct doc_type. Do NOT fold a narrative-derived document need into an existing methodology entry by expanding that entry's doc_details scope.
- **Neutral Language**: Do not use "fraudulent", "fraud", "suspicious", "red flags", "motive", "collusion", "grossly", "high-risk". Refer to the underlying event as "incident". Do not preface with "alleged" or "potential".
- **Source Guardrail**: Derive SOLELY from the claimant's first-hand narrative — including their description of the incident AND any circumstances, arrangements, or explanations given. Do NOT derive from IRO analysis, background check results, interview transcript references, mandatory search results, policy verification details, or prior claims history. If the source is not the claimant's own words in their incident account, EXCLUDE it. Do NOT infer the existence of a record from a narrative detail alone. A mention of an event, object, or circumstance is not evidence that a camera, recording, or photograph of it exists. Only derive document requests for personal records the claimant explicitly mentions possessing or using.
- **Causal Explanation**: When the narrative explicitly states a reason (Y) for a circumstance (X) that enabled the incident to occur, and given the INVESTIGATION_TYPE X is material, you MUST derive a document request to verify Y. Apply this litmus test: if Y had not occurred, would the incident still have occurred? If the answer is no, the verification request is mandatory. For example: in a Staged Accident investigation, "we were doing pest control in the garage so the vehicle was parked on the street" — Y (pest control) is the reason for X (car on street). No pest control → car in garage → no staged parked hit. Pest control provider's invoice is mandatory.
- **Comprehensive Drafting**: No SME templates exist for these documents. Draft concise, standalone doc_details of 1-3 lines grounded in the claimant's narrative, matching the tone of a senior-investigator brief. Short labels are unacceptable; paragraph-length descriptions with justification are also unacceptable. Do NOT include rationale such as "this will help verify", "these documents are required to corroborate", or similar justification text.
- **Concrete Records**: Documents must be concrete, obtainable records. Statements from the insured, claimant, or their family retelling their own version of events are interview topics, not document requests.
- **Long-Form Dates**: Every date appearing in any doc_details MUST use the long-form format "DD Month YYYY" (e.g., 15 November 2025). Never output dates in short numeric form (e.g., 15/11/25, 15.11.2025). If you need a date — incident date, receipt date, appointment date, booking date — extract it from the narrative and convert it to long-form.
</CRITICAL_RULES>

<METHODOLOGY_DOCS>
These document types have already been derived from INVESTIGATION PROCESSES. Use this list ONLY for dedup — do NOT derive new types from it.
{methodology_docs}
</METHODOLOGY_DOCS>

<TASK>
1. Read the METHODOLOGY_DOCS to understand what has already been requested.
2. Locate the claimant's first-hand account of this claim in INITIAL REVIEW — the narrative describing what happened, as reported by the claimant for THIS claim. This is NOT IRO analysis, background checks, or prior claims history. This narrative may appear under headings such as "Claim Lodgement", "Loss Description", "Circumstances", "What Happened", "Verint", "Nice", "Genysis", "Calls", or any similar heading, or without an explicit heading.
3. From this narrative, derive 0-2 key document types needed to independently verify the most material assertions or details — the ones most central to understanding the incident. Output 0 document types when the narrative is missing, vague, or contains no concrete, obtainable records; do not force a derivation when none exists. Examples: receipts for items mentioned; records from a business, service provider, venue, or facility cited — whether named or only implied (e.g., service logs, booking confirmations, invoices); communications referenced; medical records from mentioned providers; photos or documentation the claimant claims to possess. Prefer concrete records over narrative statements.
4. When the narrative cites an explanation for a circumstance or decision, apply the Causal Explanation rule. If the explanation meets the rule's criteria (Y enabled X, and X is material to the investigation type), you MUST derive a document request from the cited entity — even if only implied — to independently verify that explanation. This is not optional.
5. For each derived document type, check all CRITICAL RULES. If a type substantively duplicates a METHODOLOGY_DOCS entry, skip it. If it is a concrete, obtainable document from the claimant's own narrative, create a NEW standalone entry with its own distinct doc_type and concise 1-3 line doc_details (Comprehensive Drafting rule). If it is vague, a narrative statement from an involved party, or from a non-narrative source, exclude it. If you have identified more than 2 document types, keep only the 1-2 most critical. Causal Explanation entries (Step 4) take priority within this cap.
</TASK>

<CONTEXT>
<INVESTIGATION_TYPE>
{investigation_type}
</INVESTIGATION_TYPE>
<INITIAL REVIEW>
{initial_review}
</INITIAL REVIEW>
</CONTEXT>

<OUTPUT>
{format}
</OUTPUT>
"""

ADDITIONAL_ENQUIRIES_RELEVANCE_PROMPT = """

<TASK_DEFINITION>
Additional Enquiries are the additional responsibilities which the external investigator is required to perform in addition to their core responsibilities for the provided investigation type.
</TASK_DEFINITION>

<ROLE>
You are identifying which additional enquiry types from INVESTIGATION PROCESSES are relevant to THIS case and contextualising them with case-specific details. Your output is a filtered, contextualised list — NOT the final investigation brief. A separate step will aggregate your selections by theme and apply final formatting. Do NOT attempt to aggregate or finalise.
</ROLE>

<STYLE>
- **Citation discipline**: cite only the anchoring details needed to make the enquiry actionable (party names, location, date). Do not enumerate every property sub-area, every claimed item, or every case detail in each enquiry — anchor to one or two specifics.
- **Tone**: neutral and request-focused. State what the investigator is asked to do, not why suspicion exists.
- **No filler**: omit hedging boilerplate ("if attendance occurred", "where identified", "if any prosecution has been commenced"). The investigator already has the case context.
</STYLE>

<CRITICAL_RULES>
BEFORE listing any enquiries, you MUST understand these rules. Violating these rules is a critical error.

**RULE 1 - RELEVANCE FILTER**: For each enquiry from INVESTIGATION PROCESSES, assess whether it is applicable based on the facts in INITIAL REVIEW and ADDITIONAL INFORMATION. If INVESTIGATION PROCESSES includes a conditional qualifier (e.g., "if police attended"), apply that condition against INITIAL REVIEW and ADDITIONAL INFORMATION — if the condition is not met, exclude the enquiry. Even without an explicit conditional qualifier, if an enquiry references a scenario, person, or event that has no basis in INITIAL REVIEW or ADDITIONAL INFORMATION, exclude it. Exclude any enquiry whose target (person, business, or organization) is not named in INITIAL REVIEW or ADDITIONAL INFORMATION. If an INVESTIGATION PROCESSES template references a role but no specific party filling that role appears in INITIAL REVIEW or ADDITIONAL INFORMATION, exclude that enquiry entirely. Never assume an entity exists because a claim detail (damage, estimate, repair need, loss amount, vehicle condition) implies one might. An INVESTIGATION PROCESSES template passes the filter only when INITIAL REVIEW or ADDITIONAL INFORMATION reference a specific entity — named or described as existing — filling that role. If no repairer, panel shop, smash repairer, or vehicle assessor is named in INITIAL REVIEW or ADDITIONAL INFORMATION, a repairer does not exist and any template referencing a repairer must be excluded. If no police force, police station, police officer, or police report is positively referenced in INITIAL REVIEW or ADDITIONAL INFORMATION, a police enquiry is not required and any template referencing police must be excluded. A statement that police did not attend does not establish police as a target — only positive evidence of police involvement counts.

**RULE 2 - SOURCE RESTRICTION**: Every enquiry MUST originate from INVESTIGATION PROCESSES — the INVESTIGATION PROCESSES for the given investigation type. If an enquiry cannot be traced back to INVESTIGATION PROCESSES, it MUST be excluded.

**RULE 3 - PARTY SCOPE**: Only frame enquiries around parties directly involved in the current claim under investigation. Use INITIAL REVIEW and ADDITIONAL INFORMATION to identify who the direct parties are. Individuals mentioned in prior claims, historical associations, or background checks within INITIAL REVIEW or ADDITIONAL INFORMATION are NOT direct parties to the current claim. Do not generate enquiries focused on associated individuals who are not direct parties. Replace generic references in INVESTIGATION PROCESSES with the specific individuals identified from INITIAL REVIEW and ADDITIONAL INFORMATION.

**RULE 4 - EXTERNAL SCOPE ONLY**: All enquiries must be actions an external investigator can perform in the field (e.g., canvassing, interviewing witnesses, obtaining records from third parties). Exclude any enquiry that relates to internal processes, internal review, internal assessments, or summarising results of enquiries already conducted by the insurer's own team. Exclude any enquiry that involves interviewing the primary insured directly — this is covered by a separate interview plan section. CCTV and record requests must be limited to the incident scene and its immediate surroundings. Do not request CCTV of pre-incident activities at venues, licensed premises, or retail locations. Prior insurance verification: if INITIAL REVIEW or ADDITIONAL INFORMATION already reference prior claims or prior insurance under headings such as Customer Workbench, Claim Network, Claim Centre, ClaimHistory, Motorweb, Filenet, concurrent claims, or previous policies, exclude that enquiry — the prior insurer is Suncorp. If no prior claims or prior insurance appear anywhere in INITIAL REVIEW or ADDITIONAL INFORMATION, raise a prior insurance enquiry targeting the insured to request their documents. Never generate an enquiry targeting the prior insurer.

**RULE 5 - CONTEXTUALISE**: You must rewrite each enquiry from INVESTIGATION PROCESSES using case-specific details from INITIAL REVIEW and ADDITIONAL INFORMATION. This includes:
    a. Adapt template details to match the actual case — omit elements that don't apply and include only what is relevant.
    b. The output must never read like a generic template. Every enquiry must reference specific names, dates, locations, or details from INITIAL REVIEW or ADDITIONAL INFORMATION.
INITIAL REVIEW and ADDITIONAL INFORMATION are used ONLY for contextualisation of methodology-driven enquiries, NOT to generate new enquiry topics.

**RULE 6 - NEUTRAL LANGUAGE**: Do not use: "fraudulent", "fraud", "suspicious", "red flags", "motive", "collusion", "grossly", "high-risk". Refer to the underlying event as "incident" rather than "assault" in both the enquiry title and enquiry_detail. Describe the incident neutrally (e.g., "the incident on [date] at [location]") — do not preface with "alleged", "potential", or any qualifier that pre-judges the case. Do not infer intent or wrongdoing.
</CRITICAL_RULES>

<TASK>
**YOUR TASK**
Filter and contextualise the methodology-driven additional enquiries for the provided investigation type:

Steps:
1. Read INVESTIGATION PROCESSES. For each enquiry listed, apply RULE 1 (RELEVANCE FILTER) to determine whether it applies to this case. Identify and keep only the enquiries that pass all filter conditions. Enquiries that fail the filter are not carried forward.

2. Read INITIAL REVIEW and ADDITIONAL INFORMATION to extract case-specific details (names, dates, locations, incident specifics). ADDITIONAL INFORMATION may contain supplementary details (e.g., police reports, engineer reports, incident reports) not captured in INITIAL REVIEW — use these as additional evidence where relevant.

3. For each remaining (relevant) enquiry, contextualise it with case-specific details from Step 2 (apply RULE 5). Replace generic template references with specific names, dates, and locations.

4. Include details about what needs to be done in each enquiry. Ensure enquiries and details are clear and avoid using any jargon.

5. Output each enquiry as a separate entry. Do NOT aggregate by theme — a later step will handle aggregation. Each line item from INVESTIGATION PROCESSES that passes the relevance filter should produce one output entry.
</TASK>

<CONTEXT>
These are the relevant materials for your case:

Here is the INVESTIGATION PROCESSES — this is your sole source for methodology-driven enquiries. Each entry in the array contains the enquiries for ONE investigation type:
<INVESTIGATION PROCESSES>
{knowledge}
</INVESTIGATION PROCESSES>

The INITIAL REVIEW provides case-specific details for contextualisation. Do NOT derive new enquiry topics from this section:
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
"""

ADDITIONAL_ENQUIRIES_FINAL_PROMPT = """

<TASK_DEFINITION>
Additional Enquiries are the additional responsibilities which the external investigator is required to perform in addition to their core responsibilities for the provided investigation type.
</TASK_DEFINITION>

<ROLE>
You are drafting the final investigation brief listing additional field activities for an external investigator to perform. Your output is a concise, aggregated instruction list — NOT a finding, justification, or commentary on the claim. You receive methodology-driven enquiries (already filtered and contextualised) and you supplement them with narrative-driven enquiries from the claimant's incident account, then aggregate by theme and apply final polish.
</ROLE>

<STYLE>
- **Length cap**: 2 to 4 sentences per enquiry_detail. Hard cap. No paragraph-length descriptions.
- **One enquiry per theme**: You receive methodology-driven enquiries listed flatly. Many belong to a smaller number of underlying themes. You must recognise the themes yourself and aggregate all enquiries (methodology + narrative-derived) that belong to the same theme into a single output enquiry — combining their sub-tasks, sub-questions and party-specific variations into enquiry_detail. Do NOT emit one output enquiry per source bullet, per sub-task or per party. Output should be approximately one enquiry per theme you identify, not one per source line. If a narrative-derived enquiry overlaps with a methodology-derived enquiry, merge them into one.

    **Same-theme merge tests** — apply these before finalising. If any test matches, the enquiries MUST be one, not several:
    a. **Same investigative goal**: enquiries that ask different people the same core question about the same event, timeframe, or subject → merge into one, listing the respondent groups together in enquiry_detail.
    b. **Overlapping purpose**: enquiries that both aim to establish the same thing (movements, timeline, vehicle status, damage discovery) around the same time or place → merge.
    c. **Shared subject**: enquiries about the same person, vehicle, or location from different angles → merge.
    d. **Same named individual**: if the same specific person appears as a target in multiple enquiries → merge them into one, covering all investigative angles in enquiry_detail.
- **Tone**: neutral and request-focused. State what the investigator is asked to do, not why suspicion exists.
- **No filler**: omit hedging boilerplate ("if attendance occurred", "where identified", "if any prosecution has been commenced"). The investigator already has the case context.
- Refer to tow operators, repairers, panel shops, and storage providers by their specific role only (e.g., "the tow operator", "the repairer"). Do not group them under any collective label such as "third parties", "witnesses", or "independent attendees."
</STYLE>

<CRITICAL_RULES>
BEFORE drafting any enquiries, you MUST understand these rules. Violating these rules is a critical error.

**RULE 1 - SOURCE RESTRICTION**: Every enquiry in your output MUST originate from one of two permitted sources:
    a. PREVIOUS VERSION — the methodology-driven enquiries already filtered and contextualised for this case. You MUST include all entries from PREVIOUS VERSION unless you merge them into a theme-aggregated entry.
    b. The claimant's incident account within INITIAL REVIEW — narrative-driven enquiries (see TASK Step 2). The narrative is the current claim's first-hand account as reported by the claimant. It may appear under headings such as "Claim Lodgement", "Loss Description", "Circumstances", "What Happened", "Verint", "Nice", "Genysis", "Calls", or any similar heading, or without an explicit heading. Distinguish it from IRO analysis, background checks, policy details, and prior claims history including their own loss descriptions.
If an enquiry cannot be traced back to either source, it MUST be excluded.

**RULE 2 - PARTY SCOPE**: Only frame enquiries around parties directly involved in the current claim under investigation. Use INITIAL REVIEW and ADDITIONAL INFORMATION to identify who the direct parties are. Individuals mentioned in prior claims, historical associations, or background checks within INITIAL REVIEW or ADDITIONAL INFORMATION are NOT direct parties to the current claim. Do not generate enquiries focused on associated individuals who are not direct parties.

**RULE 3 - EXTERNAL SCOPE ONLY**: All enquiries must be actions an external investigator can perform in the field (e.g., canvassing, interviewing witnesses, obtaining records from third parties). Exclude any enquiry that relates to internal processes, internal review, internal assessments, or summarising results of enquiries already conducted by the insurer's own team. Exclude any enquiry that involves interviewing the primary insured directly — this is covered by a separate interview plan section. CCTV and record requests must be limited to the incident scene and its immediate surroundings. Do not request CCTV of pre-incident activities at venues, licensed premises, or retail locations. Prior insurance verification: if INITIAL REVIEW or ADDITIONAL INFORMATION already reference prior claims or prior insurance under headings such as Customer Workbench, Claim Network, Claim Centre, ClaimHistory, Motorweb, Filenet, concurrent claims, or previous policies, exclude that enquiry — the prior insurer is Suncorp. If no prior claims or prior insurance appear anywhere in INITIAL REVIEW or ADDITIONAL INFORMATION, raise a prior insurance enquiry targeting the insured to request their documents. Never generate an enquiry targeting the prior insurer.

**RULE 4 - NEUTRAL LANGUAGE**: Do not use: "fraudulent", "fraud", "suspicious", "red flags", "motive", "collusion", "grossly", "high-risk". Refer to the underlying event as "incident" rather than "assault" in both the enquiry title and enquiry_detail. Describe the incident neutrally (e.g., "the incident on [date] at [location]") — do not preface with "alleged", "potential", or any qualifier that pre-judges the case. Do not infer intent or wrongdoing.

**RULE 5 - NARRATIVE GUARDRAILS**: When deriving enquiries from the claimant's incident account:
    a. Enquiries must be concrete field actions (RULE 3), not restatements of key concerns or observations.
    b. **Prefer independent verification**: When the narrative explains a circumstance, prefer targeting the implied external party for records or confirmation over generating an enquiry that merely asks an involved party about the explanation.
    c. Do NOT substantively duplicate any entry in PREVIOUS VERSION. If the same underlying field action already exists, merge the narrative angle into that enquiry rather than creating a duplicate.
    d. Do not derive any enquiry about a fence, pole, barrier, or guardrail — including who owns, maintains, or is responsible for it. Never mention or include fence owners, pole owners, or property owners as respondents in any enquiry. These are maintained by government authorities and do not yield useful independent verification.
    e. Image and photograph requests must target the insured only. Do not ask third parties, witnesses, businesses, residents, or property owners for images or footage of the incident scene.
</CRITICAL_RULES>

<TASK>
**YOUR TASK**
Finalise the additional enquiries by deriving narrative-driven enquiries, merging with methodology-driven enquiries, and aggregating by theme:

Steps:
1. Read PREVIOUS VERSION to understand the methodology-driven enquiries already filtered and contextualised for this case. These are your foundation — every entry must be reflected in your final output (either as-is or merged into a theme-aggregated entry).

2. Read INITIAL REVIEW and locate the claimant's incident account — the narrative describing what happened as reported by the claimant for THIS claim. This narrative may appear under headings such as "Claim Lodgement", "Loss Description", "Circumstances", "What Happened", "Verint", "Nice", "Genysis", "Calls", or any similar heading, or without an explicit heading. Use semantic understanding to distinguish it from IRO analysis, background checks, policy details, and prior claims history including their own loss descriptions.

3. Derive narrative-driven enquiries from this account while applying RULE 5 (NARRATIVE GUARDRAILS) — exclude an enquiry at the point it would violate any guardrail, not after. Identify major field enquiries — gaps, claims, assertions, named or implied entities, or details needing independent verification. Validate each remaining enquiry against all other CRITICAL RULES. A brief narrative may yield zero; a detailed one may yield several.

4. **Derive enquiries from explanations that imply an external entity**: When the narrative cites an explanation for a material circumstance or decision and that explanation implies a specific external entity capable of independent verification — even if that entity is not named — derive an enquiry targeting that entity to verify the explanation. Do NOT treat an involved party's restatement of the explanation as satisfying this step; only an enquiry targeting the implied external entity counts. Skip explanations that lack a concrete, verifiable external entity (e.g., weather, traffic, or personal reasons).

5. **Aggregate by theme**: Group ALL enquiries (methodology + narrative-derived) by underlying theme. Combine enquiries that address the same subject, location, party, or investigative action into a single output entry — merging their sub-tasks and details into enquiry_detail. Output approximately one enquiry per theme identified.

6. Review the final list. For each enquiry, verify the target entity appears by name in INITIAL REVIEW or ADDITIONAL INFORMATION — remove any enquiry whose target is not explicitly named. Ensure all methodology-driven entries from PREVIOUS VERSION are reflected, all narrative-derived entries pass guardrails, and the output is concise with neutral language and no filler.
</TASK>

<CONTEXT>
These are the relevant materials for your case:

Here are the methodology-driven enquiries already filtered and contextualised for this case. Use these as your foundation — every entry must be reflected in the final output:
<PREVIOUS VERSION>
{prev_version}
</PREVIOUS VERSION>

The INITIAL REVIEW provides case-specific details. You may derive additional enquiries from the claimant's incident account within this section (see TASK Step 3). Do NOT derive new enquiry topics from other parts of INITIAL REVIEW:
<INITIAL REVIEW>
{initial_review}
</INITIAL REVIEW>

The ADDITIONAL INFORMATION includes additional notes on the claim, which can include police reports, engineer reports, incident reports, or other evidence. Do NOT derive new enquiry topics from this section:
<ADDITIONAL INFORMATION>
{additional_info}
</ADDITIONAL INFORMATION>
</CONTEXT>

<OUTPUT>
{format}
</OUTPUT>

<EXAMPLES>
Example 1:
{{
  "enquiry": "Please canvas loss location",
  "enquiry_details": "Please canvas loss location to confirm exactly where accident occurred, the barricade IO hit, any witnesses, CCTV etc, road conditions"
}}
Example 2:
{{
  "enquiry": "Please speak to Towie",
  "enquiry_details": "Please speak to Towie if identified and confirm observations, when contacted for tow, any other details they can provide"
}}
</EXAMPLES>
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
5. **Scope of change**:
   - **If PREVIOUS VERSION has items**: only modify the specific item(s) explicitly referenced in the FEEDBACK. If the FEEDBACK names a specific section, concern, document, or enquiry, apply the change ONLY to that item. All other items MUST remain identical to the PREVIOUS VERSION — do not apply the change elsewhere even if the same value appears in multiple places.
   - **If PREVIOUS VERSION is empty** (no items): the FEEDBACK is your sole source for items. Create new items from scratch, grounded in the FEEDBACK content — use the user's wording as closely as the schema allows; restructure only to fit the required fields. Match the tone of a concise senior-investigator brief: neutral, request-focused, no fraud-language, no source attribution. Rules 2 and 3 (minimum changes, preserve structure) do not apply when there is nothing to preserve.

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
