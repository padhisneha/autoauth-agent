"""
FastAPI Main Application - AutoAuth Agent Platform
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, EventSourceResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
import asyncio
from datetime import datetime
import json
import os

# Import agents and services
from agents.clinical_reader import ClinicalReaderAgent
from agents.policy_agent import PolicyAgent
from agents.submission_agent import SubmissionAgent
from agents.appeal_agent import AppealAgent
from orchestration.workflow import AuthorizationWorkflow, create_workflow
from models.schemas import (
    AuthorizationRequest, Patient, ClinicalNote,
    ServiceType, AuthStatus, DashboardStats
)

# Initialize OpenAI client
from openai import AsyncOpenAI

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

# Initialize app
app = FastAPI(
    title="AutoAuth Agent API",
    description="Autonomous Prior Authorization Platform",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage
auth_requests: Dict[str, Dict[str, Any]] = {}
patients: Dict[str, Dict] = {}
clinical_notes: Dict[str, List[Dict]] = {}
workflow_states: Dict[str, Dict] = {}

# Initialize agents — pass the shared openai_client
clinical_reader = ClinicalReaderAgent(llm_client=openai_client)
policy_agent = PolicyAgent(llm_client=openai_client)
submission_agent = SubmissionAgent(mock_mode=True)
appeal_agent = AppealAgent(llm_client=openai_client)

# Workflow instance
workflow = create_workflow(clinical_reader, policy_agent, submission_agent, appeal_agent)


# ============ Data Models ============

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


# ============ Patient dict → object wrapper ============

class PatientObject:
    """Wraps a patient dict so agents can use dot notation (patient.first_name etc.)"""
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id", "")
        self.mrn = data.get("mrn", "")
        self.first_name = data.get("first_name", "")
        self.last_name = data.get("last_name", "")
        self.date_of_birth = data.get("date_of_birth", "")
        self.gender = data.get("gender", "")
        self.address = data.get("address", "")
        self.phone = data.get("phone", "")
        self.insurance_id = data.get("insurance_id", "")
        self.payer_name = data.get("payer_name", "")
        self.conditions = data.get("conditions", [])
        self.medications = data.get("medications", [])
        self.allergies = data.get("allergies", [])


# ============ Demo Data ============

def initialize_demo_data():
    """Initialize demo data for the hackathon."""

    patients["patient-001"] = {
        "id": "patient-001",
        "mrn": "MRN-12345",
        "first_name": "John",
        "last_name": "Smith",
        "date_of_birth": "1965-03-15",
        "gender": "male",
        "address": "123 Main St, Boston, MA 02101",
        "phone": "(555) 123-4567",
        "insurance_id": "BCBS-789456123",
        "payer_name": "Blue Cross Blue Shield",
        "conditions": [
            {"code": "M54.5", "name": "Low back pain"},
            {"code": "I10", "name": "Hypertension"}
        ],
        "medications": [
            {"name": "Lisinopril 10mg", "frequency": "daily"},
            {"name": "Ibuprofen 400mg", "frequency": "as needed"}
        ],
        "allergies": ["Penicillin"]
    }

    patients["patient-002"] = {
        "id": "patient-002",
        "mrn": "MRN-67890",
        "first_name": "Sarah",
        "last_name": "Johnson",
        "date_of_birth": "1978-07-22",
        "gender": "female",
        "address": "456 Oak Ave, Cambridge, MA 02139",
        "phone": "(555) 987-6543",
        "insurance_id": "AET-456789012",
        "payer_name": "Aetna",
        "conditions": [
            {"code": "M75.10", "name": "Rotator cuff tear"},
            {"code": "M25.51", "name": "Shoulder pain"}
        ],
        "medications": [
            {"name": "Naproxen 500mg", "frequency": "twice daily"}
        ],
        "allergies": []
    }

    patients["patient-003"] = {
        "id": "patient-003",
        "mrn": "MRN-11223",
        "first_name": "Michael",
        "last_name": "Chen",
        "date_of_birth": "1955-11-08",
        "gender": "male",
        "address": "789 Pine Rd, Brookline, MA 02445",
        "phone": "(555) 456-7890",
        "insurance_id": "UHC-321654987",
        "payer_name": "UnitedHealthcare",
        "conditions": [
            {"code": "C61", "name": "Prostate cancer"},
            {"code": "N18.3", "name": "Chronic kidney disease"}
        ],
        "medications": [
            {"name": "Lisinopril 20mg", "frequency": "daily"},
            {"name": "Metformin 1000mg", "frequency": "twice daily"},
            {"name": "Amlodipine 5mg", "frequency": "daily"}
        ],
        "allergies": ["Sulfa drugs", "Aspirin"]
    }

    clinical_notes["patient-001"] = [
        {
            "id": "note-001-1",
            "patient_id": "patient-001",
            "note_type": "Progress Note",
            "content": """Chief Complaint: Persistent low back pain for 6 weeks

