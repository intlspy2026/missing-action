import re
from collections import defaultdict
from typing import List, Dict, Any, Optional
from agents.external_agent.schemas import (
    KeyConcern, KeyConcernSet,
    DocRequest, DocRequestSet,
    AdditionalEnquiries, AdditionalEnquiriesSet,
    InterviewQuestion, InterviewQuestionSets,
    ExternalAgentPlan,
)


def build_form_info(form_config: Dict) -> List[Dict[str, Any]]:
    brands = form_config["brands"]

    selected_sections = [
        {
            "value": section["value"],
            "label": section["label"]
        }
        for section in form_config["sections"]
    ]

    lobs = [
        {
            "value": group["value"],
            "label": group["label"]
        }
        for group in form_config["lob"]
    ]

    lob_groups_component_data = {
        "label": "What is the investigation scope for this interview plan? You can select more than one",
        "id": "investigation_type",
        "type": "multiselect_combobox",
        "required": True
    }

    lob_groups = [
        {
            "value": group["value"],
            "components": [
                {
                    "data": component.get("data", []),
                    **lob_groups_component_data
                }
                for component in group["components"]
            ]
        }
        for group in form_config["lob"]
    ]

    form_data: List[Dict[str, Any]] = [
        {
            "type": "text",
            "id": "claim_id",
            "label": "What is the claim number for this interview plan?",
            "hint": "Type in the claim number",
            "required": True,
            "pattern": {
                "value": "(?i)^(TSC|H|M)\\d{9}$",
                "message": "Please enter a valid claim number"
            }
        },
        {
            "type": "select",
            "id": "brand",
            "label": "What brand is used for this interview plan?",
            "placeholder": "Choose a Brand",
            "required": True,
            "data": brands,
        },
        {
            "type": "select",
            "id": "lob",
            "label": "What is the line of business?",
            "placeholder": "Choose a Line of business",
            "required": True,
            "data": lobs,
        },
        {
            "type": "lookup",
            "id": "lob_group",
            "metadata": {
                "field_id": "lob"
            },
            "data": lob_groups,
        },
        {
            "type": "textarea",
            "id": "initial_review",
            "label": "What are the initial review notes?",
            "hint": "Please copy and paste your initial review notes",
            "required": True,
        },
        {
            "type": "textarea",
            "id": "additional_info",
            "label": "Additional notes",
            "hint": "Add any additional notes from police reports, engineer reports, etc.",
            "required": False,
        },
        {
            "type": "select",
            "id": "selected_sections",
            "label": "Select Sections",
            "placeholder": "Choose sections to generate",
            "required": True,
            "data": selected_sections,
        },
    ]

    output = [{
        'type': "workflow_stage",
        'data': {
            'name': "Mandatory Info",
            'data': [
                {
                    'type': "smart_form",
                    'confirm_submit': True,
                    'data': form_data
                }
            ]
        }
    }]

    return output


# ------------------------------------
# Per-section form builders
# ------------------------------------

def build_form_key_concerns(key_concerns: KeyConcernSet) -> List[Dict[str, Any]]:
    """Build editable review form for key concerns."""
    components: List[Dict[str, Any]] = []

    for idx, kc in enumerate(key_concerns.concern_set, start=1):
        components.append({
            "type": "textarea",
            "id": f"rationale_{idx}",
            "label": kc.concern,
            "default_value": kc.rationale,
            "required": False,
            "not_applicabel": True,
        })

    view_data: List[Dict[str, Any]] = [
        {"type": "markdown", "data": {"content": "## Key Concerns"}},
        {"type": "markdown", "data": {"content": f"Version: {key_concerns.version}"}},
    ]

    form_data: List[Dict[str, Any]] = [
        {
            "type": "accordion",
            "id": "concern_set",
            "data": [{"value": "Key Concerns", "components": components}],
        }
    ]

    return [{
        "type": "workflow_stage",
        "data": {
            "name": "Key Concerns",
            "data": [
                {"type": "smart_view", "data": view_data},
                {"type": "smart_form", "confirm_submit": True, "data": form_data},
            ],
        },
    }]


