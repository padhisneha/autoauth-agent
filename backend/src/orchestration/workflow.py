"""
Orchestration Layer - LangGraph workflow for multi-agent coordination
"""

import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, TypedDict, Literal
from enum import Enum

# LangGraph components (simplified for demo - in production use actual langgraph)
# We'll create a custom implementation that mimics langgraph behavior


class WorkflowState(str, Enum):
    """Workflow states for the authorization process."""
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
    COMPLETED = "completed"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class AgentStatus(str, Enum):
    """Status of individual agents."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING = "waiting"


class AgentInfo(TypedDict):
    """Information about an agent's execution."""
    name: str
    status: AgentStatus
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    reasoning_steps: List[str]
    error: Optional[str]
    tokens_used: int


class WorkflowStateData(TypedDict):
    """Complete state of the authorization workflow."""
    auth_id: str
    patient_id: str
    service_type: str
    cpt_code: str
    icd10_code: str
    
    current_state: WorkflowState
    target_state: Optional[WorkflowState]
    
    clinical_evidence: Optional[Dict[str, Any]]
    policy_requirements: Optional[Dict[str, Any]]
    policy_match: Optional[Dict[str, Any]]
    fhir_bundle: Optional[Dict[str, Any]]
    submission_result: Optional[Dict[str, Any]]
    denial_analysis: Optional[Dict[str, Any]]
    appeal_letter: Optional[str]
    
    agents: Dict[str, AgentInfo]
    
    error: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    processing_log: List[Dict[str, Any]]