History of Present Illness:
Patient is a 58-year-old male presenting with chronic low back pain that began approximately 6 weeks ago. 
The pain is localized to the lumbar region, worse with movement and prolonged sitting. 
Patient reports radiation down the left leg (L5 distribution) with occasional numbness.
Patient has tried over-the-counter ibuprofen with minimal relief. 
Physical therapy was attempted for 4 weeks with modest improvement.

Past Medical History:
- Hypertension (well controlled on Lisinopril 10mg daily)
- Type 2 Diabetes (diet controlled)
- Hyperlipidemia

Medications:
- Lisinopril 10mg daily
- Ibuprofen 400mg as needed for pain
- Atorvastatin 20mg daily

Physical Examination:
- Vital Signs: BP 128/82, HR 72, Temp 98.6°F
- Weight: 185 lbs, Height: 5'10"
- General: Alert, oriented, in mild distress due to pain
- Back: Limited range of motion, tenderness at L4-L5
- Neurological: Sensation intact, motor strength 5/5 bilateral

Assessment:
1. Low back pain with radiculopathy - L4-L5 disc herniation suspected
2. Hypertension - controlled
3. Type 2 Diabetes - controlled

Plan:
1. Order MRI of lumbar spine without contrast
2. Continue current medications
3. Referral to physical therapy
4. Follow up in 2 weeks or sooner if symptoms worsen

The patient has failed 6 weeks of conservative treatment including physical therapy and NSAIDs.
Given the radicular symptoms and failure of conservative management, MRI is medically necessary.""",
            "created_at": "2025-03-15T10:30:00",
            "provider": "Dr. Emily Williams",
            "facility": "Boston Medical Associates"
        }
    ]

    clinical_notes["patient-002"] = [
        {
            "id": "note-002-1",
            "patient_id": "patient-002",
            "note_type": "Orthopedic Consultation",
            "content": """Consultation: Right Shoulder Pain

History:
45-year-old female presents with right shoulder pain for 3 months. 
Patient reports pain with overhead activities and difficulty sleeping on the affected side.
Patient reports catching/locking sensation. Conservative treatment included:
- Physical therapy for 6 weeks with minimal improvement
- Naproxen 500mg twice daily
- Ice and rest

Physical Exam:
- Right shoulder: Positive Hawkins test, positive Neer impingement sign
- Range of motion: Forward flexion 120°, external rotation 30°
- Strength: 4/5 supraspinatus
- No obvious atrophy

Imaging:
- X-ray dated 3/10/2025: Mild degenerative changes, no acute fracture
- MRI recommended for further evaluation

Assessment:
- Suspected rotator cuff tear (partial thickness)
- Impingement syndrome
- Failed conservative treatment

Plan:
1. MRI right shoulder without contrast to evaluate rotator cuff
2. If tear confirmed, consider orthopedic referral for surgical evaluation
3. Continue Naproxen as needed
4. Activity modification

