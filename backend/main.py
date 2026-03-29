"""
FastAPI Main Application - AutoAuth Agent Platform
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import EventSourceResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid, asyncio, json
from datetime import datetime

from agents.clinical_reader import ClinicalReaderAgent
from agents.policy_agent import PolicyAgent
from agents.submission_agent import SubmissionAgent
from agents.appeal_agent import AppealAgent
from orchestration.workflow import AuthorizationWorkflow, create_workflow
from models.schemas import AuthorizationRequest, Patient, ClinicalNote, ServiceType, AuthStatus, DashboardStats
from openai import AsyncOpenAI

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

app = FastAPI(title="AutoAuth Agent API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

auth_requests: Dict[str, Dict[str, Any]] = {}
patients: Dict[str, Dict] = {}
clinical_notes: Dict[str, List[Dict]] = {}
workflow_states: Dict[str, Dict] = {}

clinical_reader  = ClinicalReaderAgent(llm_client=openai_client)
policy_agent     = PolicyAgent(llm_client=openai_client)
submission_agent = SubmissionAgent(mock_mode=False)
appeal_agent     = AppealAgent(llm_client=openai_client)
workflow         = create_workflow(clinical_reader, policy_agent, submission_agent, appeal_agent)


class InitiateAuthRequest(BaseModel):
    patient_id: str; service_type: str; cpt_code: str; icd10_code: str
    priority: Optional[str] = "standard"

class PatientCreate(BaseModel):
    mrn: str; first_name: str; last_name: str; date_of_birth: str; gender: str
    address: Optional[str] = None; phone: Optional[str] = None
    insurance_id: str; payer_name: str

class ClinicalNoteCreate(BaseModel):
    patient_id: str; note_type: str; content: str; provider: str; facility: str

class ScenarioRequest(BaseModel):
    scenario_id: str


class PatientObject:
    def __init__(self, d: Dict[str, Any]):
        self.id = d.get("id",""); self.mrn = d.get("mrn","")
        self.first_name = d.get("first_name",""); self.last_name = d.get("last_name","")
        self.date_of_birth = d.get("date_of_birth",""); self.gender = d.get("gender","")
        self.address = d.get("address",""); self.phone = d.get("phone","")
        self.insurance_id = d.get("insurance_id",""); self.payer_name = d.get("payer_name","")
        self.conditions = d.get("conditions",[]); self.medications = d.get("medications",[])
        self.allergies = d.get("allergies",[])


def _clean(raw): return str(raw).split(".")[-1].lower()


# ── Demo data ─────────────────────────────────────────────────────────────────

def initialize_demo_data():
    # ── Patients ──────────────────────────────────────────────────────────────
    patients["patient-001"] = {
        "id":"patient-001","mrn":"MRN-12345","first_name":"John","last_name":"Smith",
        "date_of_birth":"1965-03-15","gender":"male",
        "address":"123 Main St, Boston, MA 02101","phone":"(617) 555-1234",
        "insurance_id":"BCBS-789456123","payer_name":"Blue Cross Blue Shield",
        "conditions":[{"code":"M54.5","name":"Low back pain"},{"code":"I10","name":"Hypertension"}],
        "medications":[{"name":"Lisinopril 10mg","frequency":"daily"},{"name":"Ibuprofen 400mg","frequency":"as needed"}],
        "allergies":["Penicillin"]
    }
    patients["patient-002"] = {
        "id":"patient-002","mrn":"MRN-67890","first_name":"Sarah","last_name":"Johnson",
        "date_of_birth":"1978-07-22","gender":"female",
        "address":"456 Oak Ave, Cambridge, MA 02139","phone":"(617) 555-9876",
        "insurance_id":"AET-456789012","payer_name":"Aetna",
        "conditions":[{"code":"M75.10","name":"Rotator cuff tear"},{"code":"M25.51","name":"Shoulder pain"}],
        "medications":[{"name":"Naproxen 500mg","frequency":"twice daily"}],
        "allergies":[]
    }
    patients["patient-003"] = {
        "id":"patient-003","mrn":"MRN-11223","first_name":"Michael","last_name":"Chen",
        "date_of_birth":"1955-11-08","gender":"male",
        "address":"789 Pine Rd, Brookline, MA 02445","phone":"(617) 555-4567",
        "insurance_id":"UHC-321654987","payer_name":"UnitedHealthcare",
        "conditions":[{"code":"C61","name":"Prostate cancer"},{"code":"N18.3","name":"Chronic kidney disease"}],
        "medications":[{"name":"Lisinopril 20mg","frequency":"daily"},
                        {"name":"Metformin 1000mg","frequency":"twice daily"},
                        {"name":"Amlodipine 5mg","frequency":"daily"}],
        "allergies":["Sulfa drugs","Aspirin"]
    }
    patients["patient-004"] = {
        "id":"patient-004","mrn":"MRN-33445","first_name":"Maria","last_name":"Rodriguez",
        "date_of_birth":"1972-04-18","gender":"female",
        "address":"321 Elm St, Somerville, MA 02143","phone":"(617) 555-7890",
        "insurance_id":"CIG-112233445","payer_name":"Cigna",
        "conditions":[{"code":"J45.50","name":"Moderate persistent asthma"},{"code":"J30.1","name":"Allergic rhinitis"}],
        "medications":[{"name":"Albuterol inhaler","frequency":"as needed"},
                        {"name":"Fluticasone 250mcg","frequency":"twice daily"},
                        {"name":"Montelukast 10mg","frequency":"nightly"}],
        "allergies":["Aspirin","NSAIDs"]
    }
    patients["patient-005"] = {
        "id":"patient-005","mrn":"MRN-55667","first_name":"James","last_name":"Williams",
        "date_of_birth":"1948-09-30","gender":"male",
        "address":"654 Maple Dr, Newton, MA 02458","phone":"(617) 555-2345",
        "insurance_id":"MED-998877665","payer_name":"Medicare",
        "conditions":[{"code":"I25.10","name":"Coronary artery disease"},
                       {"code":"I50.9","name":"Congestive heart failure"},
                       {"code":"E11.9","name":"Type 2 diabetes"}],
        "medications":[{"name":"Metoprolol 50mg","frequency":"twice daily"},
                        {"name":"Furosemide 40mg","frequency":"daily"},
                        {"name":"Metformin 500mg","frequency":"twice daily"},
                        {"name":"Atorvastatin 40mg","frequency":"nightly"}],
        "allergies":["Contrast dye"]
    }
    patients["patient-006"] = {
        "id":"patient-006","mrn":"MRN-77889","first_name":"Emily","last_name":"Patel",
        "date_of_birth":"1990-12-05","gender":"female",
        "address":"987 Cedar Ln, Waltham, MA 02451","phone":"(617) 555-6789",
        "insurance_id":"BCBS-554433221","payer_name":"Blue Cross Blue Shield",
        "conditions":[{"code":"G35","name":"Multiple sclerosis"},{"code":"G43.909","name":"Migraine"}],
        "medications":[{"name":"Interferon beta-1a","frequency":"weekly injection"},
                        {"name":"Baclofen 10mg","frequency":"three times daily"},
                        {"name":"Sumatriptan 50mg","frequency":"as needed for migraine"}],
        "allergies":[]
    }

    # ── Clinical Notes ─────────────────────────────────────────────────────────
    clinical_notes["patient-001"] = [{"id":"note-001-1","patient_id":"patient-001",
        "note_type":"Progress Note","provider":"Dr. Emily Williams","facility":"Boston Medical Associates",
        "created_at":"2025-03-15T10:30:00","content":
"""Chief Complaint: Persistent low back pain for 6 weeks

