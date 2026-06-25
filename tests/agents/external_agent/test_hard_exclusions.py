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


class TestCCTVFootageExclusion:
    """CCTV footage should be stripped unless the case mentions cameras/CCTV/footage/surveillance/video."""

    def test_cctv_stripped_when_no_hook(self):
        result = strip_hard_exclusions(
            {"document_set": [
                {"doc_type": "CCTV Footage", "doc_details": ""},
                {"doc_type": "Telephone Records", "doc_details": ""},
            ]},
            initial_review="Single vehicle accident, kangaroo swerve, hit a tree. Insured swerved and lost control.",
            additional_info="",
            investigation_types=["Reckless"],
        )
        doc_types = {d["doc_type"] for d in result["document_set"]}
        assert "CCTV Footage" not in doc_types

    @pytest.mark.parametrize("hook", [
        "CCTV footage of the incident",
        "cameras at the servo",
        "the insured reviewed the footage",
        "surveillance at the location",
        "video recording of the crash",
    ])
    def test_cctv_kept_when_hook_present(self, hook):
        docs = {"document_set": [{"doc_type": "CCTV Footage", "doc_details": ""}]}
        result = strip_hard_exclusions(
            docs,
            initial_review=f"Motor accident. {hook}",
            additional_info="",
            investigation_types=["Reckless"],
        )
        doc_types = {d["doc_type"] for d in result["document_set"]}
        assert "CCTV Footage" in doc_types


class TestMotorSportRacetrackExclusion:
    """Motor Sport/Racetrack Evidence should be stripped unless the case mentions actual motor-sport participation, not just the investigation-type label."""

    def test_motor_sport_stripped_when_only_label(self):
        result = strip_hard_exclusions(
            {"document_set": [
                {"doc_type": "Motor Sport/Racetrack Evidence", "doc_details": ""},
            ]},
            initial_review="Single vehicle accident, kangaroo swerve, hit a tree.",
            additional_info="",
            investigation_types=["Reckless", "Motor Sports"],
        )
        doc_types = {d["doc_type"] for d in result["document_set"]}
        assert "Motor Sport/Racetrack Evidence" not in doc_types

    @pytest.mark.parametrize("hook", [
        "insured participated in a track day at Queensland Raceway",
        "CAMS logbook located",
        "drag racing on the street",
        "racetrack event last weekend",
        "motorsport registration paperwork",
        "racing circuit event",
    ])
    def test_motor_sport_kept_when_hook_present(self, hook):
        docs = {"document_set": [{"doc_type": "Motor Sport/Racetrack Evidence", "doc_details": ""}]}
        result = strip_hard_exclusions(
            docs,
            initial_review=f"Motor accident. {hook}",
            additional_info="",
            investigation_types=["Reckless"],
        )
        doc_types = {d["doc_type"] for d in result["document_set"]}
        assert "Motor Sport/Racetrack Evidence" in doc_types


class TestPoliceCorrespondenceNotStripped:
    """A police doc_type containing the substring 'correspondence' must NOT be
    stripped by the correspondence/email hard exclusion. Police inclusion is
    governed by the LLM's attendance-status rule (RULE 3 item 15), not the
    deterministic pre-filter, so the doc must always reach the LLM.
    """

    POLICE_CORRESPONDENCE_DOC = (
        "A copy of all correspondence from the Police including but not limited .."
    )

    def test_police_correspondence_not_stripped_on_nil_case(self):
        # Mt Ommaney "no record" = confirmed nil. The doc must still reach the
        # LLM (which will EXCLUDE via item 15's confirmed-nil branch); the
        # pre-filter must not strip it via the correspondence rule.
        result = strip_hard_exclusions(
            {"document_set": [
                {"doc_type": self.POLICE_CORRESPONDENCE_DOC, "doc_details": ""},
            ]},
            initial_review=(
                "Called Mt Ommaney police station. Adv no record or incidents reported. "
                "Adv to try and call Dayboro police station. Called Dayboro station, no answer. "
                "Police/Citec: Nil results."
            ),
            additional_info="",
            investigation_types=["Reckless"],
        )
        doc_types = {d["doc_type"] for d in result["document_set"]}
        assert self.POLICE_CORRESPONDENCE_DOC in doc_types

    def test_police_correspondence_not_stripped_on_attended_case(self):
        # Police actually attended and a report was issued. The pre-filter must
        # not strip this doc — without the police guard, the 'correspondence'
        # substring would classify it under correspondence and strip it on the
        # no-email-hook case, wrongly removing a legitimate police-attendance doc.
        result = strip_hard_exclusions(
            {"document_set": [
                {"doc_type": self.POLICE_CORRESPONDENCE_DOC, "doc_details": ""},
            ]},
            initial_review=(
                "Police attended the incident. Police report number SAP12345678 issued. "
                "Charges laid against the insured."
            ),
            additional_info="",
            investigation_types=["Reckless"],
        )
        doc_types = {d["doc_type"] for d in result["document_set"]}
        assert self.POLICE_CORRESPONDENCE_DOC in doc_types

    def test_police_correspondence_not_stripped_on_zero_police_mention(self):
        # No mention of police at all. Still must reach the LLM (item 15's
        # not-mentioned branch will EXCLUDE). The pre-filter's job is not to
        # decide police relevance.
        result = strip_hard_exclusions(
            {"document_set": [
                {"doc_type": self.POLICE_CORRESPONDENCE_DOC, "doc_details": ""},
            ]},
            initial_review="Single vehicle accident, kangaroo swerve, hit a tree.",
            additional_info="",
            investigation_types=["Reckless"],
        )
        doc_types = {d["doc_type"] for d in result["document_set"]}
        assert self.POLICE_CORRESPONDENCE_DOC in doc_types
