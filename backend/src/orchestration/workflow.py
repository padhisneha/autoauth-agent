"""
Orchestration Layer — AutoAuth Agent multi-agent workflow.
Includes appeal resubmission to the FHIR/Payer server.
"""

from datetime import datetime
from typing import Dict, Any, List
from enum import Enum


class WorkflowState(str, Enum):
    PENDING               = "pending"
    TRIAGE                = "triage"
    EVIDENCE_EXTRACTION   = "evidence_extraction"
    POLICY_LOOKUP         = "policy_lookup"
    VALIDATION            = "validation"
    SUBMISSION            = "submission"
    MONITORING            = "monitoring"
    APPROVED              = "approved"
    DENIED                = "denied"
    APPEAL_ANALYSIS       = "appeal_analysis"
    APPEAL_GENERATION     = "appeal_generation"
    APPEAL_SUBMISSION     = "appeal_submission"
    APPEAL_APPROVED       = "appeal_approved"
    APPEAL_DENIED         = "appeal_denied"
    COMPLETED             = "completed"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class AgentStatus(str, Enum):
    IDLE = "idle"; RUNNING = "running"; COMPLETED = "completed"
    FAILED = "failed"; WAITING = "waiting"


class _EntityProxy:
    def __init__(self, d):
        self._d = d if isinstance(d, dict) else {}
    def __getattr__(self, n):
        try: return self._d[n]
        except KeyError: return None
    def __str__(self): return self._d.get("value", "")


class _EvidenceProxy:
    def __init__(self, data):
        self._data = data if isinstance(data, dict) else {}
    @property
    def clinical_summary(self): return self._data.get("clinical_summary", "")
    @property
    def extraction_confidence(self): return float(self._data.get("extraction_confidence", 0.5))
    def _wrap(self, key):
        return [_EntityProxy(x) if isinstance(x, dict) else x for x in (self._data.get(key) or [])]
    @property
    def conditions(self):  return self._wrap("conditions")
    @property
    def procedures(self):  return self._wrap("procedures")
    @property
    def medications(self): return self._wrap("medications")
    @property
    def lab_results(self): return self._wrap("lab_results")
    @property
    def vital_signs(self): return self._wrap("vital_signs")
    @property
    def allergies(self):   return self._wrap("allergies")


class _PolicyProxy:
    def __init__(self, d):
        self._d = d if isinstance(d, dict) else {}
    def __getattr__(self, n):
        try: return self._d[n]
        except KeyError: return None
    @property
    def is_covered(self): return bool(self._d.get("is_covered", False))
    @property
    def match_score(self): return float(self._d.get("match_score", 0.0))
    @property
    def policy_name(self): return self._d.get("policy_name", "")
    @property
    def satisfied_requirements(self): return self._d.get("satisfied_requirements", [])
    @property
    def missing_requirements(self): return self._d.get("missing_requirements", [])