History of Present Illness:
John Smith is a 58-year-old male presenting with chronic low back pain for 6 weeks. Pain is localized to the lumbar region, worse with movement and prolonged sitting. Reports radiation down the left leg (L5 distribution) with occasional numbness. Patient has tried OTC ibuprofen with minimal relief. Physical therapy attempted for 4 weeks with modest improvement.

Past Medical History: Hypertension, Type 2 Diabetes, Hyperlipidemia.
Medications: Lisinopril 10mg daily, Ibuprofen 400mg as needed, Atorvastatin 20mg daily.
Vital Signs: BP 128/82, HR 72, Temp 98.6F, Weight 185 lbs.

Physical Exam:
- Back: Limited ROM, tenderness at L4-L5
- Neurological: Sensation intact, motor strength 5/5 bilateral
- Straight leg raise: Positive at 45° left

Assessment:
1. Low back pain with radiculopathy - L4-L5 disc herniation suspected
2. Hypertension - controlled
3. Type 2 Diabetes - controlled

Plan: MRI lumbar spine without contrast.
Patient has failed 6 weeks of conservative treatment including physical therapy and NSAIDs.
Given the radicular symptoms, failure of conservative management, and suspected disc herniation, MRI is medically necessary."""}]

    clinical_notes["patient-002"] = [{"id":"note-002-1","patient_id":"patient-002",
        "note_type":"Orthopedic Consultation","provider":"Dr. Robert Martinez","facility":"Cambridge Orthopedic Associates",
        "created_at":"2025-03-14T14:00:00","content":
"""Consultation: Right Shoulder Pain

