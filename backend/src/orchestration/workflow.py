"""
Orchestration Layer — AutoAuth Agent multi-agent workflow.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional, TypedDict
from enum import Enum


class WorkflowState(str, Enum):
    PENDING             = "pending"
    TRIAGE              = "triage"
    EVIDENCE_EXTRACTION = "evidence_extraction"
    POLICY_LOOKUP       = "policy_lookup"
    VALIDATION          = "validation"
    SUBMISSION          = "submission"
    MONITORING          = "monitoring"
    APPROVED            = "approved"
    DENIED              = "denied"
    APPEAL_ANALYSIS     = "appeal_analysis"
    APPEAL_GENERATION   = "appeal_generation"
    APPEAL_SUBMISSION   = "appeal_submission"
    COMPLETED           = "completed"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class AgentStatus(str, Enum):
    IDLE      = "idle"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    WAITING   = "waiting"


# ── Helper: wraps a list of dicts so agents can do entity.value ──────────────

class _EntityProxy:
    """Wraps a dict (serialised ExtractedEntity) so .value, .code etc. work."""
    def __init__(self, d: dict):
        self._d = d if isinstance(d, dict) else {}

    def __getattr__(self, name):
        try:
            return self._d[name]
        except KeyError:
            return None

    def __str__(self):
        return self._d.get("value", "")


class _EvidenceProxy:
    """
    Wraps the serialised clinical_evidence dict produced by workflow state.
    Ensures agents can do evidence.conditions[0].value without crashing.
    """
    def __init__(self, data: dict):
        self._data = data if isinstance(data, dict) else {}

    @property
    def clinical_summary(self) -> str:
        return self._data.get("clinical_summary", "")

    @property
    def extraction_confidence(self) -> float:
        return float(self._data.get("extraction_confidence", 0.5))

    def _wrap_list(self, key: str) -> list:
        raw = self._data.get(key) or []
        return [_EntityProxy(x) if isinstance(x, dict) else x for x in raw]

    @property
    def conditions(self):   return self._wrap_list("conditions")
    @property
    def procedures(self):   return self._wrap_list("procedures")
    @property
    def medications(self):  return self._wrap_list("medications")
    @property
    def lab_results(self):  return self._wrap_list("lab_results")
    @property
    def vital_signs(self):  return self._wrap_list("vital_signs")
    @property
    def allergies(self):    return self._wrap_list("allergies")


class _PolicyMatchProxy:
    """Wraps the serialised policy_match dict."""
    def __init__(self, data: dict):
        self._d = data if isinstance(data, dict) else {}

    def __getattr__(self, name):
        try:
            return self._d[name]
        except KeyError:
            return None

    @property
    def is_covered(self) -> bool:
        return bool(self._d.get("is_covered", False))

    @property
    def match_score(self) -> float:
        return float(self._d.get("match_score", 0.0))

    @property
    def policy_name(self) -> str:
        return self._d.get("policy_name", "")

    @property
    def satisfied_requirements(self) -> list:
        return self._d.get("satisfied_requirements", [])

    @property
    def missing_requirements(self) -> list:
        return self._d.get("missing_requirements", [])


# ── Main workflow class ───────────────────────────────────────────────────────

class AuthorizationWorkflow:
    def __init__(self, clinical_reader_agent, policy_agent, submission_agent, appeal_agent):
        self.clinical_reader = clinical_reader_agent
        self.policy          = policy_agent
        self.submission      = submission_agent
        self.appeal          = appeal_agent

    async def execute_workflow(
        self,
        auth_request: Any,
        clinical_notes: List[Any],
        callback=None
    ) -> Dict[str, Any]:

        state = self._initialize_state(auth_request)

        try:
            state = await self._stage_triage(state, callback)
            state = await self._stage_evidence_extraction(state, clinical_notes, callback)
            state = await self._stage_policy_lookup(state, auth_request, callback)
            state = await self._stage_validation(state, callback)
            state = await self._stage_submission(state, auth_request, callback)
            state = await self._stage_monitoring(state, callback)

            if state["current_state"] == WorkflowState.DENIED:
                state = await self._handle_denial(state, auth_request, callback)

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[WORKFLOW EXCEPTION] {tb}")
            state["error"] = str(e)
            state["current_state"] = WorkflowState.REQUIRES_HUMAN_REVIEW
            state = self._log_event(state, "error", {"error": str(e), "traceback": tb})
            if callback:
                await callback(state)

        return self._compile_results(state)

    # ── Stage implementations ─────────────────────────────────────────────────

    async def _stage_triage(self, state, callback=None):
        self._start_agent(state, "TriageAgent")
        is_urgent = "urgent" in str(state.get("service_type", "")).lower()
        state["current_state"] = WorkflowState.TRIAGE
        self._complete_agent(state, "TriageAgent", {"is_urgent": is_urgent, "priority": "urgent" if is_urgent else "standard"})
        state = self._log_event(state, "triage_completed", {"is_urgent": is_urgent})
        if callback: await callback(state)
        return state

    async def _stage_evidence_extraction(self, state, clinical_notes, callback=None):
        self._start_agent(state, "ClinicalReaderAgent")

        clinical_evidence = await self.clinical_reader.extract_clinical_evidence(
            clinical_notes,
            state["patient_id"],
            state["service_type"],
            state["cpt_code"]
        )

        necessity_analysis = await self.clinical_reader.analyze_medical_necessity(
            clinical_evidence,
            state["service_type"],
            state["cpt_code"]
        )

        # Store as serialisable dict
        evidence_dict = clinical_evidence.model_dump() if hasattr(clinical_evidence, "model_dump") else vars(clinical_evidence)
        state["clinical_evidence"] = {
            "evidence": evidence_dict,
            "necessity_analysis": necessity_analysis
        }
        state["current_state"] = WorkflowState.EVIDENCE_EXTRACTION

        self._complete_agent(state, "ClinicalReaderAgent", {
            "conditions_found": len(clinical_evidence.conditions),
            "confidence": clinical_evidence.extraction_confidence,
            "summary": (clinical_evidence.clinical_summary or "")[:200]
        })
        state = self._log_event(state, "evidence_extraction_completed", {
            "conditions": len(clinical_evidence.conditions),
            "confidence": clinical_evidence.extraction_confidence
        })
        if callback: await callback(state)
        return state

    async def _stage_policy_lookup(self, state, auth_request, callback=None):
        self._start_agent(state, "PolicyAgent")

        payer_name = "Blue Cross Blue Shield"
        if auth_request.patient:
            payer_name = getattr(auth_request.patient, "payer_name", payer_name)

        policy_req = await self.policy.retrieve_policy_requirements(
            payer_name,
            state["service_type"],
            state["cpt_code"]
        )

        # Use the proxy to safely wrap the serialised evidence
        evidence_dict = state.get("clinical_evidence", {}).get("evidence", {})
        evidence_proxy = _EvidenceProxy(evidence_dict)

        policy_match = await self.policy.match_policy(
            evidence_proxy,
            policy_req,
            payer_name
        )

        state["policy_requirements"] = policy_req.model_dump() if hasattr(policy_req, "model_dump") else {}
        state["policy_match"]        = policy_match.model_dump() if hasattr(policy_match, "model_dump") else {}
        state["current_state"] = WorkflowState.POLICY_LOOKUP

        self._complete_agent(state, "PolicyAgent", {
            "policy_id":   policy_req.requirement_id,
            "match_score": policy_match.match_score,
            "is_covered":  policy_match.is_covered
        })
        state = self._log_event(state, "policy_lookup_completed", {
            "match_score": policy_match.match_score,
            "is_covered":  policy_match.is_covered
        })
        if callback: await callback(state)
        return state

    async def _stage_validation(self, state, callback=None):
        self._start_agent(state, "ValidationAgent")

        issues = []
        if not state.get("clinical_evidence"):
            issues.append("Missing clinical evidence")
        if not state.get("policy_match"):
            issues.append("Missing policy match")

        # Always proceed to submission even if policy not fully met
        state["current_state"] = WorkflowState.VALIDATION

        self._complete_agent(state, "ValidationAgent", {
            "issues": issues,
            "can_proceed": True  # always submit; payer makes the final decision
        })
        state = self._log_event(state, "validation_completed", {"issues": issues})
        if callback: await callback(state)
        return state

    async def _stage_submission(self, state, auth_request, callback=None):
        self._start_agent(state, "SubmissionAgent")

        evidence_dict  = state.get("clinical_evidence", {}).get("evidence", {})
        evidence_proxy = _EvidenceProxy(evidence_dict)
        policy_dict    = state.get("policy_match", {})
        policy_proxy   = _PolicyMatchProxy(policy_dict)

        # Build a minimal mock auth for the submission agent
        class _SubmissionAuth:
            def __init__(self, s, auth):
                self.id          = s["auth_id"]
                self.patient_id  = s["patient_id"]
                self.cpt_code    = s["cpt_code"]
                self.patient     = auth.patient
                self.policy_match = policy_proxy   # ← was missing before

        submission_auth = _SubmissionAuth(state, auth_request)

        fhir_bundle = await self.submission.build_fhir_bundle(
            submission_auth, evidence_proxy, policy_proxy
        )

        submission_result = await self.submission.submit_prior_authorization(
            submission_auth, fhir_bundle
        )

        state["fhir_bundle"]       = fhir_bundle
        state["submission_result"] = submission_result
        state["current_state"]     = WorkflowState.SUBMISSION

        self._complete_agent(state, "SubmissionAgent", {
            "external_id": submission_result.get("external_auth_id"),
            "status":      submission_result.get("status")
        })
        state = self._log_event(state, "submission_completed", {
            "external_id": submission_result.get("external_auth_id"),
            "status":      submission_result.get("status")
        })
        if callback: await callback(state)
        return state

    async def _stage_monitoring(self, state, callback=None):
        self._start_agent(state, "MonitoringAgent")

        result   = state.get("submission_result", {})
        decision = result.get("decision", {})
        outcome  = decision.get("outcome") or result.get("status") or "pending"
        outcome  = str(outcome).lower()

        if outcome == "approved":
            state["current_state"] = WorkflowState.APPROVED
        elif outcome == "denied":
            state["current_state"] = WorkflowState.DENIED
            state["denial_analysis"] = {
                "denial_reason": decision.get("reason") or "Service not medically necessary"
            }
        else:
            # pending → treat as approved for demo so UI doesn't hang
            state["current_state"] = WorkflowState.APPROVED

        self._complete_agent(state, "MonitoringAgent", {"decision": outcome})
        state = self._log_event(state, "decision_received", {"outcome": outcome})
        if callback: await callback(state)
        return state

    async def _handle_denial(self, state, auth_request, callback=None):
        denial_reason  = state.get("denial_analysis", {}).get("denial_reason", "Service not medically necessary")
        evidence_dict  = state.get("clinical_evidence", {}).get("evidence", {})
        evidence_proxy = _EvidenceProxy(evidence_dict)
        policy_dict    = state.get("policy_match", {})
        policy_proxy   = _PolicyMatchProxy(policy_dict)

        denial_analysis = await self.appeal.analyze_denial(
            auth_request, denial_reason, evidence_proxy, policy_proxy
        )
        state["denial_analysis"] = denial_analysis
        state["current_state"]   = WorkflowState.APPEAL_ANALYSIS

        state = await self._generate_appeal(state, auth_request, callback)
        return state

    async def _generate_appeal(self, state, auth_request, callback=None):
        self._start_agent(state, "AppealAgent")

        denial_analysis = state.get("denial_analysis", {})
        evidence_proxy  = _EvidenceProxy(state.get("clinical_evidence", {}).get("evidence", {}))
        policy_proxy    = _PolicyMatchProxy(state.get("policy_match", {}))

        appeal_letter = await self.appeal.generate_appeal_letter(
            auth_request, denial_analysis, evidence_proxy, policy_proxy
        )

        state["appeal_letter"]   = appeal_letter
        state["current_state"]   = WorkflowState.APPEAL_GENERATION

        self._complete_agent(state, "AppealAgent", {
            "word_count":         len(appeal_letter.split()),
            "success_probability": denial_analysis.get("success_probability", 0.5)
        })
        state = self._log_event(state, "appeal_generated", {"word_count": len(appeal_letter.split())})
        if callback: await callback(state)
        return state

    # ── Agent lifecycle helpers ───────────────────────────────────────────────

    def _start_agent(self, state, agent_name: str):
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

    def _complete_agent(self, state, agent_name: str, output: dict):
        if agent_name in state["agents"]:
            state["agents"][agent_name]["status"]      = AgentStatus.COMPLETED
            state["agents"][agent_name]["end_time"]    = datetime.now()
            state["agents"][agent_name]["output_data"] = output
        state["updated_at"] = datetime.now()

    def _log_event(self, state, event_type: str, data: dict):
        state["processing_log"].append({
            "timestamp":  datetime.now().isoformat(),
            "event_type": event_type,
            "state":      str(state["current_state"]),
            "data":       data
        })
        return state

    def _initialize_state(self, auth_request) -> dict:
        return {
            "auth_id":              auth_request.id,
            "patient_id":           auth_request.patient_id,
            "service_type":         auth_request.service_type,
            "cpt_code":             auth_request.cpt_code,
            "icd10_code":           auth_request.icd10_code,
            "current_state":        WorkflowState.PENDING,
            "target_state":         None,
            "clinical_evidence":    None,
            "policy_requirements":  None,
            "policy_match":         None,
            "fhir_bundle":          None,
            "submission_result":    None,
            "denial_analysis":      None,
            "appeal_letter":        None,
            "agents":               {},
            "error":                None,
            "created_at":           datetime.now(),
            "updated_at":           datetime.now(),
            "processing_log":       []
        }

    def _compile_results(self, state: dict) -> dict:
        return {
            "auth_id":          state["auth_id"],
            "status":           state["current_state"],
            "current_state":    state["current_state"],
            "clinical_evidence": state.get("clinical_evidence"),
            "policy_match":      state.get("policy_match"),
            "submission_result": state.get("submission_result"),
            "denial_analysis":   state.get("denial_analysis"),
            "appeal_letter":     state.get("appeal_letter"),
            "agents":            state["agents"],
            "processing_log":    state["processing_log"],
            "error":             state.get("error"),
            "completed_at":      datetime.now().isoformat()
        }


def create_workflow(clinical_reader, policy, submission, appeal):
    return AuthorizationWorkflow(clinical_reader, policy, submission, appeal)