def build_form_doc_request(doc_request: DocRequestSet) -> List[Dict[str, Any]]:
    """Build editable review form for document requests."""
    components: List[Dict[str, Any]] = []

    for idx, dr in enumerate(doc_request.document_set, start=1):
        components.append({
            "type": "textarea",
            "id": f"doc_details_{idx}",
            "label": dr.doc_type,
            "default_value": dr.doc_details,
            "required": False,
            "not_applicabel": True,
        })

    view_data: List[Dict[str, Any]] = [
        {"type": "markdown", "data": {"content": "## Document Requests"}},
        {"type": "markdown", "data": {"content": f"Version: {doc_request.version}"}},
    ]

    form_data: List[Dict[str, Any]] = [
        {
            "type": "accordion",
            "id": "document_set",
            "data": [{"value": "Document Requests", "components": components}],
        }
    ]

    return [{
        "type": "workflow_stage",
        "data": {
            "name": "Document Requests",
            "data": [
                {"type": "smart_view", "data": view_data},
                {"type": "smart_form", "confirm_submit": True, "data": form_data},
            ],
        },
    }]


def build_form_enquiries(enquiries: AdditionalEnquiriesSet) -> List[Dict[str, Any]]:
    """Build editable review form for additional enquiries."""
    components: List[Dict[str, Any]] = []

    for idx, eq in enumerate(enquiries.enquiries_set, start=1):
        # components.append({
        #     "type": "text",
        #     "id": f"enquiry_{idx}",
        #     "label": f"Enquiry {idx}",
        #     "default_value": eq.enquiry,
        #     "required": False,
        # })
        components.append({
            "type": "textarea",
            "id": f"enquiry_detail_{idx}",
            "label": eq.enquiry,
            "default_value": eq.enquiry_detail,
            "required": False,
            "not_applicabel": True
        })

    view_data: List[Dict[str, Any]] = [
        {"type": "markdown", "data": {"content": "## Additional Enquiries"}},
        {"type": "markdown", "data": {"content": f"Version: {enquiries.version}"}},
    ]

    form_data: List[Dict[str, Any]] = [
        {
            "type": "accordion",
            "id": "enquiries_set",
            "data": [{"value": "Additional Enquiries", "components": components}],
        }
    ]

    return [{
        "type": "workflow_stage",
        "data": {
            "name": "Additional Enquiries",
            "data": [
                {"type": "smart_view", "data": view_data},
                {"type": "smart_form", "confirm_submit": True, "data": form_data},
            ],
        },
    }]


def build_form_interview_plan(interview_plan: InterviewQuestionSets) -> List[Dict[str, Any]]:
    """Build editable review form for interview plan, grouped by category."""
    grouped: Dict[str, List[InterviewQuestion]] = defaultdict(list)
    category_order: List[str] = []

    for q in interview_plan.question_sets or []:
        cat = (q.category or "").strip() or "Other"
        if cat not in grouped:
            category_order.append(cat)
        grouped[cat].append(q)

    accordion_sections: List[Dict[str, Any]] = []
    for cat in category_order:
        components: List[Dict[str, Any]] = []
        for q in grouped[cat]:
            components.append({
                "type": "text",
                "id": f"q_{q.question_id}",
                "label": f"Question {q.question_id}",
                "default_value": q.question_text or "",
                "required": False,
            })
        accordion_sections.append({"value": cat, "components": components})

    view_data: List[Dict[str, Any]] = [
        {"type": "markdown", "data": {"content": "## Interview Plan"}},
        {"type": "markdown", "data": {"content": f"Version: {interview_plan.version}"}},
    ]

    form_data: List[Dict[str, Any]] = [
        {
            "type": "accordion",
            "id": "question_sets",
            "data": accordion_sections,
        }
    ]

    return [{
        "type": "workflow_stage",
        "data": {
            "name": "Interview Plan",
            "data": [
                {"type": "smart_view", "data": view_data},
                {"type": "smart_form", "confirm_submit": True, "data": form_data},
            ],
        },
    }]


