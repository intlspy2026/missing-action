import re
import logging
from collections import defaultdict
from typing import List, Dict, Any, Optional
from agents.external_agent.schemas import (
    KeyConcern, KeyConcernSet,
    DocRequest, DocRequestSet,
    AdditionalEnquiries, AdditionalEnquiriesSet,
    InterviewQuestion, InterviewQuestionSets,
    ExternalAgentPlan,
)

logger = logging.getLogger(__name__)

# Matches placeholder tokens like <INSERT DATE>, <INSERT PARTY>, etc.
_PLACEHOLDER_RE = re.compile(r"<INSERT\s+[A-Z\s]+>")


def _escape_placeholders(text: str) -> str:
    """Escape angle brackets inside <INSERT ...> tokens so Markdown renders them literally."""
    return _PLACEHOLDER_RE.sub(
        lambda m: m.group(0).replace("<", r"\<").replace(">", r"\>"),
        text,
    )


def build_chips_from_insured_details(
    insured_details: Optional[Dict[str, str]]
) -> List[Dict[str, Any]]:
    if not insured_details:
        return []
    return [
        {
            "label": k,
            "value": k,
            "description": f"Assign to {v}",
        }
        for k, v in insured_details.items()
        if v and str(v).strip()
    ]


def build_quick_action_preview_update() -> Dict[str, Any]:
    return {
        "type": "quick_action",
        "data": [
            {
                "label": "Preview update",
                "prompt": "Preview update document requests with assigned parties",
            }
        ],
    }