Patient has failed 6 weeks of conservative therapy and symptoms are progressing.""",
            "created_at": "2025-03-14T14:00:00",
            "provider": "Dr. Robert Martinez",
            "facility": "Cambridge Orthopedic Associates"
        }
    ]

    clinical_notes["patient-003"] = [
        {
            "id": "note-003-1",
            "patient_id": "patient-003",
            "note_type": "Oncology Follow-up",
            "content": """Oncology Follow-up Visit

Patient: Michael Chen
DOB: 11/8/1955

Chief Complaint: Follow-up for prostate cancer, staging workup

History:
70-year-old male with newly diagnosed prostate cancer (Gleason 7(3+4), PSA 8.2 ng/mL).
Staging workup in progress. Patient reports occasional difficulty urinating, 
no bone pain, no weight loss. Otherwise feeling well.

Past Medical History:
- Benign prostatic hyperplasia
- Hypertension
- Type 2 Diabetes
- Chronic kidney disease stage 2

Current Medications:
- Lisinopril 20mg daily
- Metformin 1000mg twice daily
- Amlodipine 5mg daily
- Tamsulosin 0.4mg nightly

Allergies: Sulfa drugs, Aspirin

Physical Exam:
- Vitals: BP 138/88, HR 76, Weight 172 lbs
- General: Alert, appears well
- GU: Mild benign prostatic enlargement on DRE
- No lymphadenopathy
- No bone tenderness

Assessment:
1. Prostate cancer, clinical stage T1cN0M0
2. Need staging imaging prior to treatment planning

Plan:
1. CT abdomen/pelvis for lymph node evaluation
2. Bone scan
3. PSA monitoring
4. Urology follow-up scheduled