History: Sarah Johnson, 45-year-old female with right shoulder pain for 3 months.
Reports pain with overhead activities and difficulty sleeping on affected side. Catching/locking sensation noted.
Conservative treatment: Physical therapy 6 weeks with minimal improvement, Naproxen 500mg twice daily, ice and rest.

Physical Exam:
- Positive Hawkins test, positive Neer impingement sign
- ROM: Forward flexion 120°, external rotation 30°
- Strength: 4/5 supraspinatus, painful arc 60-120°
- X-ray 3/10/2025: Mild degenerative changes, no acute fracture

Assessment: Suspected rotator cuff tear (partial thickness), impingement syndrome. Failed conservative treatment.

Plan: MRI right shoulder without contrast to evaluate rotator cuff integrity.
Patient has failed 6 weeks of conservative therapy. Symptoms are progressing. MRI is required before surgical planning."""}]

    clinical_notes["patient-003"] = [{"id":"note-003-1","patient_id":"patient-003",
        "note_type":"Oncology Follow-up","provider":"Dr. Jennifer Park","facility":"Dana-Farber Cancer Institute",
        "created_at":"2025-03-16T09:00:00","content":
"""Oncology Follow-up: Michael Chen, 70-year-old male.

Newly diagnosed prostate cancer: Gleason score 7 (3+4), PSA 8.2 ng/mL.
PMH: BPH, Hypertension, Type 2 Diabetes, CKD stage 2.
Medications: Lisinopril 20mg, Metformin 1000mg BID, Amlodipine 5mg, Tamsulosin 0.4mg.
Allergies: Sulfa drugs, Aspirin. Vitals: BP 138/88, HR 76, Weight 172 lbs.

Physical Exam: Alert, no lymphadenopathy, no bone tenderness. GU: mild BPH on DRE.

Assessment: Prostate cancer clinical stage T1cN0M0. Staging workup required prior to treatment planning.

Plan: CT abdomen/pelvis for lymph node evaluation. Per NCCN guidelines for intermediate-risk prostate cancer, CT staging is indicated. Patient has Gleason 7 disease with PSA >4; imaging necessary to rule out regional lymph node involvement."""}]

    clinical_notes["patient-004"] = [{"id":"note-004-1","patient_id":"patient-004",
        "note_type":"Pulmonology Consultation","provider":"Dr. Aisha Hassan","facility":"Brigham and Women's Hospital",
        "created_at":"2025-03-18T11:00:00","content":
"""Pulmonology Consultation: Maria Rodriguez, 52-year-old female.

Chief Complaint: Worsening asthma control despite current therapy.