# ------------------------------------
# Per-section parsers
# ------------------------------------

def parse_form_to_key_concerns(
    form_payload: Dict[str, Any],
    *,
    previous: Optional[KeyConcernSet] = None,
) -> KeyConcernSet:
    """Parse flat form payload back into KeyConcernSet.

    Only rationale_{N} is in the payload (concern is the display label, not editable).
    Concern is recovered from `previous` by 1-based position.
    """
    rationales: Dict[int, str] = {}
    for k, v in (form_payload or {}).items():
        m = re.fullmatch(r"rationale_(\d+)", str(k))
        if m:
            rationales[int(m.group(1))] = (v or "").strip()

    prev_items = list(
        previous.concern_set) if previous and previous.concern_set else []
    items: List[KeyConcern] = []

    for idx in sorted(rationales):
        if idx - 1 >= len(prev_items):
            continue
        concern_text = prev_items[idx - 1].concern
        rationale_text = rationales[idx]
        if concern_text:
            items.append(KeyConcern(concern=concern_text,
                         rationale=rationale_text))

    return KeyConcernSet(
        concern_set=items,
        version=(previous.version if previous else 0) + 1,
        update_notes=None,
    )


def parse_form_to_doc_request(
    form_payload: Dict[str, Any],
    *,
    previous: Optional[DocRequestSet] = None,
) -> DocRequestSet:
    """Parse flat form payload back into DocRequestSet.

    Only doc_details_{N} is in the payload (doc_type is the display label, not editable).
    doc_type is recovered from `previous` by 1-based position.
    """
    doc_details: Dict[int, str] = {}
    for k, v in (form_payload or {}).items():
        m = re.fullmatch(r"doc_details_(\d+)", str(k))
        if m:
            doc_details[int(m.group(1))] = (v or "").strip()

    prev_items = list(
        previous.document_set) if previous and previous.document_set else []
    items: List[DocRequest] = []

    for idx in sorted(doc_details):
        if idx - 1 >= len(prev_items):
            continue
        doc_type_text = prev_items[idx - 1].doc_type
        doc_details_text = doc_details[idx]
        if doc_type_text:
            items.append(DocRequest(doc_type=doc_type_text,
                         doc_details=doc_details_text))

    return DocRequestSet(
        document_set=items,
        version=(previous.version if previous else 0) + 1,
        update_notes=None,
    )


def parse_form_to_enquiries(
    form_payload: Dict[str, Any],
    *,
    previous: Optional[AdditionalEnquiriesSet] = None,
) -> AdditionalEnquiriesSet:
    """Parse flat form payload back into AdditionalEnquiriesSet.

    Only enquiry_detail_{N} is in the payload (enquiry is the display label, not editable).
    enquiry is recovered from `previous` by 1-based position.
    """
    enquiry_details: Dict[int, str] = {}
    for k, v in (form_payload or {}).items():
        m = re.fullmatch(r"enquiry_detail_(\d+)", str(k))
        if m:
            enquiry_details[int(m.group(1))] = (v or "").strip()

    prev_items = list(
        previous.enquiries_set) if previous and previous.enquiries_set else []
    items: List[AdditionalEnquiries] = []

    for idx in sorted(enquiry_details):
        if idx - 1 >= len(prev_items):
            continue
        enquiry_text = prev_items[idx - 1].enquiry
        detail_text = enquiry_details[idx]
        if enquiry_text:
            items.append(AdditionalEnquiries(
                enquiry=enquiry_text, enquiry_detail=detail_text))

    return AdditionalEnquiriesSet(
        enquiries_set=items,
        version=(previous.version if previous else 0) + 1,
        update_notes=None,
    )


