"""
Regression tests for document-request prompt guardrails.

These tests do not call an LLM; they verify that the prompt text itself
contains the hard-exclusion and narrative-derivation rules added for the
Policy Exclusion | insufficient evidence of ownership tenant-damage case.
"""

import json

import pytest

from agents.external_agent.prompt_manager.external_agent_prompts import (
    DOC_REQUEST_RELEVANCE_PROMPT,
    NARRATIVE_DOC_REQUEST_DRAFT_PROMPT,
)


# Full case text from the Policy Exclusion | insufficient evidence feedback case.
POLICY_EXCLUSION_CASE_INITIAL_REVIEW = """
Initial Review

Triage Decision TRIAGE REVIEW - retain
MD
The property was broken into on 14th Friday, there is a broken window and the screen door was stolen and
the entire houses metal piping was stolen.
The home was tenanted with the tenants moving out the day before, my friends visited Saturday morning
and they discovered the event.

* Policy inception: 28.08.2023
* DOL: 15.06.2024
* Lodgement: 16.06.2024
* No prior claims
* No recent changes to level of coverage but did make contact with policies a few mins prior to lodgement of claim
* Policy premiums are paid annually in order.
* Police reporting supplied - yes SAP12345678
* Forced entry: yes, broken window and screen door stolen
Concerns        CONCERNS
-policy exclusion concerns
-the policy doesn't have Tenant Protection and the insd is alleging all this damage was found the day after
the tenants moved out
-if tenants were moving out on 14.06 and the insd found the damage on 15.06 who had the chance to do the
damages being claimed?
-concerns that this is actually tenant damage and the policy doesn't provide cover for this so has been lodged as stranger MD

Insured's Name  John Smith
Date of Birth   18 March1963 (provided by insured over phone call)
Phone Number(s) 412345678
Mailing Address 1 Road, Brisbane, QLD 4000
Email Address   John.smith@email.com

Date of Loss     15/06/2024 11:00
Notice Date      16/06/2024 17:56
Loss Location    John.smith@email.com
Loss Description      The property was broken into on 14th Friday, there is a broken window and the screen door was stolen and the entire houses metal piping was stolen. The home was tenanted with the tenants moving out the day
before, my friends visited Saturday morning and they discovered the event. They have also disturbed the asbestos of the property,

Brand  AAMI
Inception Date & Time  28/08/2023 at 12:00AM
Product AAMI Landlord Insurance - Building
PDS    PDS A01460 15/12/20 A
System Searches
Protect

Saved to PTF    - No previous insurer

* Policy taken out online
* Policy incepted 28 August 2023
* Nil payment lapses
Customer Workbench

Saved to PTF    - No policies held under insured's name

* Current and only policy held under company name
* No previous claims
Claims Centre (Previous Claims)
* No previous claims
Claims Centre (Current Claim)
* No documents provided by insured


* CM assigned Business Pty Ltd for builder's assessment report - IRO to follow-up with findings
* SAPOL police report number provided SAP12345678 - IRO to follow-up with findings
Google Search

Saved to PTF
```
Risk Address:
```

* Shows property listed on real estate sites
* Information shown on property.com.au show the property was sold 08 September 2023, with the property listed for rent on 04 February 2024. Property was then leased on 20 February 2024.
* 20 February to current date only spans 4 months which is generally not long enough for a lease - this will need to be discussed with the insured
Insured:
* No results, nil concerns
Company:
* Details shown on ABN lookup/creditor sites - nil concerns
Social Media
* Unable to locate
ThirdEye
* No images uploaded by the insured
Verint


Saved to PTF
Lodgement call - 16/06/2024:

* Insured advised property was damaged on the Friday night (14 June). Insured advised they lodged a report with the police. Insured advised they're not sure if the property was broken into as the window was open. Insured advised all
of the metal piping was taken from the property.
* Insured advised that the tenants were moving out on the day before the event.
* Insured also advised there was damaged to the bathroom
* Insured advised friends went to visit the property on the Saturday morning
* Insured advised they lodged police report straight away
* Insured advised that the asbestos has been disturbed
* Claims advised of $3000xs and assessor visiting the property
Insured called policy team (23 minutes prior to claim lodgement)
* Insured enquiring why they cannot add things to their online account
* Claims advised that the online system identifies the company name - call then cut out
FileNet

Unable to download due to network issue - Confirms policy, nil concerns
IDA
- Nil results
RP Data

Saved to PTF       - Property owned by insured

* Sold/Settlement Date - 08 September 2023
* Property looks to be dated in photos taken June 2023.
* States owner occupied - to be discuss with insured as property should be listed as rented
Caspar

Saved to PTF       - Insured:

* Search returned, nil concerns
* Company:
* Investment trust and company name located
* ABN active for investment trust
CITEC
Saved to PTF
- Company search conducted - company ABN is currently active
* ASIC & Business Names Banned & Disqualified Register Search negative
Bureau of Meteorology    - Claim not linked to weather event
* ROI booked with insured 24/06 at 14:00
"""

