"""
Unit tests for the deterministic hard-exclusion pre-filter.
"""

import pytest

from agents.external_agent.hard_exclusions import strip_hard_exclusions


# Methodology doc set for Policy Exclusion | insufficient evidence of ownership.
POLICY_EXCLUSION_DOCS = {
    "document_set": [
        {"doc_type": "Schedule of loss (if not already filled out).", "doc_details": ""},
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

# Case text from the failing Policy Exclusion claim.
POLICY_EXCLUSION_CASE = """
The property was broken into on 14th Friday, there is a broken window and the screen door was stolen and
the entire houses metal piping was stolen.
The home was tenanted with the tenants moving out the day before, my friends visited Saturday morning
and they discovered the event.

Concerns CONCERNS
-policy exclusion concerns
-the policy doesn't have Tenant Protection and the insd is alleging all this damage was found the day after
the tenants moved out
-if tenants were moving out on 14.06 and the insd found the damage on 15.06 who had the chance to do the
damages being claimed?
-concerns that this is actually tenant damage and the policy doesn't provide cover for this so has been lodged as stranger MD

Insured's Name  John Smith
"""


class TestEmailTextCorrespondenceExclusion:
    """Email/text correspondence should be stripped unless the case mentions it."""

    def test_correspondence_stripped_when_no_hook(self):
        result = strip_hard_exclusions(
            {"document_set": list(POLICY_EXCLUSION_DOCS["document_set"])},
            initial_review=POLICY_EXCLUSION_CASE,
            additional_info="",
            investigation_types=["Policy Exclusion | insufficient evidence of ownership"],
        )
        doc_types = {d["doc_type"] for d in result["document_set"]}
        assert "Copies of any correspondence (emails or text messages) confirming the events date and time." not in doc_types

    @pytest.mark.parametrize("hook", [
        "the insured sent an email confirming the event",
        "text messages between the tenant and insured",
        "SMS records show the time of discovery",
        "correspondence with the property manager",
        "instant messages sent on the day",
    ])
    def test_correspondence_kept_when_hook_present(self, hook):
        docs = {
            "document_set": [
                {"doc_type": "Copies of any correspondence (emails or text messages) confirming the events date and time.", "doc_details": ""},
            ]
        }
        result = strip_hard_exclusions(
            docs,
            initial_review=f"Property damage. {hook}",
            additional_info="",
            investigation_types=["Policy Exclusion | insufficient evidence of ownership"],
        )
        doc_types = {d["doc_type"] for d in result["document_set"]}
        assert "Copies of any correspondence (emails or text messages) confirming the events date and time." in doc_types


class TestCoreItemsNotStripped:
    """Items with no hard-exclusion pattern should pass through."""

    def test_phone_records_not_stripped(self):
        result = strip_hard_exclusions(
            {"document_set": list(POLICY_EXCLUSION_DOCS["document_set"])},
            initial_review=POLICY_EXCLUSION_CASE,
            additional_info="",
            investigation_types=["Policy Exclusion | insufficient evidence of ownership"],
        )
        doc_types = {d["doc_type"] for d in result["document_set"]}
        assert "Phone records from around the time of the event and policy inception." in doc_types

    def test_police_report_not_stripped(self):
        result = strip_hard_exclusions(
            {"document_set": list(POLICY_EXCLUSION_DOCS["document_set"])},
            initial_review=POLICY_EXCLUSION_CASE,
            additional_info="",
            investigation_types=["Policy Exclusion | insufficient evidence of ownership"],
        )
        doc_types = {d["doc_type"] for d in result["document_set"]}
        assert "Police report" in doc_types
