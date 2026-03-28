# AutoAuth Agent

Autonomous prior authorization platform. Submits clinical requests to a mock payer FHIR server, predicts approval probability before submission, generates appeal letters preemptively when denial risk is high, and automatically resubmits appeals if denied.

---

## Architecture

```
Port 3000  Provider UI     Next.js — clinician dashboard
Port 8000  Backend         FastAPI — agent orchestration
Port 8001  FHIR Server     FastAPI — mock payer + decision API
Port 3001  Payer UI        Next.js — payer reviewer dashboard
```

All four services run independently. The provider UI proxies `/api/*` to the backend via Next.js rewrites (no separate API routes needed).

---

## Workflow

```
Triage → Clinical Evidence → Policy Match → Validation
  → Prediction Engine (approval probability)
  → Decision Engine:
      high prob  → Submit directly
      medium     → Submit with enhanced justification
      low prob   → Generate appeal letter NOW, attach to submission
  → Submit to FHIR Server (port 8001)
  → Payer reviews on Payer UI (port 3001)
  → if approved  → done ✓
  → if denied    → Appeal already written → instantly resubmit
  → Payer reviews appeal → appeal_approved / appeal_denied
```

---

## Services

### Backend (`/backend`) — Port 8000

FastAPI application. All agent logic lives here.

**Agents:**
- `TriageAgent` — classifies urgency
- `ClinicalReaderAgent` — extracts diagnoses, medications, procedures from clinical notes using GPT
- `PolicyAgent` — retrieves payer policy requirements and scores clinical evidence match
- `PredictionAgent` — computes approval probability from policy match × necessity × payer strictness
- `DecisionEngine` — picks submission strategy based on probability
- `SubmissionAgent` — builds FHIR R4 Bundle, POSTs to port 8001, polls for decision
- `AppealAgent` — generates full appeal letter using real provider info (no placeholders)
- `AppealSubmissionAgent` — resubmits bundle + appeal letter to FHIR server

**Key files:**
```
backend/main.py                          API routes, demo data, 6 patients + clinical notes
backend/src/orchestration/workflow.py   Full workflow with prediction engine
backend/src/agents/clinical_reader.py   LLM-based clinical evidence extraction
backend/src/agents/policy_agent.py      Policy retrieval and matching
backend/src/agents/submission_agent.py  FHIR bundle builder + HTTP submission
backend/src/agents/appeal_agent.py      Appeal letter generation with real provider info
```

**Demo patients:**
| ID | Patient | Payer | Scenario |
|----|---------|-------|---------|
| patient-001 | John Smith | BCBS | Lumbar spine MRI — low back pain |
| patient-002 | Sarah Johnson | Aetna | Shoulder MRI — rotator cuff |
| patient-003 | Michael Chen | UHC | CT abdomen — prostate cancer staging |
| patient-004 | Maria Rodriguez | Cigna | Dupilumab — uncontrolled asthma |
| patient-005 | James Williams | Medicare | CRT-D implant — CHF EF 30% |
| patient-006 | Emily Patel | BCBS | Natalizumab — active RRMS |

---

### FHIR Server (`/fhir_server`) — Port 8001

Mock payer system. Receives FHIR R4 Bundles from the backend, stores them, exposes a decision API for the payer UI, and returns `ClaimResponse` resources on polling.

**Endpoints used by backend:**
```
POST /fhir/Bundle                Submit PA or appeal bundle
GET  /fhir/ClaimResponse/{id}    Poll for payer decision
```

**Endpoints used by payer UI:**
```
GET  /payer/queue                All pending/decided requests
GET  /payer/request/{id}         Full detail including appeal letter
POST /payer/review/{id}          Mark as under review
POST /payer/decide/{id}          Submit approve/deny decision
GET  /payer/stats                Dashboard stats
```

---

### Provider UI (`/frontend`) — Port 3000

Next.js 14 app. Clinician-facing dashboard.

**Pages:**
- `/` — Dashboard with live workflow visualization, scenario selector, authorization list, activity feed
- `/patients` — Patient list with conditions, medications, insurance, authorization history
- `/authorizations` — Full authorization list with detail modal showing appeal letters
- `/analytics` — Live charts: approval rate, service breakdown, timeline (recharts)
- `/settings` — LLM model, server URLs, mock mode toggle
- `/help` — Quick start guide, agent reference, FAQ, terminal commands

**Key components:**
```
WorkflowVisualization.tsx   Live pipeline view + prediction panel + appeal letter viewer
ScenarioSelector.tsx        6 demo scenario cards
AuthorizationList.tsx       Real-time list with 2s polling, safe null handling
LiveActivityFeed.tsx        Recent authorization events
```

---

### Payer UI (`/payer_ui`) — Port 3001

Next.js 14 app. Payer reviewer dashboard.

**Features:**
- Queue of all PA requests with appeal badge (`APPEAL`) for resubmissions
- Full detail modal: patient info, diagnoses, clinical summary, appeal letter (scrollable)
- Approve / Deny decision form with denial reason dropdown
- Stats header: total, pending, approved, denied, appeals
- Auto-polls every 3s so new submissions appear without refresh

---

## Running Locally

Start all four services, in this order:

```bash
# Terminal 1 — FHIR/Payer server
cd autoauth-agent
source venv/bin/activate          # same venv as backend
python fhir_server/fhir_payer_server.py

# Terminal 2 — Backend
cd backend
python main.py

# Terminal 3 — Provider UI
cd frontend
npm run dev                       # http://localhost:3000

# Terminal 4 — Payer UI
cd payer_ui
npm run dev                       # http://localhost:3001
```

**Python deps** (install once in your venv):
```bash
pip install fastapi uvicorn openai httpx python-dotenv pydantic
```

**Frontend deps** (install once each):
```bash
cd frontend && npm install
cd payer_ui && npm install
```

---

## Demo Flow

1. Open **Provider UI** at `localhost:3000`
2. Open **Payer UI** at `localhost:3001` in a second tab
3. Click a scenario card on the provider dashboard
4. Watch the workflow run: Triage → Clinical → Policy → Predict → Strategy → Submit
5. The **Prediction Engine** shows approval probability before submission
6. Once submitted, the FHIR server receives the bundle — the request appears in the payer queue
7. On the payer portal, click the request → read the clinical summary → Approve or Deny
8. The provider UI updates automatically when the decision comes in
9. If **denied**: the appeal letter was already generated (or generates now) → automatically resubmitted
10. The appeal appears in the payer queue with an `APPEAL` badge → reviewer decides again

---

## Environment

Copy `.env.example` to `.env` in the `backend/` directory and fill in your OpenAI API key.

The system runs without an API key in mock mode — set `DEMO_MODE=true` to use rule-based fallback logic instead of LLM calls.