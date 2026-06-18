"""
Unit tests for external agent form builders and parsers.
"""

import pytest

from agents.external_agent.schemas import (
    KeyConcern,
    KeyConcernSet,
    DocRequest,
    DocRequestSet,
    AdditionalEnquiries,
    AdditionalEnquiriesSet,
)
from agents.external_agent.utils import (
    build_form_key_concerns,
    build_form_enquiries,
    parse_form_to_key_concerns,
    parse_form_to_enquiries,
    parse_form_to_doc_request,
)


class TestBuildFormKeyConcerns:
    def test_emits_info_component_per_concern(self):
        key_concerns = KeyConcernSet(
            concern_set=[
                KeyConcern(concern="Conflicting statements", rationale="Two versions given."),
                KeyConcern(concern="Delayed reporting", rationale="Reported 3 days later."),
            ]
        )

        artifact = build_form_key_concerns(key_concerns)
        form = artifact[0]["data"]["data"][0]
        components = form["data"]

        assert form["type"] == "smart_form"
        assert len(components) == 2

        assert components[0]["type"] == "info"
        assert components[0]["id"] == "rationale_1"
        assert components[0]["label"] == "1. Conflicting statements"
        assert components[0]["description"] == "Two versions given."
        assert "default_value" not in components[0]
        assert "required" not in components[0]
        assert "not_applicable" not in components[0]

        assert components[1]["type"] == "info"
        assert components[1]["id"] == "rationale_2"
        assert components[1]["label"] == "2. Delayed reporting"
        assert components[1]["description"] == "Reported 3 days later."


class TestBuildFormEnquiries:
    def test_emits_info_component_per_enquiry(self):
        enquiries = AdditionalEnquiriesSet(
            enquiries_set=[
                AdditionalEnquiries(
                    enquiry="Verify phone usage", enquiry_detail="Check call logs around DOL."
                ),
                AdditionalEnquiries(
                    enquiry="Confirm employment", enquiry_detail="Contact employer directly."
                ),
            ]
        )

        artifact = build_form_enquiries(enquiries)
        form = artifact[0]["data"]["data"][0]
        components = form["data"]

        assert form["type"] == "smart_form"
        assert len(components) == 2

        assert components[0]["type"] == "info"
        assert components[0]["id"] == "enquiry_detail_1"
        assert components[0]["label"] == "1. Verify phone usage"
        assert components[0]["description"] == "Check call logs around DOL."
        assert "default_value" not in components[0]
        assert "required" not in components[0]
        assert "not_applicable" not in components[0]

        assert components[1]["type"] == "info"
        assert components[1]["id"] == "enquiry_detail_2"
        assert components[1]["label"] == "2. Confirm employment"
        assert components[1]["description"] == "Contact employer directly."


class TestParseFormToKeyConcerns:
    def test_keeps_present_items_and_uses_payload_value(self):
        previous = KeyConcernSet(
            concern_set=[
                KeyConcern(concern="Conflicting statements", rationale="Two versions given."),
                KeyConcern(concern="Delayed reporting", rationale="Reported 3 days later."),
            ]
        )
        payload = {
            "rationale_1": "Edited rationale.",
            "rationale_2": "Reported 3 days later.",
        }

        result = parse_form_to_key_concerns(payload, previous=previous)

        assert len(result.concern_set) == 2
        assert result.concern_set[0].concern == "Conflicting statements"
        assert result.concern_set[0].rationale == "Edited rationale."
        assert result.concern_set[1].concern == "Delayed reporting"
        assert result.concern_set[1].rationale == "Reported 3 days later."
        assert result.version == previous.version + 1

    def test_drops_items_missing_from_payload(self):
        previous = KeyConcernSet(
            concern_set=[
                KeyConcern(concern="Conflicting statements", rationale="Two versions given."),
                KeyConcern(concern="Delayed reporting", rationale="Reported 3 days later."),
            ]
        )
        payload = {"rationale_2": "Reported 3 days later."}

        result = parse_form_to_key_concerns(payload, previous=previous)

        assert len(result.concern_set) == 1
        assert result.concern_set[0].concern == "Delayed reporting"


