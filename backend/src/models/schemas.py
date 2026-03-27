from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class AuthStatus(str, Enum):
    PENDING = "pending"
    TRIAGE = "triage"
    EVIDENCE_EXTRACTION = "evidence_extraction"
    POLICY_LOOKUP = "policy_lookup"
    VALIDATION = "validation"
    SUBMISSION = "submission"
    MONITORING = "monitoring"
    APPROVED = "approved"
    DENIED = "denied"
    APPEAL_ANALYSIS = "appeal_analysis"
    APPEAL_GENERATION = "appeal_generation"
    APPEAL_SUBMISSION = "appeal_submission"
    APPEAL_APPROVED = "appeal_approved"
    APPEAL_DENIED = "appeal_denied"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class ServiceType(str, Enum):
    MRI = "mri"
    CT_SCAN = "ct_scan"
    LAB_TEST = "lab_test"
    SURGERY = "surgery"
    PHYSICAL_THERAPY = "physical_therapy"
    DURABLE_MEDICAL_EQUIPMENT = "durable_medical_equipment"
    PRESCRIPTION = "prescription"
    MENTAL_HEALTH = "mental_health"
    OTHER = "other"


class Patient(BaseModel):
    id: str
    mrn: str
    first_name: str
    last_name: str
    date_of_birth: str
    gender: str
    address: Optional[str] = None
    phone: Optional[str] = None
    insurance_id: str
    payer_name: str
    conditions: List[Dict[str, Any]] = Field(default_factory=list)
    medications: List[Dict[str, Any]] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)


class ClinicalNote(BaseModel):
    id: str
    patient_id: str
    note_type: str
    content: str
    created_at: datetime
    provider: str
    facility: str


class ExtractedEntity(BaseModel):
    type: str
    value: str
    code: Optional[str] = None
    code_system: Optional[str] = None
    confidence: float
    context: Optional[str] = None
    is_negated: bool = False


class ClinicalEvidence(BaseModel):
    patient_id: str
    conditions: List[ExtractedEntity]
    procedures: List[ExtractedEntity]
    medications: List[ExtractedEntity]
    lab_results: List[ExtractedEntity]
    vital_signs: List[ExtractedEntity]
    allergies: List[ExtractedEntity]
    clinical_summary: str
    extraction_confidence: float


class PolicyRequirement(BaseModel):
    requirement_id: str
    description: str
    required_documentation: List[str]
    min_clinical_criteria: List[str]
    coverage_type: str
    applicable_cpt_codes: List[str]
    applicable_icd_codes: List[str]


class PolicyMatchResult(BaseModel):
    policy_id: str
    policy_name: str
    is_covered: bool
    match_score: float
    satisfied_requirements: List[str]
    missing_requirements: List[str]
    additional_documentation_needed: List[str]
    policy_text: str


class AuthorizationRequest(BaseModel):
    id: str
    patient_id: str
    patient: Optional[Patient] = None
    service_type: ServiceType
    cpt_code: str
    icd10_code: str
    clinical_evidence: Optional[ClinicalEvidence] = None
    policy_match: Optional[PolicyMatchResult] = None
    status: AuthStatus = AuthStatus.PENDING
    priority: str = "standard"  # standard, urgent
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    decision_at: Optional[datetime] = None
    external_auth_id: Optional[str] = None
    denial_reason: Optional[str] = None
    appeal_text: Optional[str] = None
    agent_traces: Dict[str, Any] = Field(default_factory=dict)
    processing_time_seconds: float = 0.0
    cost_estimate: float = 0.0


class AgentTrace(BaseModel):
    agent_name: str
    status: str
    start_time: datetime
    end_time: Optional[datetime] = None
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    reasoning_steps: List[str]
    tokens_used: int = 0
    error: Optional[str] = None


class PayerConfig(BaseModel):
    id: str
    name: str
    api_endpoint: str
    accepts_fhir: bool = True
    x12_partner_id: Optional[str] = None
    requires_pre_auth: bool = True
    avg_response_time_hours: float = 24.0


class DashboardStats(BaseModel):
    total_requests: int = 0
    approved: int = 0
    denied: int = 0
    pending: int = 0
    avg_processing_time_seconds: float = 0.0
    approval_rate: float = 0.0
    total_cost_saved: float = 0.0
    appeals_success_rate: float = 0.0
    requests_by_service_type: Dict[str, int] = Field(default_factory=dict)
    denials_by_reason: Dict[str, int] = Field(default_factory=dict)
    processing_times_by_hour: List[Dict[str, Any]] = Field(default_factory=list)
