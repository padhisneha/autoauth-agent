"""
Mock FHIR Server + Payer Decision Engine  —  Port 8001
Handles both initial PA submissions and appeal resubmissions.
"""

import uuid, json, asyncio, base64
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import EventSourceResponse
from pydantic import BaseModel

app = FastAPI(title="Mock FHIR / Payer Server", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

fhir_store: Dict[str, Dict[str, Any]] = {}
subscribers: Dict[str, List[asyncio.Queue]] = {}


class PayerDecision(BaseModel):
    decision: str
    reason: Optional[str] = None
    notes: Optional[str] = None
    reviewer: Optional[str] = "Dr. Payer Reviewer"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract(bundle: dict) -> dict:
    entries = bundle.get("entry", [])

    def _get(rt):
        return next((e["resource"] for e in entries
                     if e.get("resource", {}).get("resourceType") == rt), {})

    def _all(rt):
        return [e["resource"] for e in entries
                if e.get("resource", {}).get("resourceType") == rt]

    patient     = _get("Patient")
    service_req = _get("ServiceRequest")
    coverage    = _get("Coverage")
    conditions  = _all("Condition")
    medications = _all("MedicationStatement")

    # Patient name
    name_parts = (patient.get("name") or [{}])[0]
    first = (name_parts.get("given") or [""])[0]
    last  = name_parts.get("family", "")
    patient_name = f"{first} {last}".strip() or "Unknown"

    # CPT
    cpt_coding = ((service_req.get("code") or {}).get("coding") or [{}])[0]
    cpt_code   = cpt_coding.get("code", "")
    cpt_desc   = cpt_coding.get("display", f"CPT {cpt_code}")

    # Clinical summary (first doc ref with text/plain)
    clinical_summary = ""
    appeal_letter    = ""
    for e in entries:
        r = e.get("resource", {})
        if r.get("resourceType") != "DocumentReference": continue
        for content in r.get("content", []):
            att = content.get("attachment", {})
            if att.get("contentType") == "text/plain" and att.get("data"):
                try:
                    decoded = base64.b64decode(att["data"]).decode("utf-8")
                    # Appeal letter doc has description field
                    if r.get("description") == "Prior Authorization Appeal Letter" or r.get("id", "").startswith("appeal-"):
                        appeal_letter = decoded
                    elif not clinical_summary:
                        clinical_summary = decoded
                except Exception:
                    pass

    # Diagnoses
    diagnoses = []
    for c in conditions[:5]:
        coding = ((c.get("code") or {}).get("coding") or [{}])[0]
        diagnoses.append({"code": coding.get("code", ""), "display": coding.get("display", "")})

    # Payer
    payors = coverage.get("payor") or [{}]
    payer_name = payors[0].get("display", "") if payors else ""

    return {
        "patient_name":      patient_name,
        "patient_dob":       patient.get("birthDate", ""),
        "patient_gender":    patient.get("gender", ""),
        "cpt_code":          cpt_code,
        "cpt_description":   cpt_desc,
        "payer_name":        payer_name,
        "diagnoses":         diagnoses,
        "clinical_summary":  clinical_summary[:2000],
        "appeal_letter":     appeal_letter,
        "medications_count": len(medications),
        "conditions_count":  len(conditions),
    }


async def _notify(claim_id: str, event: dict):
    for q in subscribers.get(claim_id, []):
        await q.put(event)


# ── FHIR Endpoints ────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"name": "Mock FHIR/Payer Server", "status": "running",
            "total_requests": len(fhir_store)}


@app.post("/fhir/Bundle")
async def receive_bundle(
    bundle: Dict[str, Any],
    x_is_appeal: Optional[str] = Header(None),
    is_appeal: Optional[str] = Query(None)
):
    """Receive a FHIR Bundle — either initial PA or appeal resubmission."""
    claim_id    = f"CR-{uuid.uuid4().hex[:8].upper()}"
    received_at = datetime.now().isoformat()
    extracted   = _extract(bundle)

    # Detect if this is an appeal
    appeal_flag = (x_is_appeal or is_appeal or "").lower() == "true" or bool(extracted.get("appeal_letter"))

    record = {
        "claim_response_id": claim_id,
        "is_appeal":         appeal_flag,
        "status":            "pending",
        "received_at":       received_at,
        "decided_at":        None,
        "decision":          None,
        "denial_reason":     None,
        "reviewer_notes":    None,
        "reviewer":          None,
        "fhir_bundle":       bundle,
        "extracted":         extracted,
    }
    fhir_store[claim_id] = record

    kind = "APPEAL" if appeal_flag else "PA"
    print(f"[FHIR] {kind} received → {claim_id} | {extracted['patient_name']} | CPT {extracted['cpt_code']}")

    return {
        "resourceType":      "ClaimResponse",
        "id":                claim_id,
        "status":            "active",
        "created":           received_at,
        "outcome":           "queued",
        "disposition":       f"{'Appeal' if appeal_flag else 'PA'} request received.",
        "claim_response_id": claim_id,
        "is_appeal":         appeal_flag,
    }