# Methodology doc set for the investigation type in the failing case.
POLICY_EXCLUSION_METHODLOGY = json.dumps([
    {
        "investigation_type": "Policy Exclusion | insufficient evidence of ownership",
        "doc_list": {
            "document_set": [
                {"doc_type": "Schedule of Loss (if not already filled out).", "doc_details": ""},
                {"doc_type": "Evidence of ownership for all items listed on the Schedule of Loss.", "doc_details": ""},
                {"doc_type": "If mobile phone: A copy of the IDs, serial numbers, IMEI numbers.", "doc_details": ""},
                {"doc_type": "A copy of pre-incident photographs.", "doc_details": ""},
                {"doc_type": "A copy of the receipt of purchase.", "doc_details": ""},
                {"doc_type": "Contact information for any witnesses to the event.", "doc_details": ""},
                {"doc_type": "Copies of any correspondence (emails or text messages) confirming the events date and time.", "doc_details": ""},
                {"doc_type": "Phone records from around the time of the event and policy inception.", "doc_details": ""},
                {"doc_type": "Credit card and EFTPOS records that can verify insured's movements, evidence of financial motive around the time of loss (3-month period if concerns of fraud", "doc_details": ""},
                {"doc_type": "Police report", "doc_details": ""},
            ]
        }
    }
])


class TestDocRequestRelevancePromptGuardrails:
    """Verify the relevance-filter prompt contains the expected guardrails."""

    def test_mobile_phone_hard_exclusion_present(self):
        assert "Mobile Phone Related Documents (IDs, serial numbers, IMEI numbers)" in DOC_REQUEST_RELEVANCE_PROMPT
        assert "Exclude when no mobile device is mentioned" in DOC_REQUEST_RELEVANCE_PROMPT

    def test_phone_records_split_and_triggered(self):
        # Phone records are split out from bank/financial records.
        assert "12. Phone records and telephone records:" in DOC_REQUEST_RELEVANCE_PROMPT
        assert "13. Bank statements and financial records:" in DOC_REQUEST_RELEVANCE_PROMPT
        # Explicit tenant / third-party trigger is present.
        assert "the narrative mentions tenants, tenancy, lease, move-in, move-out, property managers, friends, neighbours, or other third parties" in DOC_REQUEST_RELEVANCE_PROMPT

    def test_bank_financial_records_narrower_gate(self):
        bank_section = DOC_REQUEST_RELEVANCE_PROMPT.split("13. Bank statements and financial records:")[1]
        phone_section = DOC_REQUEST_RELEVANCE_PROMPT.split("12. Phone records and telephone records:")[1].split("13. Bank statements and financial records:")[0]
        # Bank/financial records do NOT get the tenant/third-party trigger.
        assert "tenants, tenancy, lease" not in bank_section
        # Phone records DO get the tenant/third-party trigger.
        assert "tenants, tenancy, lease" in phone_section
        # Bank/financial records are now gated by fraud/financial motive only.
        assert "fraud or financial motive" in bank_section
        assert "inconsistent or in question" not in bank_section

    def test_receipt_of_purchase_fixture_exclusion_present(self):
        assert "Standalone receipt of purchase / original purchase receipt" in DOC_REQUEST_RELEVANCE_PROMPT
        assert "Exclude when the claimed items are building fixtures" in DOC_REQUEST_RELEVANCE_PROMPT
        assert "metal piping" in DOC_REQUEST_RELEVANCE_PROMPT

    def test_sub_item_dedup_strengthened(self):
        assert "This applies regardless of whether the standalone receipt entry claims to cover different items" in DOC_REQUEST_RELEVANCE_PROMPT


class TestNarrativeDocRequestPromptGuardrails:
    """Verify the narrative-derivation prompt contains the tenancy rule."""

    def test_tenancy_transition_rule_present(self):
        assert "Tenancy Transition Rule" in NARRATIVE_DOC_REQUEST_DRAFT_PROMPT
        assert "entry/exit condition report or tenant inspection report" in NARRATIVE_DOC_REQUEST_DRAFT_PROMPT

    def test_tenancy_transition_derivation_source_present(self):
        assert "Tenancy transition" in NARRATIVE_DOC_REQUEST_DRAFT_PROMPT
        assert "derive the entry/exit condition report for the tenancy" in NARRATIVE_DOC_REQUEST_DRAFT_PROMPT


class TestRelevanceFilterPromptFormat:
    """Smoke-test that the relevance prompt formats correctly with the case fixture."""

    def test_prompt_formats_without_error(self):
        prompt = DOC_REQUEST_RELEVANCE_PROMPT.format(
            initial_review=POLICY_EXCLUSION_CASE_INITIAL_REVIEW,
            additional_info="",
            knowledge=POLICY_EXCLUSION_METHODLOGY,
            investigation_type="Policy Exclusion | insufficient evidence of ownership",
            format='{"document_set": [{"doc_type": "string", "doc_details": "string"}]}',
        )
        # Basic sanity checks that the formatted prompt contains the case and methodology.
        assert "John Smith" in prompt
        assert "metal piping" in prompt
        assert "Mobile Phone Related Documents" in prompt
