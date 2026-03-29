"""
Orchestration Layer — AutoAuth Agent using LangGraph.

Graph structure:
  triage → evidence → policy → validation → prediction → decision_engine
    → submission → monitoring
      → approved                                          (END)
      → monitoring_pending  (awaiting payer review)       (END)
      → denied → appeal_generate → appeal_submit → appeal_monitoring
          → appeal_approved                               (END)
          → appeal_denied                                 (END)
  Any unhandled exception → requires_human_review         (END)

The preemptive appeal path (low probability) is handled inside decision_engine:
the appeal letter is generated there and attached to the FHIR bundle at submission.
"""

from __future__ import annotations

import traceback
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END


# ── Enums (kept identical — nothing else in the codebase needs to change) ────

class WorkflowState(str, Enum):
    PENDING               = "pending"
    TRIAGE                = "triage"
    EVIDENCE_EXTRACTION   = "evidence_extraction"
    POLICY_LOOKUP         = "policy_lookup"
    VALIDATION            = "validation"
    PREDICTION            = "prediction"
    DECISION_ENGINE       = "decision_engine"
    PREEMPTIVE_APPEAL     = "preemptive_appeal"
    SUBMISSION            = "submission"
    MONITORING            = "monitoring"
    APPROVED              = "approved"
    DENIED                = "denied"
    APPEAL_ANALYSIS       = "appeal_analysis"
    APPEAL_GENERATION     = "appeal_generation"
    APPEAL_SUBMISSION     = "appeal_submission"
    APPEAL_MONITORING     = "appeal_monitoring"
    APPEAL_APPROVED       = "appeal_approved"
    APPEAL_DENIED         = "appeal_denied"
    COMPLETED             = "completed"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class AgentStatus(str, Enum):
    IDLE = "idle"; RUNNING = "running"; COMPLETED = "completed"
    FAILED = "failed"; WAITING = "waiting"


# ── LangGraph typed state ─────────────────────────────────────────────────────

class GraphState(TypedDict, total=False):
    auth_id: str; patient_id: str; service_type: str; cpt_code: str; icd10_code: str
    # Runtime refs injected before the graph runs (not serialised to client)
    _auth_request: Any; _clinical_notes: List[Any]; _callback: Optional[Callable]
    _clinical_reader: Any; _policy: Any; _submission: Any; _appeal: Any
    # Workflow data
    current_state: str
    clinical_evidence: Optional[Dict]; policy_requirements: Optional[Dict]
    policy_match: Optional[Dict]; prediction: Optional[Dict]
    preemptive_appeal: bool; fhir_bundle: Optional[Dict]
    submission_result: Optional[Dict]; denial_analysis: Optional[Dict]
    appeal_letter: Optional[str]; appeal_submission_result: Optional[Dict]
    appeal_decision: Optional[Dict]
    agents: Dict; processing_log: List; error: Optional[str]
    created_at: Any; updated_at: Any


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
    def is_covered(self):             return bool(self._d.get("is_covered", False))
    @property
    def match_score(self):            return float(self._d.get("match_score", 0.0))
    @property
    def satisfied_requirements(self): return self._d.get("satisfied_requirements", [])
    @property
    def missing_requirements(self):   return self._d.get("missing_requirements", [])


# ── State mutation helpers ────────────────────────────────────────────────────

def _agent_start(s: GraphState, name: str) -> GraphState:
    agents = dict(s.get("agents", {}))
    agents[name] = {"name": name, "status": AgentStatus.RUNNING,
                    "start_time": datetime.now(), "end_time": None,
                    "input_data": {}, "output_data": {},
                    "reasoning_steps": [], "error": None, "tokens_used": 0}
    return {**s, "agents": agents, "updated_at": datetime.now()}