Given the PSA level and Gleason score, staging imaging is indicated per NCCN guidelines.""",
            "created_at": "2025-03-16T09:00:00",
            "provider": "Dr. Jennifer Park",
            "facility": "Dana-Farber Cancer Institute"
        }
    ]


# Initialize demo data on startup
initialize_demo_data()


# ============ API Endpoints ============

@app.get("/")
async def root():
    return {
        "name": "AutoAuth Agent API",
        "version": "1.0.0",
        "description": "Autonomous Prior Authorization Platform",
        "status": "running"
    }


# ============ Patient Endpoints ============

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
    patient_id = f"patient-{uuid.uuid4().hex[:8]}"
    patient_data = patient.model_dump()
    patient_data["id"] = patient_id
    patient_data["conditions"] = []
    patient_data["medications"] = []
    patient_data["allergies"] = []
    patients[patient_id] = patient_data
    return patient_data


# ============ Clinical Notes Endpoints ============

@app.get("/api/patients/{patient_id}/notes")
async def get_patient_notes(patient_id: str):
    return {"notes": clinical_notes.get(patient_id, [])}


@app.post("/api/clinical/notes")
async def create_clinical_note(note: ClinicalNoteCreate):
    note_id = f"note-{uuid.uuid4().hex[:8]}"
    note_data = note.model_dump()
    note_data["id"] = note_id
    note_data["created_at"] = datetime.now().isoformat()
    if note.patient_id not in clinical_notes:
        clinical_notes[note.patient_id] = []
    clinical_notes[note.patient_id].append(note_data)
    return note_data


# ============ Authorization Endpoints ============

@app.post("/api/auth/initiate")
async def initiate_authorization(request: InitiateAuthRequest, background_tasks: BackgroundTasks):
    """Initiate a new prior authorization request."""

    if request.patient_id not in patients:
        raise HTTPException(status_code=404, detail="Patient not found")

    auth_id = f"auth-{uuid.uuid4().hex[:8]}"
    patient = patients[request.patient_id]

    auth_request_data = {
        "id": auth_id,
        "patient_id": request.patient_id,
        "patient": patient,          # full dict stored for API responses
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

    return {
        "auth_id": auth_id,
        "status": "pending",
        "message": "Authorization request initiated. Processing in background.",
        "patient": patient
    }


async def run_workflow(auth_id: str):
    """Run the authorization workflow in the background."""

    auth_request = auth_requests.get(auth_id)
    if not auth_request:
        return

    patient_id = auth_request["patient_id"]
    notes_data = clinical_notes.get(patient_id, [])

    # ---- Note objects ----
    class MockClinicalNote:
        def __init__(self, data):
            self.id = data.get("id", "")
            self.patient_id = data.get("patient_id", "")
            self.note_type = data.get("note_type", "")
            self.content = data.get("content", "")
            self.created_at = datetime.fromisoformat(
                data.get("created_at", datetime.now().isoformat())
            )
            self.provider = data.get("provider", "")
            self.facility = data.get("facility", "")

    notes = [MockClinicalNote(note) for note in notes_data]

    # ---- Auth request object — patient is a proper object, not a raw dict ----
    class MockAuthRequest:
        def __init__(self, data):
            self.id = data["id"]
            self.patient_id = data["patient_id"]
            self.service_type = data["service_type"]
            self.cpt_code = data["cpt_code"]
            self.icd10_code = data["icd10_code"]
            # Wrap the patient dict so agents can do auth_request.patient.first_name etc.
            raw_patient = data.get("patient")
            self.patient = PatientObject(raw_patient) if isinstance(raw_patient, dict) else raw_patient

    mock_auth = MockAuthRequest(auth_request)

    async def workflow_callback(state):
        # Serialise datetime objects before storing
        serialisable = json.loads(json.dumps(state, default=str))
        workflow_states[auth_id] = serialisable
        # Mirror status into auth_requests so the list endpoint stays in sync
        auth_requests[auth_id]["status"] = state.get("current_state", "pending")
        auth_requests[auth_id]["updated_at"] = datetime.now().isoformat()

    try:
        result = await workflow.execute_workflow(mock_auth, notes, workflow_callback)
        auth_requests[auth_id].update({
            "status": result.get("status", "completed"),
            "workflow_result": json.loads(json.dumps(result, default=str)),
            "updated_at": datetime.now().isoformat()
        })
        workflow_states[auth_id] = json.loads(json.dumps(result, default=str))
    except Exception as e:
        auth_requests[auth_id]["status"] = "error"
        auth_requests[auth_id]["error"] = str(e)
        auth_requests[auth_id]["updated_at"] = datetime.now().isoformat()


@app.get("/api/auth/{auth_id}")
async def get_authorization(auth_id: str):
    if auth_id not in auth_requests:
        raise HTTPException(status_code=404, detail="Authorization not found")
    auth = auth_requests[auth_id]
    workflow_state = workflow_states.get(auth_id)
    return {"auth": auth, "workflow_state": workflow_state}


@app.get("/api/auth/{auth_id}/trace")
async def get_workflow_trace(auth_id: str):
    if auth_id not in auth_requests:
        raise HTTPException(status_code=404, detail="Authorization not found")
    workflow_state = workflow_states.get(auth_id, {})
    return {
        "auth_id": auth_id,
        "agents": workflow_state.get("agents", {}),
        "processing_log": workflow_state.get("processing_log", []),
        "current_state": workflow_state.get("current_state", "pending"),
        "clinical_evidence": workflow_state.get("clinical_evidence"),
        "policy_match": workflow_state.get("policy_match"),
        "submission_result": workflow_state.get("submission_result"),
        "appeal_letter": workflow_state.get("appeal_letter")
    }


@app.get("/api/auth")
async def list_authorizations():
    return {"authorizations": list(auth_requests.values())}


# ============ Demo/Scenario Endpoints ============

@app.post("/api/demo/scenario")
async def load_scenario(request: ScenarioRequest):
    scenario_id = request.scenario_id
    scenarios = {
        "cardiology-mri": {
            "patient_id": "patient-001",
            "service_type": "mri",
            "cpt_code": "72148",
            "icd10_code": "M54.5",
            "title": "Lumbar Spine MRI",
            "description": "Chronic back pain with radiculopathy - failed 6 weeks PT"
        },
        "orthopedics-mri": {
            "patient_id": "patient-002",
            "service_type": "mri",
            "cpt_code": "73221",
            "icd10_code": "M75.10",
            "title": "Shoulder MRI for Rotator Cuff",
            "description": "Failed 6 weeks PT, suspected rotator cuff tear"
        },
        "oncology-ct": {
            "patient_id": "patient-003",
            "service_type": "ct_scan",
            "cpt_code": "74177",
            "icd10_code": "C61",
            "title": "CT Staging for Prostate Cancer",
            "description": "Newly diagnosed prostate cancer, staging workup"
        }
    }

    if scenario_id not in scenarios:
        raise HTTPException(status_code=404, detail="Scenario not found")

    scenario = scenarios[scenario_id]
    patient = patients[scenario["patient_id"]]
    notes = clinical_notes.get(scenario["patient_id"], [])

    return {"scenario": scenario, "patient": patient, "clinical_notes": notes}


# ============ Dashboard Endpoints ============

@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    total = len(auth_requests)
    approved = sum(
        1 for a in auth_requests.values()
        if str(a.get("status", "")).lower() in ["approved"]
    )
    denied = sum(
        1 for a in auth_requests.values()
        if str(a.get("status", "")).lower() in ["denied", "appeal_denied"]
    )
    pending = total - approved - denied

    completed = approved + denied
    approval_rate = (approved / completed * 100) if completed > 0 else 0

    return {
        "total_requests": total,
        "approved": approved,
        "denied": denied,
        "pending": pending,
        "approval_rate": round(approval_rate, 1),
        "avg_processing_time_seconds": 45.2,
        "total_cost_saved": total * 70,
        "appeals_success_rate": 42.5
    }


@app.get("/api/dashboard/recent-activity")
async def get_recent_activity():
    activities = []
    for auth_id, auth in list(auth_requests.items())[-10:]:
        patient_data = auth.get("patient", {})
        first = patient_data.get("first_name", "") if isinstance(patient_data, dict) else ""
        last = patient_data.get("last_name", "") if isinstance(patient_data, dict) else ""
        activities.append({
            "auth_id": auth_id,
            "patient": f"{first} {last}".strip() or "Unknown",
            "service": auth.get("service_type", "Unknown"),
            "status": auth.get("status", "pending"),
            "timestamp": auth.get("updated_at", auth.get("created_at", ""))
        })
    return {"activities": list(reversed(activities))}


# ============ Event Stream ============

@app.get("/api/events/{auth_id}")
async def event_stream(auth_id: str):
    async def event_generator():
        while True:
            if auth_id in workflow_states:
                state = workflow_states[auth_id]
                yield f"data: {json.dumps(state, default=str)}\n\n"
                current = str(state.get("current_state", "")).lower()
                if current in ["approved", "denied", "completed", "requires_human_review"]:
                    break
            await asyncio.sleep(1)
    return EventSourceResponse(event_generator())


# ============ Utility Endpoints ============

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "clinical_reader": "ready",
            "policy_agent": "ready",
            "submission_agent": "ready",
            "appeal_agent": "ready"
        }
    }


@app.post("/api/auth/{auth_id}/approve")
async def manually_approve(auth_id: str):
    if auth_id in auth_requests:
        auth_requests[auth_id]["status"] = "approved"
        return {"success": True, "status": "approved"}
    raise HTTPException(status_code=404, detail="Authorization not found")


@app.post("/api/auth/{auth_id}/deny")
async def manually_deny(auth_id: str):
    if auth_id in auth_requests:
        auth_requests[auth_id]["status"] = "denied"
        return {"success": True, "status": "denied"}
    raise HTTPException(status_code=404, detail="Authorization not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)