def parse_form_to_interview_plan(
    form_payload: Dict[str, Any],
    *,
    previous: Optional[InterviewQuestionSets] = None,
) -> InterviewQuestionSets:
    """Parse flat form payload back into InterviewQuestionSets."""
    prev_by_id: Dict[int, InterviewQuestion] = {}
    if previous and previous.question_sets:
        for q in previous.question_sets:
            prev_by_id[q.question_id] = q

    items: List[tuple[int, str]] = []
    for k, v in (form_payload or {}).items():
        m = re.fullmatch(r"q_(\d+)", str(k))
        if not m:
            continue
        original_id = int(m.group(1))
        text = (v or "").strip()
        if text:
            items.append((original_id, text))

    items.sort(key=lambda x: x[0])

    questions: List[InterviewQuestion] = []
    for new_id, (original_id, text) in enumerate(items, start=1):
        prev_q = prev_by_id.get(original_id)
        category = prev_q.category if prev_q else "Other"
        questions.append(InterviewQuestion(
            question_id=new_id,
            category=category,
            question_text=text,
        ))

    return InterviewQuestionSets(
        question_sets=questions,
        version=(previous.version if previous else 0) + 1,
        update_notes=None,
    )


# ------------------------------------
# Final output form
# ------------------------------------

def build_form_final(claim_id: str, external_agent_plan: ExternalAgentPlan, selected_sections: List[str]) -> List[Dict[str, Any]]:
    """Build read-only final output view for the assembled external agent plan.

    selected_sections controls which optional sections are rendered.
    Key concerns is always included (it is always generated regardless of selected_sections).
    """

    view_data: List[Dict[str, Any]] = [
        {"type": "markdown", "data": {"content": "## Final External Agent Plan"}},
        {"type": "markdown", "data": {
            "content": f"Claim ID: {claim_id}  \nVersion: {external_agent_plan.version}  \nCreated: {external_agent_plan.created_at}"
        }},
    ]

    # Key Concerns — always rendered
    view_data.append({"type": "markdown", "data": {"content": "### Key Concerns"}})
    concerns = external_agent_plan.concern_set.concern_set or []
    if concerns:
        for kc in concerns:
            view_data.append({"type": "markdown", "data": {"content": kc.concern or ""}})
            view_data.append({"type": "markdown", "data": {"content": kc.rationale or ""}})
    else:
        view_data.append({"type": "markdown", "data": {"content": "_No key concerns._"}})

    if "doc_request" in selected_sections:
        view_data.append({"type": "markdown", "data": {"content": "### Document Requests"}})
        docs = external_agent_plan.document_set.document_set or []
        if docs:
            for dr in docs:
                view_data.append({"type": "markdown", "data": {"content": dr.doc_type or ""}})
                view_data.append({"type": "markdown", "data": {"content": dr.doc_details or ""}})
        else:
            view_data.append({"type": "markdown", "data": {"content": "_No document requests._"}})

    if "additional_enquiries" in selected_sections:
        view_data.append({"type": "markdown", "data": {"content": "### Additional Enquiries"}})
        enquiries = external_agent_plan.enquiry_set.enquiries_set or []
        if enquiries:
            for eq in enquiries:
                view_data.append({"type": "markdown", "data": {"content": eq.enquiry or ""}})
                view_data.append({"type": "markdown", "data": {"content": eq.enquiry_detail or ""}})
        else:
            view_data.append({"type": "markdown", "data": {"content": "_No additional enquiries._"}})

    return [{
        "type": "workflow_stage",
        "data": {
            "name": "Final External Agent Plan",
            "data": [
                {"type": "smart_view", "data": view_data},
                {"type": "smart_form", "confirm_submit": False, "data": []},
            ],
        },
    }]