def _agent_done(s: GraphState, name: str, output: dict) -> GraphState:
    agents = dict(s.get("agents", {}))
    if name in agents:
        agents[name] = {**agents[name], "status": AgentStatus.COMPLETED,
                        "end_time": datetime.now(), "output_data": output}
    return {**s, "agents": agents, "updated_at": datetime.now()}

def _log_event(s: GraphState, event: str, data: dict) -> GraphState:
    log = list(s.get("processing_log", []))
    log.append({"timestamp": datetime.now().isoformat(),
                "event_type": event,
                "state": str(s.get("current_state", "")), "data": data})
    return {**s, "processing_log": log}

async def _fire_callback(s: GraphState) -> None:
    cb = s.get("_callback")
    if cb: await cb(s)


# ── Node implementations ──────────────────────────────────────────────────────

async def node_triage(s: GraphState) -> GraphState:
    s = _agent_start(s, "TriageAgent")
    urgent = "urgent" in str(s.get("service_type", "")).lower()
    s = {**s, "current_state": WorkflowState.TRIAGE}
    s = _agent_done(s, "TriageAgent", {"is_urgent": urgent, "priority": "urgent" if urgent else "standard"})
    s = _log_event(s, "triage_completed", {"is_urgent": urgent})
    await _fire_callback(s)
    return s


async def node_evidence(s: GraphState) -> GraphState:
    s = _agent_start(s, "ClinicalReaderAgent")
    cr = s["_clinical_reader"]
    ev = await cr.extract_clinical_evidence(s["_clinical_notes"], s["patient_id"], s["service_type"], s["cpt_code"])
    na = await cr.analyze_medical_necessity(ev, s["service_type"], s["cpt_code"])
    ev_dict = ev.model_dump() if hasattr(ev, "model_dump") else vars(ev)
    s = {**s, "current_state": WorkflowState.EVIDENCE_EXTRACTION,
              "clinical_evidence": {"evidence": ev_dict, "necessity_analysis": na}}
    s = _agent_done(s, "ClinicalReaderAgent", {
        "conditions_found": len(ev.conditions),
        "confidence": round(ev.extraction_confidence, 2),
        "summary": (ev.clinical_summary or "")[:150]})
    s = _log_event(s, "evidence_done", {"conditions": len(ev.conditions)})
    await _fire_callback(s)
    return s


async def node_policy(s: GraphState) -> GraphState:
    s = _agent_start(s, "PolicyAgent")
    auth_req = s["_auth_request"]
    payer = getattr(getattr(auth_req, "patient", None), "payer_name", "Blue Cross Blue Shield")
    req = await s["_policy"].retrieve_policy_requirements(payer, s["service_type"], s["cpt_code"])
    ev  = _EvidenceProxy(s.get("clinical_evidence", {}).get("evidence", {}))
    pm  = await s["_policy"].match_policy(ev, req, payer)
    s = {**s, "current_state": WorkflowState.POLICY_LOOKUP,
              "policy_requirements": req.model_dump() if hasattr(req, "model_dump") else {},
              "policy_match":        pm.model_dump()  if hasattr(pm,  "model_dump") else {}}
    s = _agent_done(s, "PolicyAgent", {
        "match_score": round(pm.match_score, 2), "is_covered": pm.is_covered,
        "missing": len(pm.missing_requirements)})
    s = _log_event(s, "policy_done", {"match_score": pm.match_score})
    await _fire_callback(s)
    return s


async def node_validation(s: GraphState) -> GraphState:
    s = _agent_start(s, "ValidationAgent")
    s = {**s, "current_state": WorkflowState.VALIDATION}
    s = _agent_done(s, "ValidationAgent", {"can_proceed": True})
    s = _log_event(s, "validation_done", {})
    await _fire_callback(s)
    return s