History: Moderate persistent asthma diagnosed 2015. Currently on Fluticasone 250mcg BID and albuterol PRN. Reports daily symptoms and nocturnal awakening 3x/week. Two ED visits in past 6 months. FEV1 68% predicted at last PFT.
Allergies: Aspirin, NSAIDs (triggers bronchospasm). PMH: Allergic rhinitis.

Physical Exam: BP 118/76, HR 82, O2 Sat 96% on room air. Mild expiratory wheeze bilaterally. No accessory muscle use at rest.

Assessment: Moderate persistent asthma, uncontrolled on current regimen. Biologic therapy indicated per GINA Step 5 guidelines.

Plan: Initiate dupilumab (Dupixent) 300mg SC every 2 weeks. Prior authorization required. Patient's eosinophil count 450 cells/μL and total IgE 280 IU/mL support biologic candidacy. Step-up therapy justified given failure of high-dose ICS and systemic impact."""}]

    clinical_notes["patient-005"] = [{"id":"note-005-1","patient_id":"patient-005",
        "note_type":"Cardiology Consultation","provider":"Dr. Marcus Lee","facility":"Massachusetts General Hospital",
        "created_at":"2025-03-17T13:30:00","content":
"""Cardiology Consultation: James Williams, 76-year-old male.

Chief Complaint: Worsening dyspnea on exertion, reduced exercise tolerance.

History: Known CAD (3-vessel disease, CABG 2018), CHF with EF 35%, Type 2 Diabetes. Presenting with NYHA Class III heart failure symptoms worsening over 6 weeks. Recent weight gain of 8 lbs.
Medications: Metoprolol 50mg BID, Furosemide 40mg daily, Metformin 500mg BID, Atorvastatin 40mg.

Physical Exam: BP 142/88, HR 78, O2 Sat 94% on RA, Weight 218 lbs (+8 lbs from last visit).
JVD present. Bilateral basilar rales. +2 pitting edema ankles.

Echo (3/1/2025): EF 30% (decreased from 35%), moderate mitral regurgitation.
BNP 820 pg/mL. Creatinine 1.8 mg/dL.

Assessment: Decompensated CHF, CAD. CRT-D device indicated per ACC/AHA guidelines (EF<35%, NYHA III, QRS 140ms).

Plan: Cardiac resynchronization therapy with defibrillator (CRT-D) implantation. Prior authorization required. LBBB on EKG with QRS 142ms; patient meets Class I indication per 2022 ACC/AHA guidelines."""}]

    clinical_notes["patient-006"] = [{"id":"note-006-1","patient_id":"patient-006",
        "note_type":"Neurology Follow-up","provider":"Dr. Priya Sharma","facility":"Brigham MS Center",
        "created_at":"2025-03-19T10:00:00","content":
"""Neurology Follow-up: Emily Patel, 34-year-old female.

Chief Complaint: Relapsing-remitting MS — disease activity on current treatment.

History: RRMS diagnosed 2018, currently on Interferon beta-1a. Two relapses in past 12 months (optic neuritis Jan 2025, sensory relapse Oct 2024). MRI 2/2025: 3 new T2 lesions, 1 gadolinium-enhancing lesion. EDSS 2.5.
Current medications: Interferon beta-1a weekly, Baclofen 10mg TID, Sumatriptan PRN.

Physical Exam: EDSS 2.5. Mild right hand coordination deficit. Vision 20/30 right eye post-optic neuritis.

Assessment: Active RRMS with suboptimal response to interferon therapy. Escalation to high-efficacy DMT indicated.

Plan: Transition to natalizumab (Tysabri) 300mg IV every 4 weeks. JC antibody negative (index 0.14). Prior authorization required. Patient meets criteria: 2 relapses in 12 months + active MRI lesions on current DMT. High-efficacy therapy justified per ECTRIMS guidelines."""}]

initialize_demo_data()


# ── Helpers ───────────────────────────────────────────────────────────────────

