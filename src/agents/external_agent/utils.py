import re
import logging
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple
from agents.external_agent.schemas import (
    KeyConcern, KeyConcernSet,
    DocRequest, DocRequestSet,
    AdditionalEnquiries, AdditionalEnquiriesSet,
    InterviewQuestion, InterviewQuestionSets,
    ExternalAgentPlan,
)

logger = logging.getLogger(__name__)


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


def categorise_parties(
    assigned_keys: List[str],
    insured_details: Dict[str, str],
    insured_type: Optional[str],
) -> Tuple[List[str], List[str], List[str]]:
    insured_names: List[str] = []
    driver_names: List[str] = []
    other_names: List[str] = []

    is_business = (insured_type or "").strip().lower() == "yes"

    for key in assigned_keys:
        value = (insured_details.get(key) or "").strip()
        if not value:
            continue
        key_lower = key.lower()
        if is_business:
            if "director" in key_lower or "main contact" in key_lower:
                driver_names.append(value)
            elif "driver" in key_lower:
                driver_names.append(value)
            elif "business" in key_lower or "company" in key_lower or "entity" in key_lower:
                insured_names.append(value)
            else:
                other_names.append(value)
        else:
            if "driver" in key_lower:
                driver_names.append(value)
            elif "additional" in key_lower and "insured" in key_lower:
                insured_names.append(value)
            elif "insured" in key_lower:
                insured_names.insert(0, value)
            else:
                other_names.append(value)

    return insured_names, driver_names, other_names