async def node_prediction(s: GraphState) -> GraphState:
    """🔮 Prediction Engine."""
    s = _agent_start(s, "PredictionAgent")
    s = {**s, "current_state": WorkflowState.PREDICTION}
    auth_req = s["_auth_request"]
    pm_data  = s.get("policy_match", {})
    na       = s.get("clinical_evidence", {}).get("necessity_analysis", {})

    match_score     = float(pm_data.get("match_score", 0.5))
    is_covered      = bool(pm_data.get("is_covered", False))
    missing_count   = len(pm_data.get("missing_requirements", []))
    satisfied_count = len(pm_data.get("satisfied_requirements", []))
    necessity_score = float(na.get("necessity_score", 0.5))
    payer = getattr(getattr(auth_req, "patient", None), "payer_name", "")
    payer_factor = {"Blue Cross Blue Shield": 0.0, "Aetna": -0.05,
                    "UnitedHealthcare": -0.05, "Cigna": -0.08, "Medicare": 0.02}.get(payer, -0.03)

    prob = max(0.05, min(0.95,
        (match_score * 0.4) + (necessity_score * 0.35) + (0.1 if is_covered else 0.0)
        + min(satisfied_count * 0.04, 0.15) - min(missing_count * 0.06, 0.20) + payer_factor))

    if prob >= 0.75:   risk, strategy = "low",    "direct_submit"
    elif prob >= 0.55: risk, strategy = "medium",  "submit_with_justification"
    else:              risk, strategy = "high",    "preemptive_appeal"

    reasoning = {
        "direct_submit":            f"Strong policy match ({match_score:.0%}) and necessity score ({necessity_score:.0%}). Confident approval expected.",
        "submit_with_justification": "Moderate approval probability. Submitting with enhanced clinical justification.",
        "preemptive_appeal":        f"Low approval probability ({prob:.0%}) — generating appeal proactively before submission.",
    }[strategy]

    prediction = {
        "approval_probability": round(prob, 3), "risk_level": risk,
        "strategy": strategy, "reasoning": reasoning,
        "policy_match_score": round(match_score, 2), "necessity_score": round(necessity_score, 2),
        "missing_criteria": missing_count, "satisfied_criteria": satisfied_count, "payer": payer,
    }
    s = {**s, "prediction": prediction}
    s = _agent_done(s, "PredictionAgent", {"approval_probability": f"{prob:.0%}", "risk_level": risk, "strategy": strategy})
    s = _log_event(s, "prediction_complete", prediction)
    await _fire_callback(s)
    return s


async def node_decision_engine(s: GraphState) -> GraphState:
    """🧠 Decision Engine — may generate preemptive appeal inside this node."""
    s = _agent_start(s, "DecisionEngine")
    s = {**s, "current_state": WorkflowState.DECISION_ENGINE}

    prediction = s.get("prediction", {})
    strategy   = prediction.get("strategy", "direct_submit")
    prob       = prediction.get("approval_probability", 0.5)
    auth_req   = s["_auth_request"]

    if strategy == "preemptive_appeal":
        s = {**s, "current_state": WorkflowState.PREEMPTIVE_APPEAL}
        await _fire_callback(s)

        ev = _EvidenceProxy(s.get("clinical_evidence", {}).get("evidence", {}))
        pm = _PolicyProxy(s.get("policy_match", {}))
        preemptive_denial = {
            "denial_reason": f"Anticipated: {', '.join(pm.missing_requirements[:2]) or 'incomplete documentation'}",
            "primary_appeal_argument": "Proactive documentation package demonstrates full medical necessity.",
            "supporting_evidence": [], "urgency_indicators": [], "peer_review_recommended": True,
            "success_probability": min(prob + 0.2, 0.85),
        }
        s = _agent_start(s, "AppealAgent")
        letter = await s["_appeal"].generate_appeal_letter(auth_req, preemptive_denial, ev, pm)
        s = {**s, "appeal_letter": letter, "denial_analysis": preemptive_denial, "preemptive_appeal": True}
        s = _agent_done(s, "AppealAgent", {
            "word_count": len(letter.split()), "type": "preemptive",
            "success_probability": f"{preemptive_denial['success_probability']:.0%}"})
        s = _log_event(s, "preemptive_appeal_generated", {"word_count": len(letter.split())})

    s = _agent_done(s, "DecisionEngine", {
        "strategy": strategy, "probability": f"{prob:.0%}",
        "action": "Appeal pre-generated" if strategy == "preemptive_appeal" else "Proceeding with submission"})
    s = {**s, "current_state": WorkflowState.DECISION_ENGINE}
    s = _log_event(s, "decision_engine_complete", {"strategy": strategy})
    await _fire_callback(s)
    return s