class AuthorizationWorkflow:
    def __init__(self, clinical_reader, policy, submission, appeal):
        self.clinical_reader = clinical_reader
        self.policy = policy
        self.submission = submission
        self.appeal = appeal

    async def execute_workflow(self, auth_request, clinical_notes, callback=None):
        state = self._init(auth_request)
        try:
            state = await self._triage(state, callback)
            state = await self._evidence(state, clinical_notes, callback)
            state = await self._policy_lookup(state, auth_request, callback)
            state = await self._validation(state, callback)
            state = await self._submission(state, auth_request, callback)
            state = await self._monitoring(state, callback)

            if state["current_state"] == WorkflowState.DENIED:
                state = await self._appeal_generate(state, auth_request, callback)
                state = await self._appeal_submit(state, auth_request, callback)

        except Exception as e:
            import traceback
            print(f"[WORKFLOW ERROR]\n{traceback.format_exc()}")
            state["error"] = str(e)
            state["current_state"] = WorkflowState.REQUIRES_HUMAN_REVIEW
            state = self._log(state, "error", {"error": str(e)})
            if callback: await callback(state)

        return self._compile(state)

    # ── Stages ──────────────────────────────────────────────────────────────

    async def _triage(self, state, cb):
        self._start(state, "TriageAgent")
        urgent = "urgent" in str(state.get("service_type", "")).lower()
        state["current_state"] = WorkflowState.TRIAGE
        self._done(state, "TriageAgent", {"is_urgent": urgent})
        state = self._log(state, "triage_completed", {"is_urgent": urgent})
        if cb: await cb(state)
        return state

    async def _evidence(self, state, notes, cb):
        self._start(state, "ClinicalReaderAgent")
        ev = await self.clinical_reader.extract_clinical_evidence(
            notes, state["patient_id"], state["service_type"], state["cpt_code"])
        na = await self.clinical_reader.analyze_medical_necessity(
            ev, state["service_type"], state["cpt_code"])
        ev_dict = ev.model_dump() if hasattr(ev, "model_dump") else vars(ev)
        state["clinical_evidence"] = {"evidence": ev_dict, "necessity_analysis": na}
        state["current_state"] = WorkflowState.EVIDENCE_EXTRACTION
        self._done(state, "ClinicalReaderAgent", {
            "conditions_found": len(ev.conditions),
            "confidence": ev.extraction_confidence,
            "summary": (ev.clinical_summary or "")[:200]
        })
        state = self._log(state, "evidence_done", {"conditions": len(ev.conditions)})
        if cb: await cb(state)
        return state

    async def _policy_lookup(self, state, auth_req, cb):
        self._start(state, "PolicyAgent")
        payer = getattr(getattr(auth_req, "patient", None), "payer_name", "Blue Cross Blue Shield")
        req = await self.policy.retrieve_policy_requirements(payer, state["service_type"], state["cpt_code"])
        ev  = _EvidenceProxy(state.get("clinical_evidence", {}).get("evidence", {}))
        pm  = await self.policy.match_policy(ev, req, payer)
        state["policy_requirements"] = req.model_dump() if hasattr(req, "model_dump") else {}
        state["policy_match"] = pm.model_dump() if hasattr(pm, "model_dump") else {}
        state["current_state"] = WorkflowState.POLICY_LOOKUP
        self._done(state, "PolicyAgent", {"match_score": pm.match_score, "is_covered": pm.is_covered})
        state = self._log(state, "policy_done", {"match_score": pm.match_score})
        if cb: await cb(state)
        return state

    async def _validation(self, state, cb):
        self._start(state, "ValidationAgent")
        state["current_state"] = WorkflowState.VALIDATION
        self._done(state, "ValidationAgent", {"can_proceed": True})
        state = self._log(state, "validation_done", {})
        if cb: await cb(state)
        return state

    async def _submission(self, state, auth_req, cb):
        self._start(state, "SubmissionAgent")
        ev = _EvidenceProxy(state.get("clinical_evidence", {}).get("evidence", {}))
        pm = _PolicyProxy(state.get("policy_match", {}))

        class _Auth:
            def __init__(self, s, a):
                self.id = s["auth_id"]; self.patient_id = s["patient_id"]
                self.cpt_code = s["cpt_code"]; self.patient = a.patient
                self.policy_match = pm

        sa = _Auth(state, auth_req)
        bundle = await self.submission.build_fhir_bundle(sa, ev, pm)
        result = await self.submission.submit_prior_authorization(sa, bundle)
        state["fhir_bundle"] = bundle
        state["submission_result"] = result
        state["current_state"] = WorkflowState.SUBMISSION
        self._done(state, "SubmissionAgent", {
            "external_id": result.get("external_auth_id"),
            "claim_id": result.get("claim_response_id"),
            "status": result.get("status")
        })
        state = self._log(state, "submission_done", {"status": result.get("status")})
        if cb: await cb(state)
        return state

    async def _monitoring(self, state, cb):
        self._start(state, "MonitoringAgent")
        res = state.get("submission_result", {})
        dec = res.get("decision", {})
        outcome = str(dec.get("outcome") or res.get("status") or "approved").lower()

        if outcome == "approved":
            state["current_state"] = WorkflowState.APPROVED
        else:
            state["current_state"] = WorkflowState.DENIED
            state["denial_analysis"] = {
                "denial_reason": dec.get("reason") or "Service not medically necessary"
            }

        self._done(state, "MonitoringAgent", {"decision": outcome})
        state = self._log(state, "decision_received", {"outcome": outcome})
        if cb: await cb(state)
        return state

    async def _appeal_generate(self, state, auth_req, cb):
        """Analyse denial and generate an LLM appeal letter."""
        denial = state.get("denial_analysis", {}).get("denial_reason", "Not medically necessary")
        ev  = _EvidenceProxy(state.get("clinical_evidence", {}).get("evidence", {}))
        pm  = _PolicyProxy(state.get("policy_match", {}))

        analysis = await self.appeal.analyze_denial(auth_req, denial, ev, pm)
        state["denial_analysis"] = analysis
        state["current_state"]   = WorkflowState.APPEAL_ANALYSIS
        if cb: await cb(state)

        self._start(state, "AppealAgent")
        letter = await self.appeal.generate_appeal_letter(auth_req, analysis, ev, pm)
        state["appeal_letter"]   = letter
        state["current_state"]   = WorkflowState.APPEAL_GENERATION
        self._done(state, "AppealAgent", {
            "word_count": len(letter.split()),
            "success_probability": analysis.get("success_probability", 0.5)
        })
        state = self._log(state, "appeal_generated", {"word_count": len(letter.split())})
        if cb: await cb(state)
        return state

    async def _appeal_submit(self, state, auth_req, cb):
        """Submit the appeal (with letter) back to the FHIR/Payer server."""
        self._start(state, "AppealSubmissionAgent")
        state["current_state"] = WorkflowState.APPEAL_SUBMISSION
        if cb: await cb(state)

        pm = _PolicyProxy(state.get("policy_match", {}))

        class _AppealAuth:
            def __init__(self, s, a):
                self.id = s["auth_id"] + "-APPEAL"
                self.patient_id = s["patient_id"]
                self.cpt_code = s["cpt_code"]
                self.patient = a.patient
                self.policy_match = pm

        aa = _AppealAuth(state, auth_req)
        result = await self.submission.submit_appeal(
            aa,
            state.get("fhir_bundle", {}),
            state.get("appeal_letter", "")
        )
        state["appeal_submission_result"] = result
        # Final state depends on whether FHIR server is live; keep as APPEAL_SUBMISSION
        # so the frontend shows it clearly
        state["current_state"] = WorkflowState.APPEAL_SUBMISSION

        self._done(state, "AppealSubmissionAgent", {
            "claim_id": result.get("claim_response_id"),
            "status":   result.get("status", "submitted"),
            "message":  result.get("message", "Appeal submitted to payer for review")
        })
        state = self._log(state, "appeal_submitted", {"claim_id": result.get("claim_response_id")})
        if cb: await cb(state)
        return state

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _start(self, state, name):
        state["agents"][name] = {
            "name": name, "status": AgentStatus.RUNNING,
            "start_time": datetime.now(), "end_time": None,
            "input_data": {}, "output_data": {}, "reasoning_steps": [],
            "error": None, "tokens_used": 0
        }
        state["updated_at"] = datetime.now()

    def _done(self, state, name, output):
        if name in state["agents"]:
            state["agents"][name]["status"]      = AgentStatus.COMPLETED
            state["agents"][name]["end_time"]    = datetime.now()
            state["agents"][name]["output_data"] = output
        state["updated_at"] = datetime.now()

    def _log(self, state, event, data):
        state["processing_log"].append({
            "timestamp": datetime.now().isoformat(),
            "event_type": event,
            "state": str(state["current_state"]),
            "data": data
        })
        return state

    def _init(self, auth_req):
        return {
            "auth_id": auth_req.id, "patient_id": auth_req.patient_id,
            "service_type": auth_req.service_type, "cpt_code": auth_req.cpt_code,
            "icd10_code": auth_req.icd10_code,
            "current_state": WorkflowState.PENDING, "target_state": None,
            "clinical_evidence": None, "policy_requirements": None,
            "policy_match": None, "fhir_bundle": None,
            "submission_result": None, "denial_analysis": None,
            "appeal_letter": None, "appeal_submission_result": None,
            "agents": {}, "error": None,
            "created_at": datetime.now(), "updated_at": datetime.now(),
            "processing_log": []
        }

    def _compile(self, state):
        return {
            "auth_id": state["auth_id"],
            "status": state["current_state"],
            "current_state": state["current_state"],
            "clinical_evidence": state.get("clinical_evidence"),
            "policy_match": state.get("policy_match"),
            "submission_result": state.get("submission_result"),
            "denial_analysis": state.get("denial_analysis"),
            "appeal_letter": state.get("appeal_letter"),
            "appeal_submission_result": state.get("appeal_submission_result"),
            "agents": state["agents"],
            "processing_log": state["processing_log"],
            "error": state.get("error"),
            "completed_at": datetime.now().isoformat()
        }


def create_workflow(cr, policy, submission, appeal):
    return AuthorizationWorkflow(cr, policy, submission, appeal)