class AuthorizationWorkflow:
    """
    Main orchestration workflow for the AutoAuth Agent.
    Coordinates the multi-agent system for end-to-end prior authorization.
    """
    
    def __init__(
        self,
        clinical_reader_agent,
        policy_agent,
        submission_agent,
        appeal_agent
    ):
        self.clinical_reader = clinical_reader_agent
        self.policy = policy_agent
        self.submission = submission_agent
        self.appeal = appeal_agent
        
        # State machine transitions
        self.transitions = {
            WorkflowState.PENDING: [WorkflowState.TRIAGE],
            WorkflowState.TRIAGE: [WorkflowState.EVIDENCE_EXTRACTION, WorkflowState.VALIDATION],
            WorkflowState.EVIDENCE_EXTRACTION: [WorkflowState.POLICY_LOOKUP],
            WorkflowState.POLICY_LOOKUP: [WorkflowState.VALIDATION],
            WorkflowState.VALIDATION: [WorkflowState.SUBMISSION, WorkflowState.REQUIRES_HUMAN_REVIEW],
            WorkflowState.SUBMISSION: [WorkflowState.MONITORING],
            WorkflowState.MONITORING: [WorkflowState.APPROVED, WorkflowState.DENIED],
            WorkflowState.DENIED: [WorkflowState.APPEAL_ANALYSIS, WorkflowState.COMPLETED],
            WorkflowState.APPEAL_ANALYSIS: [WorkflowState.APPEAL_GENERATION],
            WorkflowState.APPEAL_GENERATION: [WorkflowState.APPEAL_SUBMISSION],
            WorkflowState.APPEAL_SUBMISSION: [WorkflowState.MONITORING, WorkflowState.COMPLETED],
        }
    
    async def execute_workflow(
        self,
        auth_request: Any,
        clinical_notes: List[Any],
        callback=None
    ) -> Dict[str, Any]:
        """
        Execute the complete authorization workflow.
        """
        # Initialize workflow state
        state = self._initialize_state(auth_request)
        
        # Execute each stage
        try:
            # Stage 1: Triage
            state = await self._stage_triage(state, callback)
            
            # Stage 2: Evidence Extraction
            state = await self._stage_evidence_extraction(state, clinical_notes, callback)
            
            # Stage 3: Policy Lookup
            state = await self._stage_policy_lookup(state, auth_request, callback)
            
            # Stage 4: Validation
            state = await self._stage_validation(state, callback)
            
            # Stage 5: Submission
            state = await self._stage_submission(state, auth_request, callback)
            
            # Stage 6: Monitoring (simulate decision)
            state = await self._stage_monitoring(state, callback)
            
            # Handle result
            if state["current_state"] == WorkflowState.DENIED:
                # Auto-trigger appeal if denied
                state = await self._handle_denial(state, auth_request, callback)
            
        except Exception as e:
            state["error"] = str(e)
            state["current_state"] = WorkflowState.REQUIRES_HUMAN_REVIEW
            state = self._log_event(state, "error", {"error": str(e)})
        
        return self._compile_results(state)
    
    def _initialize_state(self, auth_request: Any) -> WorkflowStateData:
        """Initialize the workflow state."""
        return {
            "auth_id": auth_request.id,
            "patient_id": auth_request.patient_id,
            "service_type": auth_request.service_type,
            "cpt_code": auth_request.cpt_code,
            "icd10_code": auth_request.icd10_code,
            "current_state": WorkflowState.PENDING,
            "target_state": None,
            "clinical_evidence": None,
            "policy_requirements": None,
            "policy_match": None,
            "fhir_bundle": None,
            "submission_result": None,
            "denial_analysis": None,
            "appeal_letter": None,
            "agents": {},
            "error": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "processing_log": []
        }
    
    async def _stage_triage(
        self, 
        state: WorkflowStateData,
        callback=None
    ) -> WorkflowStateData:
        """Initial triage and priority determination."""
        
        self._start_agent(state, "TriageAgent")
        
        # Analyze urgency
        is_urgent = self._check_urgency(state)
        
        state["target_state"] = WorkflowState.EVIDENCE_EXTRACTION
        state["current_state"] = WorkflowState.TRIAGE
        
        self._complete_agent(
            state, "TriageAgent",
            output={"is_urgent": is_urgent, "priority": "urgent" if is_urgent else "standard"}
        )
        
        state = self._log_event(state, "triage_completed", {"is_urgent": is_urgent})
        
        if callback:
            await callback(state)
        
        return state
    
    async def _stage_evidence_extraction(
        self,
        state: WorkflowStateData,
        clinical_notes: List[Any],
        callback=None
    ) -> WorkflowStateData:
        """Extract clinical evidence from notes."""
        
        self._start_agent(state, "ClinicalReaderAgent")
        
        # Extract clinical evidence
        clinical_evidence = await self.clinical_reader.extract_clinical_evidence(
            clinical_notes,
            state["patient_id"],
            state["service_type"],
            state["cpt_code"]
        )
        
        # Analyze medical necessity
        necessity_analysis = await self.clinical_reader.analyze_medical_necessity(
            clinical_evidence,
            state["service_type"],
            state["cpt_code"]
        )
        
        state["clinical_evidence"] = {
            "evidence": clinical_evidence.model_dump() if hasattr(clinical_evidence, 'model_dump') else clinical_evidence.__dict__,
            "necessity_analysis": necessity_analysis
        }
        
        state["current_state"] = WorkflowState.EVIDENCE_EXTRACTION
        
        self._complete_agent(
            state, "ClinicalReaderAgent",
            output={
                "conditions_found": len(clinical_evidence.conditions),
                "confidence": clinical_evidence.extraction_confidence,
                "summary": clinical_evidence.clinical_summary[:200]
            }
        )
        
        state = self._log_event(state, "evidence_extraction_completed", {
            "conditions": len(clinical_evidence.conditions),
            "confidence": clinical_evidence.extraction_confidence
        })
        
        if callback:
            await callback(state)
        
        return state
    
    async def _stage_policy_lookup(
        self,
        state: WorkflowStateData,
        auth_request: Any,
        callback=None
    ) -> WorkflowStateData:
        """Look up payer policy requirements."""
        
        self._start_agent(state, "PolicyAgent")
        
        # Get policy requirements
        payer_name = auth_request.patient.payer_name if auth_request.patient else "Blue Cross"
        
        policy_req = await self.policy.retrieve_policy_requirements(
            payer_name,
            state["service_type"],
            state["cpt_code"]
        )
        
        # Match clinical evidence to policy
        evidence_dict = state.get("clinical_evidence", {}).get("evidence", {})
        
        # Create a mock clinical evidence object for matching
        class MockEvidence:
            def __init__(self, data):
                self.clinical_summary = data.get("clinical_summary", "")
                self.conditions = data.get("conditions", [])
                self.procedures = data.get("procedures", [])
                self.medications = data.get("medications", [])
                self.lab_results = data.get("lab_results", [])
        
        mock_evidence = MockEvidence(evidence_dict)
        
        policy_match = await self.policy.match_policy(
            mock_evidence,
            policy_req,
            payer_name
        )
        
        state["policy_requirements"] = policy_req.model_dump() if hasattr(policy_req, 'model_dump') else {}
        state["policy_match"] = policy_match.model_dump() if hasattr(policy_match, 'model_dump') else {}
        
        state["current_state"] = WorkflowState.POLICY_LOOKUP
        
        self._complete_agent(
            state, "PolicyAgent",
            output={
                "policy_id": policy_req.requirement_id,
                "match_score": policy_match.match_score,
                "is_covered": policy_match.is_covered
            }
        )
        
        state = self._log_event(state, "policy_lookup_completed", {
            "match_score": policy_match.match_score,
            "is_covered": policy_match.is_covered
        })
        
        if callback:
            await callback(state)
        
        return state
    
    async def _stage_validation(
        self,
        state: WorkflowStateData,
        callback=None
    ) -> WorkflowStateData:
        """Validate the request before submission."""
        
        self._start_agent(state, "ValidationAgent")
        
        # Check if we have all required data
        validation_issues = []
        
        if not state.get("clinical_evidence"):
            validation_issues.append("Missing clinical evidence")
        
        if not state.get("policy_match"):
            validation_issues.append("Missing policy match")
        
        policy_match = state.get("policy_match", {})
        if policy_match and not policy_match.get("is_covered"):
            validation_issues.append("Request does not meet policy criteria")
        
        # Determine next state
        if validation_issues:
            if any("policy" in issue.lower() for issue in validation_issues):
                # Still submit - may be denied
                state["target_state"] = WorkflowState.SUBMISSION
            else:
                state["target_state"] = WorkflowState.REQUIRES_HUMAN_REVIEW
                state["current_state"] = WorkflowState.REQUIRES_HUMAN_REVIEW
        else:
            state["target_state"] = WorkflowState.SUBMISSION
        
        state["current_state"] = WorkflowState.VALIDATION
        
        self._complete_agent(
            state, "ValidationAgent",
            output={"issues": validation_issues, "can_proceed": len(validation_issues) == 0}
        )
        
        state = self._log_event(state, "validation_completed", {
            "issues": validation_issues,
            "can_proceed": len(validation_issues) == 0
        })
        
        if callback:
            await callback(state)
        
        return state
    
    async def _stage_submission(
        self,
        state: WorkflowStateData,
        auth_request: Any,
        callback=None
    ) -> WorkflowStateData:
        """Submit the prior authorization."""
        
        self._start_agent(state, "SubmissionAgent")
        
        # Build FHIR bundle
        evidence_dict = state.get("clinical_evidence", {}).get("evidence", {})
        
        class MockEvidence:
            def __init__(self, data):
                for k, v in data.items():
                    setattr(self, k, v)
        
        mock_evidence = MockEvidence(evidence_dict)
        
        # Create mock objects for FHIR bundle
        class MockAuthRequest:
            def __init__(self, state, auth):
                self.id = state["auth_id"]
                self.patient_id = state["patient_id"]
                self.cpt_code = state["cpt_code"]
                self.patient = auth.patient
        
        mock_auth = MockAuthRequest(state, auth_request)
        
        # Build FHIR bundle
        from models.schemas import PolicyMatchResult
        
        class MockPolicyMatch:
            def __init__(self, data):
                for k, v in data.items():
                    setattr(self, k, v)
        
        policy_match_data = state.get("policy_match", {})
        
        fhir_bundle = await self.submission.build_fhir_bundle(
            mock_auth,
            mock_evidence,
            MockPolicyMatch(policy_match_data)
        )
        
        # Submit
        submission_result = await self.submission.submit_prior_authorization(
            mock_auth,
            fhir_bundle
        )
        
        state["fhir_bundle"] = fhir_bundle
        state["submission_result"] = submission_result
        
        state["current_state"] = WorkflowState.SUBMISSION
        
        self._complete_agent(
            state, "SubmissionAgent",
            output={
                "external_id": submission_result.get("external_auth_id"),
                "status": submission_result.get("status")
            }
        )
        
        state = self._log_event(state, "submission_completed", {
            "external_id": submission_result.get("external_auth_id"),
            "status": submission_result.get("status")
        })
        
        if callback:
            await callback(state)
        
        return state
    
    async def _stage_monitoring(
        self,
        state: WorkflowStateData,
        callback=None
    ) -> WorkflowStateData:
        """Monitor submission and get decision (simulated)."""
        
        self._start_agent(state, "MonitoringAgent")
        
        submission_result = state.get("submission_result", {})
        decision = submission_result.get("decision", {})
        outcome = decision.get("outcome", submission_result.get("status", "pending"))
        
        if outcome == "approved":
            state["current_state"] = WorkflowState.APPROVED
        elif outcome == "denied":
            state["current_state"] = WorkflowState.DENIED
            state["denial_analysis"] = {
                "denial_reason": decision.get("reason", "Service not medically necessary")
            }
        else:
            state["current_state"] = WorkflowState.MONITORING
        
        self._complete_agent(
            state, "MonitoringAgent",
            output={"decision": outcome}
        )
        
        state = self._log_event(state, "decision_received", {"outcome": outcome})
        
        if callback:
            await callback(state)
        
        return state
    
    async def _handle_denial(
        self,
        state: WorkflowStateData,
        auth_request: Any,
        callback=None
    ) -> WorkflowStateData:
        """Handle denial - auto-generate appeal."""
        
        denial_reason = state.get("denial_analysis", {}).get("denial_reason", "Service not medically necessary")
        
        # Analyze denial
        evidence_dict = state.get("clinical_evidence", {}).get("evidence", {})
        
        class MockEvidence:
            def __init__(self, data):
                for k, v in data.items():
                    setattr(self, k, v)
        
        mock_evidence = MockEvidence(evidence_dict)
        
        denial_analysis = await self.appeal.analyze_denial(
            auth_request,
            denial_reason,
            mock_evidence,
            None
        )
        
        state["denial_analysis"] = denial_analysis
        state["current_state"] = WorkflowState.APPEAL_ANALYSIS
        
        # Generate appeal letter
        state = await self._generate_appeal(state, auth_request, callback)
        
        return state
    
    async def _generate_appeal(
        self,
        state: WorkflowStateData,
        auth_request: Any,
        callback=None
    ) -> WorkflowStateData:
        """Generate appeal letter."""
        
        self._start_agent(state, "AppealAgent")
        
        denial_analysis = state.get("denial_analysis", {})
        evidence_dict = state.get("clinical_evidence", {}).get("evidence", {})
        
        class MockEvidence:
            def __init__(self, data):
                for k, v in data.items():
                    setattr(self, k, v)
        
        mock_evidence = MockEvidence(evidence_dict)
        
        appeal_letter = await self.appeal.generate_appeal_letter(
            auth_request,
            denial_analysis,
            mock_evidence,
            None
        )
        
        state["appeal_letter"] = appeal_letter
        state["current_state"] = WorkflowState.APPEAL_GENERATION
        
        self._complete_agent(
            state, "AppealAgent",
            output={
                "word_count": len(appeal_letter.split()),
                "success_probability": denial_analysis.get("success_probability", 0.5)
            }
        )
        
        state = self._log_event(state, "appeal_generated", {
            "word_count": len(appeal_letter.split())
        })
        
        if callback:
            await callback(state)
        
        return state
    
    def _start_agent(self, state: WorkflowStateData, agent_name: str):
        """Mark an agent as started."""
        state["agents"][agent_name] = {
            "name": agent_name,
            "status": AgentStatus.RUNNING,
            "start_time": datetime.now(),
            "end_time": None,
            "input_data": {},
            "output_data": {},
            "reasoning_steps": [],
            "error": None,
            "tokens_used": 0
        }
        state["updated_at"] = datetime.now()
    
    def _complete_agent(
        self,
        state: WorkflowStateData,
        agent_name: str,
        output: Dict[str, Any]
    ):
        """Mark an agent as completed."""
        if agent_name in state["agents"]:
            state["agents"][agent_name]["status"] = AgentStatus.COMPLETED
            state["agents"][agent_name]["end_time"] = datetime.now()
            state["agents"][agent_name]["output_data"] = output
        
        state["updated_at"] = datetime.now()
    
    def _log_event(
        self,
        state: WorkflowStateData,
        event_type: str,
        data: Dict[str, Any]
    ) -> WorkflowStateData:
        """Log an event in the processing log."""
        state["processing_log"].append({
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "state": state["current_state"],
            "data": data
        })
        return state
    
    def _check_urgency(self, state: WorkflowStateData) -> bool:
        """Check if the request is urgent."""
        # Simple urgency check - in production, would analyze clinical notes
        return "urgent" in state.get("service_type", "").lower()
    
    def _compile_results(self, state: WorkflowStateData) -> Dict[str, Any]:
        """Compile final results from the workflow."""
        
        return {
            "auth_id": state["auth_id"],
            "status": state["current_state"],
            "clinical_evidence": state.get("clinical_evidence"),
            "policy_match": state.get("policy_match"),
            "submission_result": state.get("submission_result"),
            "denial_analysis": state.get("denial_analysis"),
            "appeal_letter": state.get("appeal_letter"),
            "agents": state["agents"],
            "processing_log": state["processing_log"],
            "error": state.get("error"),
            "completed_at": datetime.now().isoformat()
        }


def create_workflow(clinical_reader, policy, submission, appeal):
    """Factory function to create a workflow."""
    return AuthorizationWorkflow(clinical_reader, policy, submission, appeal)