async def node_submission(s: GraphState) -> GraphState:
    s = _agent_start(s, "SubmissionAgent")
    auth_req   = s["_auth_request"]
    ev         = _EvidenceProxy(s.get("clinical_evidence", {}).get("evidence", {}))
    pm         = _PolicyProxy(s.get("policy_match", {}))
    preemptive = s.get("appeal_letter") if s.get("preemptive_appeal") else None

    class _Auth:
        def __init__(self_, ss, a):
            self_.id = ss["auth_id"]; self_.patient_id = ss["patient_id"]
            self_.cpt_code = ss["cpt_code"]; self_.patient = a.patient; self_.policy_match = pm

    sa     = _Auth(s, auth_req)
    bundle = await s["_submission"].build_fhir_bundle(sa, ev, pm, appeal_letter=preemptive)
    result = await s["_submission"].submit_prior_authorization(sa, bundle)
    s = {**s, "current_state": WorkflowState.SUBMISSION, "fhir_bundle": bundle, "submission_result": result}
    s = _agent_done(s, "SubmissionAgent", {
        "claim_id": result.get("claim_response_id"), "status": result.get("status"),
        "strategy": "preemptive_attached" if preemptive else "standard"})
    s = _log_event(s, "submission_done", {"status": result.get("status")})
    await _fire_callback(s)
    return s


async def node_monitoring(s: GraphState) -> GraphState:
    s = _agent_start(s, "MonitoringAgent")
    res     = s.get("submission_result", {})
    dec     = res.get("decision", {})
    outcome = str(dec.get("outcome") or res.get("status") or "pending").lower()

    if outcome == "approved":
        s = {**s, "current_state": WorkflowState.APPROVED}
        s = _agent_done(s, "MonitoringAgent", {"decision": "approved"})
    elif outcome == "denied":
        existing = s.get("denial_analysis") or {}
        s = {**s, "current_state": WorkflowState.DENIED,
                  "denial_analysis": {**existing, "denial_reason": dec.get("reason") or "Service not medically necessary"}}
        s = _agent_done(s, "MonitoringAgent", {"decision": "denied"})
    else:
        # pending / timeout — payer hasn't decided yet
        s = {**s, "current_state": WorkflowState.MONITORING}
        s = _agent_done(s, "MonitoringAgent", {"decision": "awaiting_review", "note": "Check payer portal"})

    s = _log_event(s, "payer_decision", {"outcome": outcome})
    await _fire_callback(s)
    return s


async def node_appeal_generate(s: GraphState) -> GraphState:
    auth_req = s["_auth_request"]
    denial   = (s.get("denial_analysis") or {}).get("denial_reason", "Not medically necessary")
    ev = _EvidenceProxy(s.get("clinical_evidence", {}).get("evidence", {}))
    pm = _PolicyProxy(s.get("policy_match", {}))

    analysis = await s["_appeal"].analyze_denial(auth_req, denial, ev, pm)
    s = {**s, "denial_analysis": analysis, "current_state": WorkflowState.APPEAL_ANALYSIS}
    await _fire_callback(s)

    s = _agent_start(s, "AppealAgent")
    letter = await s["_appeal"].generate_appeal_letter(auth_req, analysis, ev, pm)
    s = {**s, "appeal_letter": letter, "current_state": WorkflowState.APPEAL_GENERATION}
    s = _agent_done(s, "AppealAgent", {
        "word_count": len(letter.split()),
        "success_probability": f"{analysis.get('success_probability', 0.5):.0%}"})
    s = _log_event(s, "appeal_generated", {"word_count": len(letter.split())})
    await _fire_callback(s)
    return s


