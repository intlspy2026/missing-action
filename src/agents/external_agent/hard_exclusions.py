"""
Hard-exclusion pre-filter for external-agent document requests.

Strips methodology doc types that have no factual hook in the case facts,
before the LLM ever sees them.

Each hook keyword is compiled as a case-insensitive word-boundary regex
to prevent false matches (e.g. "work" matching "WorkBench").
"""

import logging
import re as _re
from typing import Optional

logger = logging.getLogger(__name__)

_HARD_EXCLUSIONS = {
    # doc_type pattern → hook keywords (word-boundary regexes)
    "work roster":       [r"work roster", r"time sheet", r"shift work",
                          r"clock in", r"clock out", r"on duty"],
    "timesheet":         [r"work roster", r"time sheet", r"shift work",
                          r"clock in", r"clock out", r"on duty"],
    "insurance history": [r"other insurer", r"external claims?",
                          r"claims? ?made ?outside", r"outside of suncorp",
                          r"lodged a claim with"],
    "claims history":    [r"other insurer", r"external claims?",
                          r"claims? ?made ?outside", r"outside of suncorp",
                          r"lodged a claim with"],
    "criminal history":  [r"\bcrim", r"offen[dc]er?", r"convict(?:ed|ion)",
                           r"arrest(?:ed)?"],
    "background check":  [r"\bcrim", r"offen[dc]er?", r"convict(?:ed|ion)",
                           r"charg(?:ed?|ing)", r"police", r"arrest(?:ed)?"],
    "fit to interview":   [r"hospital", r"medical treat", r"admission",
                           r"surger", r"mental health"],
    "medical certificate": [r"injur", r"hospital", r"medical treat", r"admission",
                            r"surger", r"doctor", r"ambulance", r"mental health"],
    "hospital":           [r"hospitali[sz]", r"admission", r"injur",
                            r"ambulance", r"surger"],
    "medical records":     [r"injur", r"hospital", r"medical treat", r"admission",
                            r"surger", r"doctor", r"ambulance", r"mental health"],
    "rideshare":         [r"rideshare", r"taxi", r"\buber\b", r"\bdidi\b",
                          r"\bbolt\b", r"\bola\b"],
    "taxi":              [r"rideshare", r"taxi", r"\buber\b", r"\bdidi\b",
                          r"\bbolt\b", r"\bola\b"],
    "transport receipt": [r"rideshare", r"taxi", r"\buber\b", r"\bdidi\b",
                          r"\bbolt\b", r"\bola\b"],
    "towing records":    [r"\btow(?:ing|ed|s|truck)?\b"],
    "tow truck receipt": [r"\btow(?:ing|ed|s|truck)?\b"],
    "toll":              [r"\btoll\b", r"\bmotorway\b", r"\bexpressway\b",
                          r"\btollway\b"],
    "tenancy":           [r"\btenant\b", r"\btenancy\b", r"\brental\b",
                          r"\blease\b", r"\blandlord\b"],
    "contract of sale":  [r"contract of sale", r"\bconveyanc", r"\bsettlement\b",
                          r"\bpurchaser\b", r"\bvendor\b"],
    "correspondence":    [r"\bemail\b", r"\btext messages?\b", r"\bsms\b",
                          r"\bcorrespondence\b", r"\bmessages?\b",
                          r"\binstant messages?\b"],
    "email":             [r"\bemail\b", r"\btext messages?\b", r"\bsms\b",
                          r"\bcorrespondence\b", r"\bmessages?\b",
                          r"\binstant messages?\b"],
    "text message":      [r"\bemail\b", r"\btext messages?\b", r"\bsms\b",
                          r"\bcorrespondence\b", r"\bmessages?\b",
                          r"\binstant messages?\b"],
    "sms":               [r"\bemail\b", r"\btext messages?\b", r"\bsms\b",
                          r"\bcorrespondence\b", r"\bmessages?\b",
                          r"\binstant messages?\b"],
    "cctv footage":      [r"\bcctv\b", r"\bcamera", r"\bfootage\b",
                          r"\bsurveillance\b", r"\bvideo\b"],
    "motor sport":       [r"\bmotorsport\b", r"\bracetrack\b", r"\brace track\b",
                          r"\btrack day\b", r"\bcams\b", r"\bracing circuit\b",
                          r"\bdrag race\b", r"\bdrag racing\b"],
}

