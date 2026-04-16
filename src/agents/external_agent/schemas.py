from pydantic import BaseModel, Field
from typing import List, TypedDict, Optional, Annotated, Union, Any, Literal, Tuple, Dict
from smart_investigator.foundation.schemas.schemas import SmartInvestigatorAgentState, SIErrorCode
from datetime import datetime
from langgraph.graph import StateGraph, START, END, MessagesState


# --- Commented out: duplicate of SmartInvestigatorAgentState in foundation ---
# class SmartInvestigatorAgentState(MessagesState):
#     artifact: dict[str, Any]
#     resume: bool


class Reference(BaseModel):
    reference: str
    source: str


# --- Commented out: leftover from interview plans agent ---
# class InterviewObjective(BaseModel):
#     objective_title: str = Field(
#         description="Brief 1-4 word label"
#     )
#     objective: str
#     supporting_evidence: Optional[List[Reference]] = None


# --- Commented out: leftover from interview plans agent ---
# class InterviewStrategy(BaseModel):
#     aim: str
#     objectives: List[InterviewObjective]
#     update_notes: Optional[str] = None


class InterviewQuestion(BaseModel):
    question_id: int
    category: str
    question_text: str


class InterviewQuestionSets(BaseModel):
    question_sets: List[InterviewQuestion]
    version: int = 1
    update_notes: Optional[str] = None


class KeyConcern(BaseModel):
    concern: str
    rationale: str


class KeyConcernSet(BaseModel):
    concern_set: List[KeyConcern]
    version: int = 1
    update_notes: Optional[str] = None


class DocRequest(BaseModel):
    doc_type: str
    doc_details: str


class DocRequestSet(BaseModel):
    document_set: List[DocRequest]
    version: int = 1
    update_notes: Optional[str] = None


class AdditionalEnquiries(BaseModel):
    enquiry: str
    enquiry_detail: str


class AdditionalEnquiriesSet(BaseModel):
    enquiries_set: List[AdditionalEnquiries]
    version: int = 1
    update_notes: Optional[str] = None


# --- Commented out: leftover from interview plans agent ---
# class InterviewPlan(BaseModel):
#     question_sets: List[InterviewQuestion]
#     additional_evidence_requests: List[str]
#     version: int
#     created_at: str = Field(
#         default_factory=lambda: datetime.utcnow().isoformat())
#     update_notes: Optional[str] = None


class ExternalAgentPlan(BaseModel):
    concern_set: KeyConcernSet
    document_set: DocRequestSet
    enquiry_set: AdditionalEnquiriesSet
    # interview_plan: InterviewQuestionSets
    version: int
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat())
    update_notes: Optional[str] = None


class Knowledge(BaseModel):
    query: str
    answer: str = Field(
        description="The relevant answer - do not summarise."
    )


class KnowledgeSet(BaseModel):
    knowledge: List[Knowledge]


# --- Commented out: replaced by per-section synthesis using existing schemas ---
# class KnowledgeReport(BaseModel):
#     document_set: DocRequestSet
#     enquiries_rationale: List[str]
#     interview_plan: InterviewQuestionSets


class HITLDecision(BaseModel):
    intent: Literal["accept", "feedback", "unrelated"]
    task_summary: str


class ExternalAgentState(MessagesState):
    """State for the external agent investigation instructions system."""
    # Case context
    claim_id: str
    brand: str
    initial_review: str
    additional_info: Optional[str] = None
    lob: str
    investigation_type: List[str]
    investigation_scope: str

    # User-selected sections (key_concerns always generated regardless)
    selected_sections: List[Literal["doc_request", "additional_enquiries", "interview_plan"]]

    # Per-section outputs
    key_concerns: Optional[KeyConcernSet] = None
    doc_request: Optional[DocRequestSet] = None
    additional_enquiries: Optional[AdditionalEnquiriesSet] = None
    interview_plan: Optional[InterviewQuestionSets] = None

    # Per-section synthesized knowledge (cached for feedback regeneration)
    doc_request_knowledge: Optional[str] = None
    enquiries_knowledge: Optional[str] = None
    interview_plan_knowledge: Optional[str] = None

    # Final assembled output
    external_agent_plan: Optional[ExternalAgentPlan] = None

    # HITL / control flow
    artifact: dict[str, Any]
    resume: bool
    pending_step: Optional[str] = None
    hitl_decision: Optional[HITLDecision] = None
    hitl_artifact: Optional[dict[str, Any]] = None
    hitl_task: Optional[str] = None


# --- Commented out: leftover from interview plans agent ---
# class InterviewPlanStruct(BaseModel):
#     claim_id: Optional[str] = None
#     lob: Optional[str] = None
#     investigation_type: Optional[List[str]] = None