PROVIDER_INFO = {
    "patient-001": {"provider": "Dr. Emily Williams, MD", "facility": "Boston Medical Associates",
                     "address": "750 Harrison Ave, Boston, MA 02118", "phone": "(617) 638-8000", "fax": "(617) 638-8001"},
    "patient-002": {"provider": "Dr. Robert Martinez, MD", "facility": "Cambridge Orthopedic Associates",
                     "address": "1 Kendall Square, Cambridge, MA 02139", "phone": "(617) 494-3500", "fax": "(617) 494-3501"},
    "patient-003": {"provider": "Dr. Jennifer Park, MD", "facility": "Dana-Farber Cancer Institute",
                     "address": "450 Brookline Ave, Boston, MA 02215", "phone": "(617) 632-3000", "fax": "(617) 632-3001"},
    "patient-004": {"provider": "Dr. Aisha Hassan, MD", "facility": "Brigham and Women's Hospital",
                     "address": "75 Francis St, Boston, MA 02115", "phone": "(617) 732-5500", "fax": "(617) 732-5501"},
    "patient-005": {"provider": "Dr. Marcus Lee, MD, FACC", "facility": "Massachusetts General Hospital",
                     "address": "55 Fruit St, Boston, MA 02114", "phone": "(617) 726-2000", "fax": "(617) 726-2001"},
    "patient-006": {"provider": "Dr. Priya Sharma, MD, PhD", "facility": "Brigham MS Center",
                     "address": "60 Fenwood Rd, Boston, MA 02115", "phone": "(617) 732-7432", "fax": "(617) 732-7433"},
}


# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"name": "AutoAuth Agent API", "version": "1.0.0", "status": "running"}

@app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/patients")
async def list_patients():
    return {"patients": list(patients.values())}

@app.get("/api/patients/{patient_id}")
async def get_patient(patient_id: str):
    if patient_id not in patients:
        raise HTTPException(404, "Patient not found")
    return patients[patient_id]

@app.post("/api/patients")
async def create_patient(patient: PatientCreate):
    pid = f"patient-{uuid.uuid4().hex[:8]}"
    data = {**patient.model_dump(), "id": pid, "conditions": [], "medications": [], "allergies": []}
    patients[pid] = data
    return data

@app.get("/api/patients/{patient_id}/notes")
async def get_notes(patient_id: str):
    return {"notes": clinical_notes.get(patient_id, [])}

@app.post("/api/clinical/notes")
async def create_note(note: ClinicalNoteCreate):
    nid = f"note-{uuid.uuid4().hex[:8]}"
    data = {**note.model_dump(), "id": nid, "created_at": datetime.now().isoformat()}
    clinical_notes.setdefault(note.patient_id, []).append(data)
    return data


@app.post("/api/auth/initiate")
async def initiate_authorization(request: InitiateAuthRequest, background_tasks: BackgroundTasks):
    if request.patient_id not in patients:
        raise HTTPException(404, "Patient not found")

    auth_id = f"auth-{uuid.uuid4().hex[:8]}"
    patient = patients[request.patient_id]
    provider_info = PROVIDER_INFO.get(request.patient_id, {
        "provider": "Dr. Attending Physician, MD",
        "facility": "Boston Area Medical Center",
        "address": "100 Medical Center Dr, Boston, MA 02101",
        "phone": "(617) 555-0000",
        "fax": "(617) 555-0001"
    })

    auth_request_data = {
        "id": auth_id, "patient_id": request.patient_id, "patient": patient,
        "service_type": request.service_type, "cpt_code": request.cpt_code,
        "icd10_code": request.icd10_code, "priority": request.priority,
        "status": "pending", "provider_info": provider_info,
        "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat()
    }
    auth_requests[auth_id] = auth_request_data
    background_tasks.add_task(run_workflow, auth_id)
    return {"auth_id": auth_id, "status": "pending",
            "message": "Processing started.", "patient": patient}