async def node_appeal_submit(s: GraphState) -> GraphState:
    s = _agent_start(s, "AppealSubmissionAgent")
    s = {**s, "current_state": WorkflowState.APPEAL_SUBMISSION}
    await _fire_callback(s)

    auth_req = s["_auth_request"]
    pm = _PolicyProxy(s.get("policy_match", {}))

    class _AppealAuth:
        def __init__(self_, ss, a):
            self_.id = ss["auth_id"] + "-APPEAL"; self_.patient_id = ss["patient_id"]
            self_.cpt_code = ss["cpt_code"]; self_.patient = a.patient; self_.policy_match = pm

    aa     = _AppealAuth(s, auth_req)
    result = await s["_submission"].submit_appeal(aa, s.get("fhir_bundle", {}), s.get("appeal_letter", ""))
    s = {**s, "appeal_submission_result": result}
    s = _agent_done(s, "AppealSubmissionAgent", {
        "claim_id": result.get("claim_response_id"),
        "status":   result.get("status", "submitted"),
        "message":  result.get("message", "Appeal sent to payer")})
    s = _log_event(s, "appeal_submitted", {"claim_id": result.get("claim_response_id")})
    await _fire_callback(s)
    return s


async def node_appeal_monitoring(s: GraphState) -> GraphState:
    s = _agent_start(s, "AppealMonitoringAgent")
    s = {**s, "current_state": WorkflowState.APPEAL_MONITORING}
    await _fire_callback(s)

    claim_id = (s.get("appeal_submission_result") or {}).get("claim_response_id")
    if not claim_id:
        s = _agent_done(s, "AppealMonitoringAgent", {"decision": "awaiting_payer_review"})
        s = _log_event(s, "appeal_monitoring_skipped", {"reason": "no_claim_id"})
        await _fire_callback(s)
        return s

    data    = await s["_submission"]._poll(claim_id)
    outcome = data.get("auth_status", "pending")

    if outcome == "approved":   s = {**s, "current_state": WorkflowState.APPEAL_APPROVED}
    elif outcome == "denied":   s = {**s, "current_state": WorkflowState.APPEAL_DENIED}
    else:                       s = {**s, "current_state": WorkflowState.APPEAL_SUBMISSION}

    s = {**s, "appeal_decision": {
        "outcome": outcome, "decided_at": data.get("decided_at"),
        "reviewer": data.get("reviewer"), "denial_reason": data.get("denial_reason")}}
    s = _agent_done(s, "AppealMonitoringAgent", {"decision": outcome, "decided_at": data.get("decided_at", "")})
    s = _log_event(s, "appeal_decision_received", {"outcome": outcome})
    await _fire_callback(s)
    return s


# ── Conditional edge routing ──────────────────────────────────────────────────

def route_monitoring(s: GraphState) -> str:
    cs = str(s.get("current_state", "")).split(".")[-1].lower()
    if cs == "approved": return "approved"
    if cs == "denied":   return "appeal_generate"
    return "pending"  # timeout / still waiting


def route_appeal_monitoring(s: GraphState) -> str:
    cs = str(s.get("current_state", "")).split(".")[-1].lower()
    return "appeal_approved" if cs == "appeal_approved" else "appeal_denied"


# ── Graph assembly ────────────────────────────────────────────────────────────