def build_party_possessive_phrase(
    insured_names: List[str],
    driver_names: List[str],
    other_names: List[str],
    insured_type: Optional[str],
) -> Optional[str]:
    is_business = (insured_type or "").strip().lower() == "yes"

    all_names = insured_names + driver_names + other_names
    if not all_names:
        return None

    if is_business:
        parts = [f"{name}'s" for name in all_names]
    elif len(all_names) == 1 and not driver_names and not other_names:
        return "your"
    else:
        parts: List[str] = []
        if insured_names and len(insured_names) == 1:
            parts.append("your")
        else:
            for name in insured_names:
                parts.append(f"{name}'s")
        for name in driver_names:
            parts.append(f"{name}'s")
        for name in other_names:
            parts.append(f"{name}'s")

    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def apply_party_names_to_doc_details(
    doc_details: str,
    assigned_keys: List[str],
    insured_details: Dict[str, str],
    insured_type: Optional[str],
) -> str:
    if not assigned_keys or not insured_details:
        return doc_details

    insured_names, driver_names, other_names = categorise_parties(
        assigned_keys, insured_details, insured_type
    )

    phrase = build_party_possessive_phrase(
        insured_names, driver_names, other_names, insured_type
    )

    if not phrase:
        return doc_details

    is_business = (insured_type or "").strip().lower() == "yes"

    has_personal_ref = bool(
        re.search(r"\byour\b", doc_details, re.IGNORECASE)
        or re.search(r"\byou\b", doc_details, re.IGNORECASE)
        or re.search(r"\[Name\]|\[INSERT NAME\]|enter name of person", doc_details, re.IGNORECASE)
    )

    if not has_personal_ref:
        pattern = r"^(A copy of )"
        if re.search(pattern, doc_details):
            doc_details = re.sub(
                pattern, rf"\1{phrase} ", doc_details, count=1)
        return doc_details

    if is_business:
        doc_details = re.sub(
            r"\byour\b", lambda m: f"{insured_names[0]}'s" if insured_names else m.group(
            ),
            doc_details, flags=re.IGNORECASE
        )
        doc_details = re.sub(
            r"\byou\b", lambda m: insured_names[0] if insured_names else "you",
            doc_details, flags=re.IGNORECASE
        )
        doc_details = re.sub(
            r"\[Name\]|\[INSERT NAME\]|enter name of person",
            lambda m: insured_names[0] if insured_names else m.group(),
            doc_details, flags=re.IGNORECASE
        )
    else:
        if phrase == "your":
            return doc_details

        doc_details = re.sub(
            r"\byour\b", phrase, doc_details, count=1, flags=re.IGNORECASE
        )
        doc_details = re.sub(
            r"\[Name\]|\[INSERT NAME\]|enter name of person",
            phrase, doc_details, count=1, flags=re.IGNORECASE
        )

    return doc_details


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
    """Build editable review form for key concerns."""
    components: List[Dict[str, Any]] = []

    for idx, kc in enumerate(key_concerns.concern_set, start=1):
        components.append({
            "type": "textarea",
            "id": f"concern_{idx}",
            "label": f"Concern {idx}",
            "placeholder": kc.concern,
            "required": False,
        })
        components.append({
            "type": "textarea",
            "id": f"rationale_{idx}",
            "label": "Rationale",
            "placeholder": kc.rationale,
            "required": False,
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


def build_form_doc_request(
    doc_request: DocRequestSet,
    insured_details: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Build editable review form for document requests with optional party chips."""
    components: List[Dict[str, Any]] = []

    chip_data = build_chips_from_insured_details(insured_details)

    for idx, dr in enumerate(doc_request.document_set, start=1):
        components.append({
            "type": "text",
            "id": f"doc_type_{idx}",
            "label": f"Document Type {idx}",
            "placeholder": dr.doc_type,
            "required": False,
        })
        components.append({
            "type": "textarea",
            "id": f"doc_details_{idx}",
            "label": "Details",
            "placeholder": dr.doc_details,
            "required": False,
        })
        if chip_data:
            default_chips = (dr.assigned_parties or [])
            components.append({
                "type": "info_chipbox",
                "id": f"doc_{idx}_chips",
                "label": "Assign Party",
                "data": chip_data,
                "required": False,
                "notApplicable": True,
                "defaultValue": default_chips,
                "description": "Review this information and mark N/A if it does not apply.",
                "hint": "Select the parties this document request applies to",
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
        components.append({
            "type": "text",
            "id": f"enquiry_{idx}",
            "label": f"Enquiry {idx}",
            "placeholder": eq.enquiry,
            "required": False,
        })
        components.append({
            "type": "textarea",
            "id": f"enquiry_detail_{idx}",
            "label": "Detail",
            "placeholder": eq.enquiry_detail,
            "required": False,
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
    """Parse flat form payload back into KeyConcernSet."""
    # Collect concern_{N} and rationale_{N} pairs
    concerns: Dict[int, str] = {}
    rationales: Dict[int, str] = {}

    for k, v in (form_payload or {}).items():
        m = re.fullmatch(r"concern_(\d+)", str(k))
        if m:
            concerns[int(m.group(1))] = (v or "").strip()
        m = re.fullmatch(r"rationale_(\d+)", str(k))
        if m:
            rationales[int(m.group(1))] = (v or "").strip()

    indices = sorted(set(concerns) | set(rationales))

    prev_items = list(
        previous.concern_set) if previous and previous.concern_set else []
    items: List[KeyConcern] = []

    for i, idx in enumerate(indices):
        concern_text = concerns.get(idx, "")
        rationale_text = rationales.get(idx, "")

        # Carry forward rationale if concern text unchanged
        if not rationale_text and i < len(prev_items):
            if concern_text == prev_items[i].concern:
                rationale_text = prev_items[i].rationale

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
    doc_chips: Dict[int, List[str]] = {}
    for k, v in (form_payload or {}).items():
        m = re.fullmatch(r"doc_details_(\d+)", str(k))
        if m:
            doc_details[int(m.group(1))] = (v or "").strip()
        m = re.fullmatch(r"doc_(\d+)_chips", str(k))
        if m:
            val = v or []
            if isinstance(val, str):
                val = [val]
            doc_chips[int(m.group(1))] = [x.strip() for x in val if x and str(x).strip()]

    prev_items = list(
        previous.document_set if previous and previous.document_set else []
    )
    items: List[DocRequest] = []

    for idx in sorted(doc_details):
        if idx - 1 >= len(prev_items):
            continue
        doc_type_text = prev_items[idx - 1].doc_type
        doc_details_text = doc_details[idx]

        chips = doc_chips.get(idx, [])
        if not chips and idx - 1 < len(prev_items) and prev_items[idx - 1].assigned_parties:
            chips = prev_items[idx - 1].assigned_parties

        if doc_type_text:
            items.append(DocRequest(
                doc_type=doc_type_text,
                doc_details=doc_details_text,
                assigned_parties=chips if chips else None,
            ))

    return DocRequestSet(
        document_set=items,
        version=(previous.version if previous else 0) + 1,
        update_notes=None,
    )
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
    """Parse flat form payload back into AdditionalEnquiriesSet."""
    enquiries: Dict[int, str] = {}
    enquiry_details: Dict[int, str] = {}

    for k, v in (form_payload or {}).items():
        m = re.fullmatch(r"enquiry_(\d+)", str(k))
        if m:
            enquiries[int(m.group(1))] = (v or "").strip()
        m = re.fullmatch(r"enquiry_detail_(\d+)", str(k))
        if m:
            enquiry_details[int(m.group(1))] = (v or "").strip()

    indices = sorted(set(enquiries) | set(enquiry_details))

    prev_items = list(
        previous.enquiries_set) if previous and previous.enquiries_set else []
    items: List[AdditionalEnquiries] = []

    for i, idx in enumerate(indices):
        enquiry_text = enquiries.get(idx, "")
        detail_text = enquiry_details.get(idx, "")

        # Carry forward detail if enquiry text unchanged
        if not detail_text and i < len(prev_items):
            if enquiry_text == prev_items[i].enquiry:
                detail_text = prev_items[i].enquiry_detail

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
        doc_lines.append(f"**{dr.doc_type}:** {dr.doc_details}")
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