async def run_workflow(auth_id: str):
    auth_request = auth_requests.get(auth_id)
    if not auth_request: return

    notes_data    = clinical_notes.get(auth_request["patient_id"], [])
    provider_info = auth_request.get("provider_info", {})

    class MockNote:
        def __init__(self, d):
            self.id = d.get("id",""); self.patient_id = d.get("patient_id","")
            self.note_type = d.get("note_type",""); self.content = d.get("content","")
            self.created_at = datetime.fromisoformat(d.get("created_at", datetime.now().isoformat()))
            self.provider = d.get("provider",""); self.facility = d.get("facility","")

    notes = [MockNote(n) for n in notes_data]

    class MockAuth:
        def __init__(self, d):
            self.id = d["id"]; self.patient_id = d["patient_id"]
            self.service_type = d["service_type"]; self.cpt_code = d["cpt_code"]
            self.icd10_code = d["icd10_code"]
            raw = d.get("patient")
            self.patient = PatientObject(raw) if isinstance(raw, dict) else raw
            # Attach provider info so appeal agent can use real names
            self.provider_name    = provider_info.get("provider", "Dr. Attending Physician")
            self.provider_facility= provider_info.get("facility", "Boston Medical Center")
            self.provider_address = provider_info.get("address", "100 Medical Dr, Boston MA")
            self.provider_phone   = provider_info.get("phone", "(617) 555-0000")
            self.provider_fax     = provider_info.get("fax", "(617) 555-0001")

    mock_auth = MockAuth(auth_request)

    async def callback(state):
        ser = json.loads(json.dumps(state, default=str))
        ser["current_state"] = _clean(ser.get("current_state", "pending"))
        workflow_states[auth_id] = ser
        auth_requests[auth_id]["status"] = ser["current_state"]
        auth_requests[auth_id]["updated_at"] = datetime.now().isoformat()

    try:
        result = await workflow.execute_workflow(mock_auth, notes, callback)
        ser = json.loads(json.dumps(result, default=str))
        clean = _clean(ser.get("status") or ser.get("current_state") or "completed")
        ser["status"] = clean; ser["current_state"] = clean
        auth_requests[auth_id].update({"status": clean, "workflow_result": ser,
                                        "updated_at": datetime.now().isoformat()})
        workflow_states[auth_id] = ser
    except Exception as e:
        import traceback
        print(f"[WORKFLOW ERROR] {traceback.format_exc()}")
        auth_requests[auth_id]["status"] = "error"
        auth_requests[auth_id]["error"] = str(e)
        auth_requests[auth_id]["updated_at"] = datetime.now().isoformat()


@app.get("/api/auth/{auth_id}")
async def get_authorization(auth_id: str):
    if auth_id not in auth_requests:
        raise HTTPException(404, "Not found")
    return {"auth": auth_requests[auth_id], "workflow_state": workflow_states.get(auth_id)}

@app.get("/api/auth/{auth_id}/trace")
async def get_trace(auth_id: str):
    if auth_id not in auth_requests:
        raise HTTPException(404, "Not found")
    ws = workflow_states.get(auth_id, {})
    raw = ws.get("current_state") or ws.get("status") or "pending"
    current = _clean(raw)
    return {
        "auth_id": auth_id,
        "agents": ws.get("agents", {}),
        "processing_log": ws.get("processing_log", []),
        "current_state": current,
        "clinical_evidence": ws.get("clinical_evidence"),
        "policy_match": ws.get("policy_match"),
        "prediction": ws.get("prediction"),
        "submission_result": ws.get("submission_result"),
        "appeal_letter": ws.get("appeal_letter"),
        "appeal_submission_result": ws.get("appeal_submission_result"),
        "appeal_decision": ws.get("appeal_decision"),
        "denial_analysis": ws.get("denial_analysis"),
    }

@app.get("/api/auth")
async def list_authorizations():
    return {"authorizations": list(auth_requests.values())}

@app.post("/api/auth/{auth_id}/approve")
async def manually_approve(auth_id: str):
    if auth_id not in auth_requests: raise HTTPException(404, "Not found")
    auth_requests[auth_id]["status"] = "approved"
    return {"success": True}