class TestParseFormToEnquiries:
    def test_keeps_present_items_and_uses_payload_value(self):
        previous = AdditionalEnquiriesSet(
            enquiries_set=[
                AdditionalEnquiries(
                    enquiry="Verify phone usage", enquiry_detail="Check call logs around DOL."
                ),
                AdditionalEnquiries(
                    enquiry="Confirm employment", enquiry_detail="Contact employer directly."
                ),
            ]
        )
        payload = {
            "enquiry_detail_1": "Check all calls on the day.",
            "enquiry_detail_2": "Contact employer directly.",
        }

        result = parse_form_to_enquiries(payload, previous=previous)

        assert len(result.enquiries_set) == 2
        assert result.enquiries_set[0].enquiry == "Verify phone usage"
        assert result.enquiries_set[0].enquiry_detail == "Check all calls on the day."
        assert result.enquiries_set[1].enquiry == "Confirm employment"
        assert result.enquiries_set[1].enquiry_detail == "Contact employer directly."
        assert result.version == previous.version + 1

    def test_drops_items_missing_from_payload(self):
        previous = AdditionalEnquiriesSet(
            enquiries_set=[
                AdditionalEnquiries(
                    enquiry="Verify phone usage", enquiry_detail="Check call logs around DOL."
                ),
                AdditionalEnquiries(
                    enquiry="Confirm employment", enquiry_detail="Contact employer directly."
                ),
            ]
        )
        payload = {"enquiry_detail_2": "Contact employer directly."}

        result = parse_form_to_enquiries(payload, previous=previous)

        assert len(result.enquiries_set) == 1
        assert result.enquiries_set[0].enquiry == "Confirm employment"


class TestParseFormToDocRequest:
    def _doc_request(self, **overrides) -> DocRequestSet:
        defaults = {
            "doc_type": "Telephone Records",
            "doc_details": "John Smith's telephone records.",
            "assigned_parties": None,
            "doc_details_original": "your telephone records.",
        }
        defaults.update(overrides)
        return DocRequestSet(
            document_set=[DocRequest(**defaults)],
            version=1,
        )

    def test_keeps_payload_chips_and_preserves_original(self):
        previous = self._doc_request(
            doc_details="your telephone records.",
            doc_details_original="your telephone records.",
        )
        payload = {"doc_1_chips": ["insured"]}

        result = parse_form_to_doc_request(payload, previous=previous)

        doc = result.document_set[0]
        assert doc.assigned_parties == ["insured"]
        assert doc.doc_details == "your telephone records."
        assert doc.doc_details_original == "your telephone records."
        assert result.version == previous.version + 1

    def test_empty_array_reverts_doc_details_to_original(self):
        previous = self._doc_request(
            doc_details="John Smith's telephone records.",
            assigned_parties=["insured"],
            doc_details_original="your telephone records.",
        )
        payload = {"doc_1_chips": []}

        result = parse_form_to_doc_request(payload, previous=previous)

        doc = result.document_set[0]
        assert doc.assigned_parties is None
        assert doc.doc_details == "your telephone records."
        assert doc.doc_details_original == "your telephone records."

    def test_missing_key_reverts_doc_details_to_original(self):
        previous = self._doc_request(
            doc_details="John Smith's telephone records.",
            assigned_parties=["insured"],
            doc_details_original="your telephone records.",
        )
        # FE omits doc_1_chips when all chips are unselected.
        payload = {}

        result = parse_form_to_doc_request(payload, previous=previous)

        doc = result.document_set[0]
        assert doc.assigned_parties is None
        assert doc.doc_details == "your telephone records."
        assert doc.doc_details_original == "your telephone records."

    def test_no_chip_keys_at_all_reverts_to_original(self):
        previous = self._doc_request(
            doc_details="John Smith's telephone records.",
            assigned_parties=["insured"],
            doc_details_original="your telephone records.",
        )
        payload = {}

        result = parse_form_to_doc_request(payload, previous=previous)

        doc = result.document_set[0]
        assert doc.assigned_parties is None
        assert doc.doc_details == "your telephone records."

    def test_mixed_docs_some_with_chips_some_without(self):
        previous = DocRequestSet(
            document_set=[
                DocRequest(
                    doc_type="Telephone Records",
                    doc_details="John Smith's telephone records.",
                    assigned_parties=["insured"],
                    doc_details_original="your telephone records.",
                ),
                DocRequest(
                    doc_type="Bank Statements",
                    doc_details="Jane Doe's bank statements.",
                    assigned_parties=["driver"],
                    doc_details_original="your bank statements.",
                ),
            ],
            version=1,
        )
        payload = {"doc_2_chips": ["insured"]}

        result = parse_form_to_doc_request(payload, previous=previous)

        assert len(result.document_set) == 2
        telephone, bank = result.document_set

        # Missing key means unselected.
        assert telephone.assigned_parties is None
        assert telephone.doc_details == "your telephone records."

        # Present key means use payload.
        assert bank.assigned_parties == ["insured"]
        assert bank.doc_details == "Jane Doe's bank statements."