# ------------------------------------
# Form builders: initial info form
# ------------------------------------


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

    insured_options = [
        {
            "value": item["value"],
            "label": item["label"]
        }
        for item in form_config["insured_type"]
    ]

    insured_lookup_data: List[Dict[str, Any]] = []
    for insured_item in form_config["insured_type"]:
        lob_components: List[Dict[str, Any]] = []
        for lob_component in insured_item["components"]:
            for lob_key, fields in lob_component.items():
                lob_value = next(
                    (g["value"] for g in form_config["lob"]
                     if g["value"].lower() == lob_key.lower()),
                    lob_key
                )
                keyvalue_data = [
                    {
                        "value": field["value"],
                        "label": field["label"]
                    }
                    for field in fields
                ]
                lob_components.append({
                    "value": lob_value,
                    "components": [
                        {
                            "type": "keyvalue_mapper",
                            "id": "insured_details",
                            "label": "Provide insured details",
                            "required": True,
                            "data": keyvalue_data,
                        }
                    ],
                })
        insured_lookup_data.append({
            "value": insured_item["value"],
            "components": [
                {
                    "type": "lookup",
                    "id": f"insured_details_lob_{insured_item['value']}",
                    "metadata": {
                        "field_id": "lob"
                    },
                    "data": lob_components,
                }
            ],
        })

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
            "type": "select",
            "id": "insured_type",
            "label": "Is the insured policy holder a business?",
            "placeholder": "Choose an option",
            "required": True,
            "data": insured_options,
        },
        {
            "type": "lookup",
            "id": "insured_details_lookup",
            "metadata": {
                "field_id": "insured_type"
            },
            "data": insured_lookup_data,
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
    """Build review form for key concerns."""
    components: List[Dict[str, Any]] = []

    for idx, kc in enumerate(key_concerns.concern_set, start=1):

        components.append({
            "type": "info",
            "id": f"rationale_{idx}",
            "label": f"{idx}. {kc.concern}",
            "description": kc.rationale,
        })

    form_data = components

    return [{
        "type": "workflow_stage",
        "data": {
            "name": "Key Concerns",
            "data": [
                # {"type": "smart_view", "data": view_data},
                {"type": "smart_form", "confirm_submit": True, "data": form_data},
            ],
        },
    }]


def build_form_doc_request(
    doc_request: DocRequestSet,
    insured_details: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Build editable review form for document requests with optional party chips."""
    components: List[Dict[str, Any]] = []

    chip_data = build_chips_from_insured_details(insured_details)

    for idx, dr in enumerate(doc_request.document_set, start=1):
        default_chips = (dr.assigned_parties or [])
        chipbox: Dict[str, Any] = {
            "type": "info_chipbox",
            "id": f"doc_{idx}_chips",
            "label": dr.doc_type,
            "description": dr.doc_details,
            "required": False,
            "notApplicable": True,
            "defaultValue": default_chips,
        }
        if chip_data:
            chipbox["data"] = chip_data
        components.append(chipbox)

    view_data: List[Dict[str, Any]] = [
        {"type": "markdown", "data": {"content": "## Document Requests"}},
        {"type": "markdown", "data": {"content": f"Version: {doc_request.version}"}},
    ]

    form_data: List[Dict[str, Any]] = [
        {
            "type": "title",
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
    """Build review form for additional enquiries."""
    components: List[Dict[str, Any]] = []

    for idx, eq in enumerate(enquiries.enquiries_set, start=1):

        components.append({
            "type": "info",
            "id": f"enquiry_detail_{idx}",
            "label": f"{idx}. {eq.enquiry}",
            "description": eq.enquiry_detail,
        })

    form_data = components

    return [{
        "type": "workflow_stage",
        "data": {
            "name": "Additional Enquiries",
            "data": [
                # {"type": "smart_view", "data": view_data},
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
                "placeholder": q.question_text or "",
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
    Concern is recovered from `previous` by 1-based position. Used only when a list item marked as NA on front end
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

    Only doc_{N}_chips is in the payload. doc_type and doc_details are
    display-only (label/description on chipbox), recovered from `previous`
    by 1-based position.
    """
    doc_chips: Dict[int, List[str]] = {}
    for k, v in (form_payload or {}).items():
        m = re.fullmatch(r"doc_(\d+)_chips", str(k))
        if m:
            val = v or []
            if isinstance(val, str):
                val = [val]
            doc_chips[int(m.group(1))] = [x.strip()
                                          for x in val if x and str(x).strip()]

    prev_items = list(
        previous.document_set if previous and previous.document_set else []
    )
    items: List[DocRequest] = []

    for i, prev in enumerate(prev_items):
        idx = i + 1
        if idx in doc_chips:
            chips = doc_chips[idx]
        elif prev.assigned_parties:
            chips = prev.assigned_parties
        else:
            chips = []

        if prev.doc_type:
            items.append(DocRequest(
                doc_type=prev.doc_type,
                doc_details=prev.doc_details,
                assigned_parties=chips if chips else None,
                doc_details_original=prev.doc_details_original or prev.doc_details,
            ))

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

def build_form_final(claim_id: str, external_agent_plan: ExternalAgentPlan) -> List[Dict[str, Any]]:
    """Build read-only final output view for the assembled external agent plan."""

    # Key Concerns section
    concern_lines = ["### Key Concerns\n"]
    for i, kc in enumerate(external_agent_plan.concern_set.concern_set or [], start=1):
        concern_lines.append(f"**Concern {i}.** {kc.concern}")
        if kc.rationale:
            concern_lines.append(f"> {kc.rationale}")
        concern_lines.append("")
    concerns_markdown = "\n".join(
        concern_lines).strip() or "_No key concerns._"

    # Document Requests section
    doc_lines = ["### Document Requests\n"]
    for dr in external_agent_plan.document_set.document_set or []:
        doc_lines.append(f"**{dr.doc_type}:** {_escape_placeholders(dr.doc_details)}")
        doc_lines.append("")
    docs_markdown = "\n".join(doc_lines).strip() or "_No document requests._"

    # Additional Enquiries section
    enq_lines = ["### Additional Enquiries\n"]
    for eq in external_agent_plan.enquiry_set.enquiries_set or []:
        enq_lines.append(f"**{eq.enquiry}:** {eq.enquiry_detail}")
        enq_lines.append("")
    enquiries_markdown = "\n".join(
        enq_lines).strip() or "_No additional enquiries._"

    view_data: List[Dict[str, Any]] = [
        {"type": "markdown", "data": {"content": "## Final External Agent Plan"}},
        {"type": "markdown", "data": {
            "content": f"Claim ID: {claim_id}  \nVersion: {external_agent_plan.version}  \nCreated: {external_agent_plan.created_at}"
        }},
        {"type": "markdown", "data": {"content": concerns_markdown}},
        {"type": "markdown", "data": {"content": docs_markdown}},
        {"type": "markdown", "data": {"content": enquiries_markdown}},
    ]

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