@app.post("/api/auth/{auth_id}/deny")
async def manually_deny(auth_id: str):
    if auth_id not in auth_requests: raise HTTPException(404, "Not found")
    auth_requests[auth_id]["status"] = "denied"
    return {"success": True}


@app.post("/api/demo/scenario")
async def load_scenario(request: ScenarioRequest):
    scenarios = {
        "cardiology-mri":   {"patient_id":"patient-001","service_type":"mri","cpt_code":"72148","icd10_code":"M54.5","title":"Lumbar Spine MRI","description":"Chronic back pain with radiculopathy"},
        "orthopedics-mri":  {"patient_id":"patient-002","service_type":"mri","cpt_code":"73221","icd10_code":"M75.10","title":"Shoulder MRI","description":"Failed 6 weeks PT, suspected rotator cuff tear"},
        "oncology-ct":      {"patient_id":"patient-003","service_type":"ct_scan","cpt_code":"74177","icd10_code":"C61","title":"CT Staging — Prostate Cancer","description":"Newly diagnosed prostate cancer staging workup"},
        "asthma-biologic":  {"patient_id":"patient-004","service_type":"prescription","cpt_code":"J0173","icd10_code":"J45.50","title":"Dupilumab — Uncontrolled Asthma","description":"Step 5 biologic therapy, failed ICS"},
        "cardiology-device":{"patient_id":"patient-005","service_type":"surgery","cpt_code":"33249","icd10_code":"I50.9","title":"CRT-D Implant — CHF","description":"EF 30%, NYHA Class III, LBBB"},
        "ms-biologic":      {"patient_id":"patient-006","service_type":"prescription","cpt_code":"J2323","icd10_code":"G35","title":"Natalizumab — Active RRMS","description":"Two relapses + new MRI lesions on interferon"},
    }
    if request.scenario_id not in scenarios:
        raise HTTPException(404, "Scenario not found")
    s = scenarios[request.scenario_id]
    return {"scenario": s, "patient": patients[s["patient_id"]],
            "clinical_notes": clinical_notes.get(s["patient_id"], [])}


@app.get("/api/dashboard/stats")
async def get_stats():
    total    = len(auth_requests)
    approved = sum(1 for a in auth_requests.values() if _clean(a.get("status","")) in ["approved","appeal_approved"])
    denied   = sum(1 for a in auth_requests.values() if _clean(a.get("status","")) in ["denied","appeal_denied"])
    pending  = max(total - approved - denied, 0)
    rate     = (approved / (approved + denied) * 100) if (approved + denied) > 0 else 0
    return {
        "total_requests": total, "approved": approved, "denied": denied,
        "pending": pending, "approval_rate": round(rate, 1),
        "avg_processing_time_seconds": 45.2,
        "total_cost_saved": total * 70, "appeals_success_rate": 42.5
    }

@app.get("/api/dashboard/recent-activity")
async def recent_activity():
    activities = []
    for auth_id, auth in list(auth_requests.items())[-15:]:
        pd = auth.get("patient", {})
        first = pd.get("first_name","") if isinstance(pd, dict) else ""
        last  = pd.get("last_name","")  if isinstance(pd, dict) else ""
        activities.append({
            "auth_id": auth_id,
            "patient": f"{first} {last}".strip() or "Unknown",
            "service": auth.get("service_type","Unknown"),
            "status":  _clean(auth.get("status","pending")),
            "timestamp": auth.get("updated_at", auth.get("created_at",""))
        })
    return {"activities": list(reversed(activities))}

@app.get("/api/events/{auth_id}")
async def event_stream(auth_id: str):
    async def gen():
        while True:
            if auth_id in workflow_states:
                ws = {**workflow_states[auth_id]}
                ws["current_state"] = _clean(ws.get("current_state","pending"))
                yield f"data: {json.dumps(ws, default=str)}\n\n"
                if ws["current_state"] in ["approved","appeal_submission","appeal_approved","requires_human_review"]:
                    break
            await asyncio.sleep(1)
    from fastapi.responses import EventSourceResponse
    return EventSourceResponse(gen())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)