@app.get("/fhir/ClaimResponse/{claim_id}")
async def get_claim_response(claim_id: str):
    if claim_id not in fhir_store:
        raise HTTPException(404, "ClaimResponse not found")
    r = fhir_store[claim_id]
    outcome_map = {"pending": "queued", "under_review": "queued",
                   "approved": "complete", "denied": "error"}
    return {
        "resourceType":      "ClaimResponse",
        "id":                claim_id,
        "status":            "active",
        "created":           r["received_at"],
        "outcome":           outcome_map.get(r["status"], "queued"),
        "disposition":       r["decision"] or "Pending payer review",
        "claim_response_id": claim_id,
        "auth_status":       r["status"],
        "denial_reason":     r["denial_reason"],
        "decided_at":        r["decided_at"],
        "reviewer":          r["reviewer"],
        "is_appeal":         r.get("is_appeal", False),
    }


# ── Payer UI API ──────────────────────────────────────────────────────────────

@app.get("/payer/queue")
async def get_queue():
    queue = []
    for cid, r in fhir_store.items():
        queue.append({
            "claim_id":         cid,
            "is_appeal":        r.get("is_appeal", False),
            "status":           r["status"],
            "received_at":      r["received_at"],
            "decided_at":       r["decided_at"],
            "patient_name":     r["extracted"]["patient_name"],
            "patient_dob":      r["extracted"]["patient_dob"],
            "cpt_code":         r["extracted"]["cpt_code"],
            "cpt_description":  r["extracted"]["cpt_description"],
            "payer_name":       r["extracted"]["payer_name"],
            "diagnoses":        r["extracted"]["diagnoses"],
            "conditions_count": r["extracted"]["conditions_count"],
            "medications_count":r["extracted"]["medications_count"],
            "has_appeal_letter":bool(r["extracted"].get("appeal_letter")),
        })
    queue.sort(key=lambda x: x["received_at"], reverse=True)
    return {"queue": queue, "total": len(queue)}


@app.get("/payer/request/{claim_id}")
async def get_request_detail(claim_id: str):
    if claim_id not in fhir_store:
        raise HTTPException(404, "Request not found")
    r = fhir_store[claim_id]
    return {
        "claim_id":       claim_id,
        "is_appeal":      r.get("is_appeal", False),
        "status":         r["status"],
        "received_at":    r["received_at"],
        "decided_at":     r["decided_at"],
        "decision":       r["decision"],
        "denial_reason":  r["denial_reason"],
        "reviewer_notes": r["reviewer_notes"],
        "reviewer":       r["reviewer"],
        "extracted":      r["extracted"],
    }


@app.post("/payer/review/{claim_id}")
async def mark_under_review(claim_id: str):
    if claim_id not in fhir_store:
        raise HTTPException(404, "Request not found")
    fhir_store[claim_id]["status"] = "under_review"
    return {"success": True, "claim_id": claim_id, "status": "under_review"}


@app.post("/payer/decide/{claim_id}")
async def payer_decide(claim_id: str, body: PayerDecision):
    if claim_id not in fhir_store:
        raise HTTPException(404, "Request not found")
    dec = body.decision.lower()
    if dec not in ("approved", "denied"):
        raise HTTPException(400, "decision must be approved or denied")

    r = fhir_store[claim_id]
    r.update({"status": dec, "decision": dec,
               "denial_reason": body.reason if dec == "denied" else None,
               "reviewer_notes": body.notes, "reviewer": body.reviewer,
               "decided_at": datetime.now().isoformat()})

    kind = "APPEAL" if r.get("is_appeal") else "PA"
    print(f"[PAYER] {kind} {claim_id}: {dec.upper()} by {body.reviewer}")

    await _notify(claim_id, {
        "type": "decision", "claim_id": claim_id,
        "status": dec, "reason": body.reason,
        "reviewer": body.reviewer, "decided_at": r["decided_at"]
    })

    return {"success": True, "claim_id": claim_id,
            "decision": dec, "decided_at": r["decided_at"]}


@app.get("/payer/stats")
async def stats():
    total    = len(fhir_store)
    pending  = sum(1 for r in fhir_store.values() if r["status"] in ("pending","under_review"))
    approved = sum(1 for r in fhir_store.values() if r["status"] == "approved")
    denied   = sum(1 for r in fhir_store.values() if r["status"] == "denied")
    appeals  = sum(1 for r in fhir_store.values() if r.get("is_appeal"))
    return {"total": total, "pending": pending, "approved": approved,
            "denied": denied, "appeals": appeals, "avg_review_time_minutes": 2.4}


@app.get("/payer/stream/{claim_id}")
async def stream(claim_id: str):
    q: asyncio.Queue = asyncio.Queue()
    subscribers.setdefault(claim_id, []).append(q)
    async def gen():
        try:
            if claim_id in fhir_store:
                yield f"data: {json.dumps({'type':'status','status':fhir_store[claim_id]['status']})}\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"data: {json.dumps(ev)}\n\n"
                    if ev.get("type") == "decision": break
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type':'heartbeat'})}\n\n"
        finally:
            if q in subscribers.get(claim_id, []):
                subscribers[claim_id].remove(q)
    return EventSourceResponse(gen())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
