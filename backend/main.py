"""
FastAPI Main Application - AutoAuth Agent Platform
"""

import sys
import os

# ── Fix #1: add src/ to path so agent/model/orchestration imports resolve ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import EventSourceResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
import asyncio
from datetime import datetime
import json

from agents.clinical_reader import ClinicalReaderAgent
from agents.policy_agent import PolicyAgent
from agents.submission_agent import SubmissionAgent
from agents.appeal_agent import AppealAgent
from orchestration.workflow import AuthorizationWorkflow, create_workflow
from models.schemas import (
    AuthorizationRequest, Patient, ClinicalNote,
    ServiceType, AuthStatus, DashboardStats
)

from openai import AsyncOpenAI
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

app = FastAPI(
    title="AutoAuth Agent API",
    description="Autonomous Prior Authorization Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

auth_requests: Dict[str, Dict[str, Any]] = {}
patients: Dict[str, Dict] = {}
clinical_notes: Dict[str, List[Dict]] = {}
workflow_states: Dict[str, Dict] = {}

clinical_reader  = ClinicalReaderAgent(llm_client=openai_client)
policy_agent     = PolicyAgent(llm_client=openai_client)
submission_agent = SubmissionAgent(mock_mode=True)
appeal_agent     = AppealAgent(llm_client=openai_client)

workflow = create_workflow(clinical_reader, policy_agent, submission_agent, appeal_agent)


# ── helpers ──────────────────────────────────────────────────────────────────

def _clean_status(raw: Any) -> str:
    """Convert WorkflowState enum or string like 'WorkflowState.APPROVED' → 'approved'."""
    return str(raw).split(".")[-1].lower()


# ── Request models ────────────────────────────────────────────────────────────

class InitiateAuthRequest(BaseModel):
    patient_id: str
    service_type: str
    cpt_code: str
    icd10_code: str
    priority: Optional[str] = "standard"

class PatientCreate(BaseModel):
    mrn: str
    first_name: str
    last_name: str
    date_of_birth: str
    gender: str
    address: Optional[str] = None
    phone: Optional[str] = None
    insurance_id: str
    payer_name: str

class ClinicalNoteCreate(BaseModel):
    patient_id: str
    note_type: str
    content: str
    provider: str
    facility: str

class ScenarioRequest(BaseModel):
    scenario_id: str


# ── Patient dict → dot-access object ─────────────────────────────────────────

class PatientObject:
    def __init__(self, data: Dict[str, Any]):
        self.id            = data.get("id", "")
        self.mrn           = data.get("mrn", "")
        self.first_name    = data.get("first_name", "")
        self.last_name     = data.get("last_name", "")
        self.date_of_birth = data.get("date_of_birth", "")
        self.gender        = data.get("gender", "")
        self.address       = data.get("address", "")
        self.phone         = data.get("phone", "")
        self.insurance_id  = data.get("insurance_id", "")
        self.payer_name    = data.get("payer_name", "")
        self.conditions    = data.get("conditions", [])
        self.medications   = data.get("medications", [])
        self.allergies     = data.get("allergies", [])


# ── Demo data ─────────────────────────────────────────────────────────────────

def initialize_demo_data():
    patients["patient-001"] = {
        "id": "patient-001", "mrn": "MRN-12345",
        "first_name": "John", "last_name": "Smith",
        "date_of_birth": "1965-03-15", "gender": "male",
        "address": "123 Main St, Boston, MA 02101", "phone": "(555) 123-4567",
        "insurance_id": "BCBS-789456123", "payer_name": "Blue Cross Blue Shield",
        "conditions": [{"code": "M54.5", "name": "Low back pain"}, {"code": "I10", "name": "Hypertension"}],
        "medications": [{"name": "Lisinopril 10mg", "frequency": "daily"}, {"name": "Ibuprofen 400mg", "frequency": "as needed"}],
        "allergies": ["Penicillin"]
    }
    patients["patient-002"] = {
        "id": "patient-002", "mrn": "MRN-67890",
        "first_name": "Sarah", "last_name": "Johnson",
        "date_of_birth": "1978-07-22", "gender": "female",
        "address": "456 Oak Ave, Cambridge, MA 02139", "phone": "(555) 987-6543",
        "insurance_id": "AET-456789012", "payer_name": "Aetna",
        "conditions": [{"code": "M75.10", "name": "Rotator cuff tear"}, {"code": "M25.51", "name": "Shoulder pain"}],
        "medications": [{"name": "Naproxen 500mg", "frequency": "twice daily"}],
        "allergies": []
    }
    patients["patient-003"] = {
        "id": "patient-003", "mrn": "MRN-11223",
        "first_name": "Michael", "last_name": "Chen",
        "date_of_birth": "1955-11-08", "gender": "male",
        "address": "789 Pine Rd, Brookline, MA 02445", "phone": "(555) 456-7890",
        "insurance_id": "UHC-321654987", "payer_name": "UnitedHealthcare",
        "conditions": [{"code": "C61", "name": "Prostate cancer"}, {"code": "N18.3", "name": "Chronic kidney disease"}],
        "medications": [
            {"name": "Lisinopril 20mg", "frequency": "daily"},
            {"name": "Metformin 1000mg", "frequency": "twice daily"},
            {"name": "Amlodipine 5mg", "frequency": "daily"}
        ],
        "allergies": ["Sulfa drugs", "Aspirin"]
    }

    clinical_notes["patient-001"] = [{
        "id": "note-001-1", "patient_id": "patient-001", "note_type": "Progress Note",
        "content": """Chief Complaint: Persistent low back pain for 6 weeks

History of Present Illness:
Patient is a 58-year-old male presenting with chronic low back pain that began approximately 6 weeks ago.
The pain is localized to the lumbar region, worse with movement and prolonged sitting.
Patient reports radiation down the left leg (L5 distribution) with occasional numbness.
Patient has tried over-the-counter ibuprofen with minimal relief.
Physical therapy was attempted for 4 weeks with modest improvement.

Past Medical History: Hypertension, Type 2 Diabetes, Hyperlipidemia.
Medications: Lisinopril 10mg daily, Ibuprofen 400mg as needed, Atorvastatin 20mg daily.
Vital Signs: BP 128/82, HR 72, Temp 98.6F.

Assessment:
1. Low back pain with radiculopathy - L4-L5 disc herniation suspected
2. Hypertension - controlled

Plan: MRI lumbar spine without contrast.
Patient has failed 6 weeks of conservative treatment including physical therapy and NSAIDs.
Given the radicular symptoms and failure of conservative management, MRI is medically necessary.""",
        "created_at": "2025-03-15T10:30:00", "provider": "Dr. Emily Williams", "facility": "Boston Medical Associates"
    }]

    clinical_notes["patient-002"] = [{
        "id": "note-002-1", "patient_id": "patient-002", "note_type": "Orthopedic Consultation",
        "content": """Consultation: Right Shoulder Pain

45-year-old female presents with right shoulder pain for 3 months.
Conservative treatment: Physical therapy for 6 weeks with minimal improvement, Naproxen 500mg twice daily.
Physical Exam: Positive Hawkins test, positive Neer impingement sign. Strength 4/5 supraspinatus.
Assessment: Suspected rotator cuff tear, failed conservative treatment.
Plan: MRI right shoulder without contrast. Patient has failed 6 weeks of conservative therapy.""",
        "created_at": "2025-03-14T14:00:00", "provider": "Dr. Robert Martinez", "facility": "Cambridge Orthopedic Associates"
    }]

    clinical_notes["patient-003"] = [{
        "id": "note-003-1", "patient_id": "patient-003", "note_type": "Oncology Follow-up",
        "content": """Oncology Follow-up: 70-year-old male with newly diagnosed prostate cancer (Gleason 7, PSA 8.2).
PMH: BPH, Hypertension, Type 2 Diabetes, CKD stage 2.
Medications: Lisinopril 20mg, Metformin 1000mg, Amlodipine 5mg, Tamsulosin 0.4mg.
Allergies: Sulfa drugs, Aspirin. Vitals: BP 138/88, HR 76.
Assessment: Prostate cancer T1cN0M0, staging workup needed.
Plan: CT abdomen/pelvis for lymph node evaluation. Per NCCN guidelines, staging imaging is indicated.""",
        "created_at": "2025-03-16T09:00:00", "provider": "Dr. Jennifer Park", "facility": "Dana-Farber Cancer Institute"
    }]


initialize_demo_data()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"name": "AutoAuth Agent API", "version": "1.0.0", "status": "running"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/patients")
async def list_patients():
    return {"patients": list(patients.values())}

@app.get("/api/patients/{patient_id}")
async def get_patient(patient_id: str):
    if patient_id not in patients:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patients[patient_id]

@app.post("/api/patients")
async def create_patient(patient: PatientCreate):
    pid = f"patient-{uuid.uuid4().hex[:8]}"
    data = {**patient.model_dump(), "id": pid, "conditions": [], "medications": [], "allergies": []}
    patients[pid] = data
    return data

@app.get("/api/patients/{patient_id}/notes")
async def get_patient_notes(patient_id: str):
    return {"notes": clinical_notes.get(patient_id, [])}

@app.post("/api/clinical/notes")
async def create_clinical_note(note: ClinicalNoteCreate):
    nid = f"note-{uuid.uuid4().hex[:8]}"
    data = {**note.model_dump(), "id": nid, "created_at": datetime.now().isoformat()}
    clinical_notes.setdefault(note.patient_id, []).append(data)
    return data


@app.post("/api/auth/initiate")
async def initiate_authorization(request: InitiateAuthRequest, background_tasks: BackgroundTasks):
    if request.patient_id not in patients:
        raise HTTPException(status_code=404, detail="Patient not found")

    auth_id = f"auth-{uuid.uuid4().hex[:8]}"
    patient = patients[request.patient_id]

    auth_request_data = {
        "id": auth_id,
        "patient_id": request.patient_id,
        "patient": patient,
        "service_type": request.service_type,
        "cpt_code": request.cpt_code,
        "icd10_code": request.icd10_code,
        "priority": request.priority,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    auth_requests[auth_id] = auth_request_data
    background_tasks.add_task(run_workflow, auth_id)
    return {"auth_id": auth_id, "status": "pending",
            "message": "Processing started.", "patient": patient}


async def run_workflow(auth_id: str):
    auth_request = auth_requests.get(auth_id)
    if not auth_request:
        return

    notes_data = clinical_notes.get(auth_request["patient_id"], [])

    class MockClinicalNote:
        def __init__(self, d):
            self.id = d.get("id", "")
            self.patient_id = d.get("patient_id", "")
            self.note_type = d.get("note_type", "")
            self.content = d.get("content", "")
            self.created_at = datetime.fromisoformat(d.get("created_at", datetime.now().isoformat()))
            self.provider = d.get("provider", "")
            self.facility = d.get("facility", "")

    notes = [MockClinicalNote(n) for n in notes_data]

    class MockAuthRequest:
        def __init__(self, d):
            self.id = d["id"]
            self.patient_id = d["patient_id"]
            self.service_type = d["service_type"]
            self.cpt_code = d["cpt_code"]
            self.icd10_code = d["icd10_code"]
            raw = d.get("patient")
            self.patient = PatientObject(raw) if isinstance(raw, dict) else raw

    mock_auth = MockAuthRequest(auth_request)

    async def callback(state):
        ser = json.loads(json.dumps(state, default=str))
        # Normalise every occurrence of the enum string
        ser["current_state"] = _clean_status(ser.get("current_state", "pending"))
        workflow_states[auth_id] = ser
        auth_requests[auth_id]["status"] = ser["current_state"]
        auth_requests[auth_id]["updated_at"] = datetime.now().isoformat()

    try:
        result = await workflow.execute_workflow(mock_auth, notes, callback)
        ser = json.loads(json.dumps(result, default=str))
        clean = _clean_status(ser.get("status") or ser.get("current_state") or "completed")
        ser["status"] = clean
        ser["current_state"] = clean
        auth_requests[auth_id].update({
            "status": clean,
            "workflow_result": ser,
            "updated_at": datetime.now().isoformat()
        })
        workflow_states[auth_id] = ser
    except Exception as e:
        import traceback
        print(f"[WORKFLOW ERROR] {auth_id}: {traceback.format_exc()}")
        auth_requests[auth_id]["status"] = "error"
        auth_requests[auth_id]["error"] = str(e)
        auth_requests[auth_id]["updated_at"] = datetime.now().isoformat()


@app.get("/api/auth/{auth_id}")
async def get_authorization(auth_id: str):
    if auth_id not in auth_requests:
        raise HTTPException(status_code=404, detail="Authorization not found")
    return {"auth": auth_requests[auth_id], "workflow_state": workflow_states.get(auth_id)}

@app.get("/api/auth/{auth_id}/trace")
async def get_workflow_trace(auth_id: str):
    if auth_id not in auth_requests:
        raise HTTPException(status_code=404, detail="Authorization not found")
    ws = workflow_states.get(auth_id, {})
    raw = ws.get("current_state") or ws.get("status") or "pending"
    current = _clean_status(raw)
    return {
        "auth_id": auth_id,
        "agents": ws.get("agents", {}),
        "processing_log": ws.get("processing_log", []),
        "current_state": current,
        "clinical_evidence": ws.get("clinical_evidence"),
        "policy_match": ws.get("policy_match"),
        "submission_result": ws.get("submission_result"),
        "appeal_letter": ws.get("appeal_letter")
    }

@app.get("/api/auth")
async def list_authorizations():
    return {"authorizations": list(auth_requests.values())}

@app.post("/api/auth/{auth_id}/approve")
async def manually_approve(auth_id: str):
    if auth_id not in auth_requests:
        raise HTTPException(status_code=404, detail="Authorization not found")
    auth_requests[auth_id]["status"] = "approved"
    return {"success": True, "status": "approved"}

@app.post("/api/auth/{auth_id}/deny")
async def manually_deny(auth_id: str):
    if auth_id not in auth_requests:
        raise HTTPException(status_code=404, detail="Authorization not found")
    auth_requests[auth_id]["status"] = "denied"
    return {"success": True, "status": "denied"}


@app.post("/api/demo/scenario")
async def load_scenario(request: ScenarioRequest):
    scenarios = {
        "cardiology-mri":  {"patient_id": "patient-001", "service_type": "mri",     "cpt_code": "72148", "icd10_code": "M54.5",  "title": "Lumbar Spine MRI",            "description": "Chronic back pain with radiculopathy"},
        "orthopedics-mri": {"patient_id": "patient-002", "service_type": "mri",     "cpt_code": "73221", "icd10_code": "M75.10", "title": "Shoulder MRI for Rotator Cuff","description": "Failed 6 weeks PT"},
        "oncology-ct":     {"patient_id": "patient-003", "service_type": "ct_scan", "cpt_code": "74177", "icd10_code": "C61",    "title": "CT Staging for Prostate Cancer","description": "Newly diagnosed prostate cancer"},
    }
    if request.scenario_id not in scenarios:
        raise HTTPException(status_code=404, detail="Scenario not found")
    s = scenarios[request.scenario_id]
    return {"scenario": s, "patient": patients[s["patient_id"]], "clinical_notes": clinical_notes.get(s["patient_id"], [])}


@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    total    = len(auth_requests)
    approved = sum(1 for a in auth_requests.values() if _clean_status(a.get("status","")) == "approved")
    denied   = sum(1 for a in auth_requests.values() if _clean_status(a.get("status","")) in ["denied","appeal_denied"])
    pending  = total - approved - denied
    rate     = (approved / (approved + denied) * 100) if (approved + denied) > 0 else 0
    return {
        "total_requests": total, "approved": approved, "denied": denied, "pending": max(pending, 0),
        "approval_rate": round(rate, 1), "avg_processing_time_seconds": 45.2,
        "total_cost_saved": total * 70, "appeals_success_rate": 42.5
    }

@app.get("/api/dashboard/recent-activity")
async def get_recent_activity():
    activities = []
    for auth_id, auth in list(auth_requests.items())[-10:]:
        pd = auth.get("patient", {})
        first = pd.get("first_name", "") if isinstance(pd, dict) else ""
        last  = pd.get("last_name",  "") if isinstance(pd, dict) else ""
        activities.append({
            "auth_id":   auth_id,
            "patient":   f"{first} {last}".strip() or "Unknown",
            "service":   auth.get("service_type", "Unknown"),
            "status":    _clean_status(auth.get("status", "pending")),
            "timestamp": auth.get("updated_at", auth.get("created_at", ""))
        })
    return {"activities": list(reversed(activities))}


@app.get("/api/events/{auth_id}")
async def event_stream(auth_id: str):
    async def gen():
        while True:
            if auth_id in workflow_states:
                ws = {**workflow_states[auth_id]}
                ws["current_state"] = _clean_status(ws.get("current_state", "pending"))
                yield f"data: {json.dumps(ws, default=str)}\n\n"
                if ws["current_state"] in ["approved","denied","completed","requires_human_review"]:
                    break
            await asyncio.sleep(1)
    return EventSourceResponse(gen())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)