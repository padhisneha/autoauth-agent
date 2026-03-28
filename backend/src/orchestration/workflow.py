"""
Orchestration Layer — AutoAuth Agent multi-agent workflow with Prediction Engine.

Flow:
  Triage → Evidence → Policy → 🔮 Prediction → Decision Engine
     → [if high prob] Submit → Payer → approved ✓
     → [if low prob]  Generate appeal EARLY → Submit + attach justification → Payer
        → if denied → instantly resubmit appeal (already ready)
        → if approved → ✓
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
    PREDICTION            = "prediction"
    DECISION_ENGINE       = "decision_engine"
    PREEMPTIVE_APPEAL     = "preemptive_appeal"   # NEW — appeal generated before submission
    SUBMISSION            = "submission"
    MONITORING            = "monitoring"
    APPROVED              = "approved"
    DENIED                = "denied"
    APPEAL_ANALYSIS       = "appeal_analysis"
    APPEAL_GENERATION     = "appeal_generation"
    APPEAL_SUBMISSION     = "appeal_submission"
    APPEAL_MONITORING     = "appeal_monitoring"   # NEW — polls for appeal decision
    APPEAL_APPROVED       = "appeal_approved"
    APPEAL_DENIED         = "appeal_denied"
    COMPLETED             = "completed"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class AgentStatus(str, Enum):
    IDLE = "idle"; RUNNING = "running"; COMPLETED = "completed"
    FAILED = "failed"; WAITING = "waiting"


# ── Proxy helpers ─────────────────────────────────────────────────────────────

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


# ── Workflow ──────────────────────────────────────────────────────────────────

class AuthorizationWorkflow:
    LOW_PROB_THRESHOLD  = 0.55   # below this → preemptive appeal path
    HIGH_PROB_THRESHOLD = 0.75   # above this → confident direct submit

    def __init__(self, clinical_reader, policy, submission, appeal):
        self.clinical_reader = clinical_reader
        self.policy          = policy
        self.submission      = submission
        self.appeal          = appeal

    async def execute_workflow(self, auth_request, clinical_notes, callback=None):
        state = self._init(auth_request)
        try:
            # ── Core pipeline ──────────────────────────────────────────────
            state = await self._triage(state, callback)
            state = await self._evidence(state, clinical_notes, callback)
            state = await self._policy_lookup(state, auth_request, callback)
            state = await self._validation(state, callback)

            # ── Prediction Engine ──────────────────────────────────────────
            state = await self._prediction(state, auth_request, callback)
            state = await self._decision_engine(state, auth_request, callback)

            # ── Submission (with or without preemptive appeal) ─────────────
            state = await self._submission(state, auth_request, callback)
            state = await self._monitoring(state, callback)

            # ── Handle payer decision ──────────────────────────────────────
            if state["current_state"] == WorkflowState.APPROVED:
                pass  # done

            elif state["current_state"] == WorkflowState.MONITORING:
                pass  # still awaiting payer — poll timed out, payer portal still open

            elif state["current_state"] == WorkflowState.DENIED:
                # If preemptive appeal already generated → skip generation, go straight to submission
                if state.get("appeal_letter"):
                    # Appeal was pre-generated; just resubmit immediately
                    state["current_state"] = WorkflowState.APPEAL_ANALYSIS
                    if callback: await callback(state)
                    state = await self._appeal_submit(state, auth_request, callback)
                else:
                    # Standard path: analyse denial, generate letter, then submit
                    state = await self._appeal_generate(state, auth_request, callback)
                    state = await self._appeal_submit(state, auth_request, callback)

                # Poll FHIR server for appeal decision
                state = await self._appeal_monitoring(state, callback)

        except Exception as e:
            import traceback
            print(f"[WORKFLOW ERROR]\n{traceback.format_exc()}")
            state["error"] = str(e)
            state["current_state"] = WorkflowState.REQUIRES_HUMAN_REVIEW
            state = self._log(state, "error", {"error": str(e)})
            if callback: await callback(state)

        return self._compile(state)

    # ── Stages ───────────────────────────────────────────────────────────────

    async def _triage(self, state, cb):
        self._start(state, "TriageAgent")
        urgent = "urgent" in str(state.get("service_type", "")).lower()
        state["current_state"] = WorkflowState.TRIAGE
        self._done(state, "TriageAgent", {"is_urgent": urgent, "priority": "urgent" if urgent else "standard"})
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
            "confidence": round(ev.extraction_confidence, 2),
            "summary": (ev.clinical_summary or "")[:150]
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
        state["policy_match"]        = pm.model_dump() if hasattr(pm, "model_dump") else {}
        state["current_state"] = WorkflowState.POLICY_LOOKUP
        self._done(state, "PolicyAgent", {
            "match_score": round(pm.match_score, 2),
            "is_covered": pm.is_covered,
            "missing": len(pm.missing_requirements)
        })
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

    async def _prediction(self, state, auth_req, cb):
        """
        🔮 Prediction Engine — scores approval probability using:
        - Policy match score
        - Clinical evidence completeness
        - Medical necessity score
        - Payer strictness heuristic
        """
        self._start(state, "PredictionAgent")
        state["current_state"] = WorkflowState.PREDICTION

        pm_data = state.get("policy_match", {})
        ev_data = state.get("clinical_evidence", {})
        na      = ev_data.get("necessity_analysis", {})

        match_score       = float(pm_data.get("match_score", 0.5))
        is_covered        = bool(pm_data.get("is_covered", False))
        missing_count     = len(pm_data.get("missing_requirements", []))
        satisfied_count   = len(pm_data.get("satisfied_requirements", []))
        necessity_score   = float(na.get("necessity_score", 0.5))
        na_recommendation = na.get("recommendation", "needs_review")

        # Payer strictness (from historical denial rates)
        payer = getattr(getattr(auth_req, "patient", None), "payer_name", "")
        payer_factor = {
            "Blue Cross Blue Shield": 0.0,
            "Aetna": -0.05,
            "UnitedHealthcare": -0.05,
            "Cigna": -0.08,
            "Medicare": 0.02,
        }.get(payer, -0.03)

        # Weighted approval probability
        base = (match_score * 0.4) + (necessity_score * 0.35) + (0.1 if is_covered else 0.0)
        doc_bonus  = min(satisfied_count * 0.04, 0.15)
        doc_penalty= min(missing_count  * 0.06, 0.20)
        approval_probability = max(0.05, min(0.95, base + doc_bonus - doc_penalty + payer_factor))

        # Confidence band
        if approval_probability >= self.HIGH_PROB_THRESHOLD:
            risk_level = "low"
            strategy   = "direct_submit"
            reasoning  = f"Strong policy match ({match_score:.0%}) and necessity score ({necessity_score:.0%}). Confident approval expected."
        elif approval_probability >= self.LOW_PROB_THRESHOLD:
            risk_level = "medium"
            strategy   = "submit_with_justification"
            reasoning  = f"Moderate approval probability. Will submit with enhanced clinical justification to strengthen the request."
        else:
            risk_level = "high"
            strategy   = "preemptive_appeal"
            reasoning  = f"Low approval probability ({approval_probability:.0%}) due to {missing_count} unmet criteria. Generating appeal proactively before submission."

        prediction = {
            "approval_probability": round(approval_probability, 3),
            "risk_level":           risk_level,
            "strategy":             strategy,
            "reasoning":            reasoning,
            "policy_match_score":   round(match_score, 2),
            "necessity_score":      round(necessity_score, 2),
            "missing_criteria":     missing_count,
            "satisfied_criteria":   satisfied_count,
            "payer":                payer,
        }
        state["prediction"] = prediction

        self._done(state, "PredictionAgent", {
            "approval_probability": f"{approval_probability:.0%}",
            "risk_level": risk_level,
            "strategy": strategy,
        })
        state = self._log(state, "prediction_complete", prediction)
        if cb: await cb(state)
        return state

    async def _decision_engine(self, state, auth_req, cb):
        """
        🧠 Decision Engine — acts on the prediction:
        - HIGH prob  → submit directly
        - MEDIUM prob → submit with extra clinical justification note
        - LOW prob   → generate appeal letter NOW before submitting, attach to submission
        """
        self._start(state, "DecisionEngine")
        state["current_state"] = WorkflowState.DECISION_ENGINE

        prediction = state.get("prediction", {})
        strategy   = prediction.get("strategy", "direct_submit")
        prob       = prediction.get("approval_probability", 0.5)

        if strategy == "preemptive_appeal":
            # Generate appeal letter NOW — before any denial
            state["current_state"] = WorkflowState.PREEMPTIVE_APPEAL
            if cb: await cb(state)

            ev = _EvidenceProxy(state.get("clinical_evidence", {}).get("evidence", {}))
            pm = _PolicyProxy(state.get("policy_match", {}))

            # Create a synthetic denial analysis for the preemptive letter
            preemptive_denial = {
                "denial_reason": f"Anticipated denial: {', '.join(pm.missing_requirements[:2]) or 'incomplete documentation'}",
                "primary_appeal_argument": "Proactive documentation package demonstrates full medical necessity per payer policy criteria.",
                "supporting_evidence": [],
                "urgency_indicators": [],
                "peer_review_recommended": True,
                "success_probability": min(prob + 0.2, 0.85)
            }

            self._start(state, "AppealAgent")
            appeal_letter = await self.appeal.generate_appeal_letter(auth_req, preemptive_denial, ev, pm)
            state["appeal_letter"]    = appeal_letter
            state["denial_analysis"]  = preemptive_denial
            state["preemptive_appeal"] = True
            self._done(state, "AppealAgent", {
                "word_count": len(appeal_letter.split()),
                "type": "preemptive",
                "success_probability": f"{preemptive_denial['success_probability']:.0%}"
            })
            state = self._log(state, "preemptive_appeal_generated", {
                "word_count": len(appeal_letter.split()),
                "strategy": "preemptive"
            })

        self._done(state, "DecisionEngine", {
            "strategy":    strategy,
            "probability": f"{prob:.0%}",
            "action":      "Appeal pre-generated" if strategy == "preemptive_appeal" else "Proceeding with submission"
        })
        state["current_state"] = WorkflowState.DECISION_ENGINE
        state = self._log(state, "decision_engine_complete", {"strategy": strategy})
        if cb: await cb(state)
        return state

    async def _submission(self, state, auth_req, cb):
        self._start(state, "SubmissionAgent")
        ev  = _EvidenceProxy(state.get("clinical_evidence", {}).get("evidence", {}))
        pm  = _PolicyProxy(state.get("policy_match", {}))
        preemptive_appeal = state.get("appeal_letter") if state.get("preemptive_appeal") else None

        class _Auth:
            def __init__(self, s, a):
                self.id = s["auth_id"]; self.patient_id = s["patient_id"]
                self.cpt_code = s["cpt_code"]; self.patient = a.patient
                self.policy_match = pm

        sa     = _Auth(state, auth_req)
        bundle = await self.submission.build_fhir_bundle(sa, ev, pm, appeal_letter=preemptive_appeal)
        result = await self.submission.submit_prior_authorization(sa, bundle)
        state["fhir_bundle"]       = bundle
        state["submission_result"] = result
        state["current_state"]     = WorkflowState.SUBMISSION
        self._done(state, "SubmissionAgent", {
            "claim_id": result.get("claim_response_id"),
            "status":   result.get("status"),
            "strategy": "preemptive_appeal_attached" if preemptive_appeal else "standard"
        })
        state = self._log(state, "submission_done", {"status": result.get("status")})
        if cb: await cb(state)
        return state

    async def _monitoring(self, state, cb):
        self._start(state, "MonitoringAgent")
        res     = state.get("submission_result", {})
        dec     = res.get("decision", {})
        outcome = str(dec.get("outcome") or res.get("status") or "pending").lower()

        if outcome == "approved":
            state["current_state"] = WorkflowState.APPROVED
            self._done(state, "MonitoringAgent", {"decision": "approved"})
        elif outcome == "denied":
            state["current_state"] = WorkflowState.DENIED
            existing_denial = state.get("denial_analysis", {})
            state["denial_analysis"] = {
                **existing_denial,
                "denial_reason": dec.get("reason") or "Service not medically necessary"
            }
            self._done(state, "MonitoringAgent", {"decision": "denied"})
        else:
            # pending / timeout — payer hasn't decided yet
            # Keep state as MONITORING so the UI shows "Awaiting payer review"
            state["current_state"] = WorkflowState.MONITORING
            self._done(state, "MonitoringAgent", {
                "decision": "awaiting_review",
                "note": "Payer review in progress — check payer portal"
            })

        state = self._log(state, "payer_decision", {"outcome": outcome})
        if cb: await cb(state)
        return state

    async def _appeal_generate(self, state, auth_req, cb):
        """Standard (post-denial) appeal generation."""
        denial = state.get("denial_analysis", {}).get("denial_reason", "Not medically necessary")
        ev     = _EvidenceProxy(state.get("clinical_evidence", {}).get("evidence", {}))
        pm     = _PolicyProxy(state.get("policy_match", {}))

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
            "success_probability": f"{analysis.get('success_probability', 0.5):.0%}"
        })
        state = self._log(state, "appeal_generated", {"word_count": len(letter.split())})
        if cb: await cb(state)
        return state

    async def _appeal_submit(self, state, auth_req, cb):
        """Submit appeal back to FHIR server."""
        self._start(state, "AppealSubmissionAgent")
        state["current_state"] = WorkflowState.APPEAL_SUBMISSION
        if cb: await cb(state)

        pm = _PolicyProxy(state.get("policy_match", {}))

        class _AppealAuth:
            def __init__(self, s, a):
                self.id = s["auth_id"] + "-APPEAL"
                self.patient_id = s["patient_id"]
                self.cpt_code   = s["cpt_code"]
                self.patient    = a.patient
                self.policy_match = pm

        aa     = _AppealAuth(state, auth_req)
        result = await self.submission.submit_appeal(aa, state.get("fhir_bundle", {}), state.get("appeal_letter", ""))
        state["appeal_submission_result"] = result
        self._done(state, "AppealSubmissionAgent", {
            "claim_id": result.get("claim_response_id"),
            "status":   result.get("status", "submitted"),
            "message":  result.get("message", "Appeal sent to payer")
        })
        state = self._log(state, "appeal_submitted", {"claim_id": result.get("claim_response_id")})
        if cb: await cb(state)
        return state

    async def _appeal_monitoring(self, state, cb):
        """
        Poll the FHIR server for the appeal decision (separate claim ID).
        Updates current_state to APPEAL_APPROVED or APPEAL_DENIED.
        """
        self._start(state, "AppealMonitoringAgent")
        state["current_state"] = WorkflowState.APPEAL_MONITORING
        if cb: await cb(state)

        appeal_result = state.get("appeal_submission_result", {})
        appeal_claim_id = appeal_result.get("claim_response_id")

        if not appeal_claim_id:
            # No real FHIR server (mock mode) — leave as appeal_submission
            self._done(state, "AppealMonitoringAgent", {"decision": "awaiting_payer_review"})
            state = self._log(state, "appeal_monitoring_skipped", {"reason": "no_claim_id"})
            if cb: await cb(state)
            return state

        # Poll for the appeal decision
        decision_data = await self.submission._poll(appeal_claim_id)
        appeal_outcome = decision_data.get("auth_status", "pending")

        if appeal_outcome == "approved":
            state["current_state"] = WorkflowState.APPEAL_APPROVED
        elif appeal_outcome == "denied":
            state["current_state"] = WorkflowState.APPEAL_DENIED
        else:
            # Still pending — leave as appeal_submission so UI shows "awaiting"
            state["current_state"] = WorkflowState.APPEAL_SUBMISSION

        state["appeal_decision"] = {
            "outcome":        appeal_outcome,
            "decided_at":     decision_data.get("decided_at"),
            "reviewer":       decision_data.get("reviewer"),
            "denial_reason":  decision_data.get("denial_reason"),
        }

        self._done(state, "AppealMonitoringAgent", {
            "decision": appeal_outcome,
            "decided_at": decision_data.get("decided_at", "")
        })
        state = self._log(state, "appeal_decision_received", {"outcome": appeal_outcome})
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
            "clinical_evidence": None, "policy_requirements": None, "policy_match": None,
            "prediction": None, "preemptive_appeal": False,
            "fhir_bundle": None, "submission_result": None,
            "denial_analysis": None, "appeal_letter": None,
            "appeal_submission_result": None, "appeal_decision": None,
            "agents": {}, "error": None,
            "created_at": datetime.now(), "updated_at": datetime.now(),
            "processing_log": []
        }

    def _compile(self, state):
        return {
            "auth_id":                  state["auth_id"],
            "status":                   state["current_state"],
            "current_state":            state["current_state"],
            "clinical_evidence":        state.get("clinical_evidence"),
            "policy_match":             state.get("policy_match"),
            "prediction":               state.get("prediction"),
            "submission_result":        state.get("submission_result"),
            "denial_analysis":          state.get("denial_analysis"),
            "appeal_letter":            state.get("appeal_letter"),
            "appeal_submission_result": state.get("appeal_submission_result"),
            "appeal_decision":          state.get("appeal_decision"),
            "agents":                   state["agents"],
            "processing_log":           state["processing_log"],
            "error":                    state.get("error"),
            "completed_at":             datetime.now().isoformat()
        }


def create_workflow(cr, policy, submission, appeal):
    return AuthorizationWorkflow(cr, policy, submission, appeal)