# Pre-compile hook patterns for each exclusion group
_HOOK_REGEXES = {
    group: [_re.compile(patt, _re.IGNORECASE) for patt in patterns]
    for group, patterns in _HARD_EXCLUSIONS.items()
}

_CATCH_ALL_MARKERS = [
    "any other document",
    "other documents",
    "other supporting",
]


def _has_hook(case_text: str, group: str) -> bool:
    """Check if any hook regex for `group` finds a match in case_text."""
    regexes = _HOOK_REGEXES.get(group, [])
    if not regexes:
        return False
    case_lower = case_text.lower()
    return any(rgx.search(case_lower) for rgx in regexes)


def _is_catch_all(doc_type: str) -> bool:
    doc_lower = doc_type.lower()
    return any(marker in doc_lower for marker in _CATCH_ALL_MARKERS)


def _doc_type_is_excludable(doc_type: str, case_text: str) -> bool:
    """Return True if doc_type matches a hard exclusion with no hook.

    Two doc-type categories bypass the deterministic pre-filter entirely and
    are instead governed by the LLM's relevance rules:
      - Signed authorities: never stripped (RULE 3d placeholder filling is
        handled by the SME wording step; the relevance filter must not drop
        them).
      - Police documents: never stripped here. Police inclusion is decided by
        the LLM's attendance-status rule (RULE 3 item 15 in
        DOC_REQUEST_RELEVANCE_PROMPT), not by keyword hooks. Without this
        guard, a police doc_type containing the substring "correspondence"
        (e.g. "A copy of all correspondence from the Police ...") would be
        misclassified under the "correspondence" exclusion group and stripped
        on cases with no email/text hook — including cases where police
        actually attended. The guard prevents that cross-category collision.
    """
    doc_lower = doc_type.lower()
    if "signed authorit" in doc_lower:
        return False
    if "police" in doc_lower:
        return False
    for pattern in _HARD_EXCLUSIONS:
        if pattern in doc_lower:
            if not _has_hook(case_text, pattern):
                return True
            return False
    return False


def _split_sub_items(text: str) -> list:
    if ";" in text:
        return [s.strip() for s in text.split(";") if s.strip()]
    if "\n-" in text or "\n•" in text:
        parts = []
        for line in text.split("\n"):
            stripped = line.lstrip("-• \t")
            if stripped:
                parts.append(stripped)
        return parts
    if "\n" in text:
        return [s.strip() for s in text.split("\n") if s.strip()]
    return [text]


def _filter_doc_details(doc_details: str, case_text: str) -> str:
    sub_items = _split_sub_items(doc_details)
    if len(sub_items) <= 1:
        return doc_details
    kept = []
    for item in sub_items:
        if not _doc_type_is_excludable(item, case_text):
            kept.append(item)
    if not kept:
        return ""
    if ";" in doc_details:
        return "; ".join(kept)
    if "\n" in doc_details:
        return "\n".join(kept)
    return ", ".join(kept)


def strip_hard_exclusions(
    doc_list_data: dict,
    initial_review: str,
    additional_info: str,
    investigation_types: Optional[list[str]] = None,
) -> dict:
    """
    Strip methodology document types that have no factual hook in the case
    narrative. Mutates and returns `doc_list_data`.
    """
    docs = doc_list_data.get("document_set", [])
    case_text = (
        f"{initial_review or ''} {additional_info or ''} "
        f"{' '.join(investigation_types or [])}"
    )
    result = []
    stripped = []
    for doc in docs:
        doc_type = doc.get("doc_type", "")
        if _doc_type_is_excludable(doc_type, case_text):
            stripped.append(doc_type)
            continue
        doc_details = doc.get("doc_details", "")
        if _is_catch_all(doc_type) and doc_details:
            cleaned = _filter_doc_details(doc_details, case_text)
            if not cleaned.strip():
                stripped.append(f"{doc_type} [all sub-items filtered]")
                continue
            for item in _split_sub_items(cleaned):
                result.append({"doc_type": item, "doc_details": item})
            continue
        if doc_details:
            cleaned = _filter_doc_details(doc_details, case_text)
            if cleaned != doc_details:
                doc["doc_details"] = cleaned
        result.append(doc)
    if stripped:
        logger.info("Hard-exclusion pre-filter stripped %d doc types: %s",
                      len(stripped), stripped)
    doc_list_data["document_set"] = result
    return doc_list_data