def _build_graph():
    g = StateGraph(GraphState)

    for name, fn in [
        ("triage",            node_triage),
        ("evidence",          node_evidence),
        ("policy",            node_policy),
        ("validation",        node_validation),
        ("prediction",        node_prediction),
        ("decision_engine",   node_decision_engine),
        ("submission",        node_submission),
        ("monitoring",        node_monitoring),
        ("appeal_generate",   node_appeal_generate),
        ("appeal_submit",     node_appeal_submit),
        ("appeal_monitoring", node_appeal_monitoring),
    ]:
        g.add_node(name, fn)

    g.set_entry_point("triage")

    # Linear spine
    for a, b in [("triage","evidence"), ("evidence","policy"), ("policy","validation"),
                 ("validation","prediction"), ("prediction","decision_engine"),
                 ("decision_engine","submission"), ("submission","monitoring")]:
        g.add_edge(a, b)

    # After monitoring: branch on outcome
    g.add_conditional_edges("monitoring", route_monitoring, {
        "approved":      END,
        "pending":       END,   # awaiting payer — workflow parks here
        "appeal_generate":"appeal_generate",
    })

    # Appeal spine
    g.add_edge("appeal_generate",   "appeal_submit")
    g.add_edge("appeal_submit",     "appeal_monitoring")

    # After appeal monitoring: always END
    g.add_conditional_edges("appeal_monitoring", route_appeal_monitoring, {
        "appeal_approved": END,
        "appeal_denied":   END,
    })

    return g.compile()


# ── Public API — identical to before so main.py needs no changes ─────────────

class AuthorizationWorkflow:
    def __init__(self, clinical_reader, policy, submission, appeal):
        self.clinical_reader = clinical_reader
        self.policy          = policy
        self.submission      = submission
        self.appeal          = appeal
        self._graph          = _build_graph()

    async def execute_workflow(self, auth_request, clinical_notes, callback=None) -> Dict[str, Any]:
        initial: GraphState = {
            "auth_id": auth_request.id, "patient_id": auth_request.patient_id,
            "service_type": auth_request.service_type, "cpt_code": auth_request.cpt_code,
            "icd10_code": auth_request.icd10_code,
            "_auth_request": auth_request, "_clinical_notes": clinical_notes,
            "_callback": callback, "_clinical_reader": self.clinical_reader,
            "_policy": self.policy, "_submission": self.submission, "_appeal": self.appeal,
            "current_state": WorkflowState.PENDING,
            "clinical_evidence": None, "policy_requirements": None, "policy_match": None,
            "prediction": None, "preemptive_appeal": False, "fhir_bundle": None,
            "submission_result": None, "denial_analysis": None, "appeal_letter": None,
            "appeal_submission_result": None, "appeal_decision": None,
            "agents": {}, "error": None, "processing_log": [],
            "created_at": datetime.now(), "updated_at": datetime.now(),
        }
        try:
            final = await self._graph.ainvoke(initial)
        except Exception as e:
            print(f"[LANGGRAPH ERROR]\n{traceback.format_exc()}")
            final = {**initial, "current_state": WorkflowState.REQUIRES_HUMAN_REVIEW, "error": str(e)}
            final = _log_event(final, "error", {"error": str(e)})
            if callback: await callback(final)
        return self._compile(final)

    def _compile(self, s: GraphState) -> Dict[str, Any]:
        return {
            "auth_id": s.get("auth_id"), "status": s.get("current_state"),
            "current_state": s.get("current_state"),
            "clinical_evidence": s.get("clinical_evidence"),
            "policy_match": s.get("policy_match"), "prediction": s.get("prediction"),
            "submission_result": s.get("submission_result"), "denial_analysis": s.get("denial_analysis"),
            "appeal_letter": s.get("appeal_letter"),
            "appeal_submission_result": s.get("appeal_submission_result"),
            "appeal_decision": s.get("appeal_decision"),
            "agents": s.get("agents", {}), "processing_log": s.get("processing_log", []),
            "error": s.get("error"), "completed_at": datetime.now().isoformat(),
        }


def create_workflow(cr, policy, submission, appeal) -> AuthorizationWorkflow:
    return AuthorizationWorkflow(cr, policy, submission, appeal)