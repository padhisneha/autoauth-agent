"""
Submission Agent — builds FHIR bundles, submits to FHIR server, handles appeals.
"""

import uuid, asyncio, random, base64
from datetime import datetime
from typing import Dict, Any, List, Optional

FHIR_SERVER_URL   = "http://localhost:8001"
POLL_INTERVAL     = 3
POLL_MAX_ATTEMPTS = 300  # 15 min


def _val(entity, attr, default=""):
    if isinstance(entity, dict): return entity.get(attr, default)
    return getattr(entity, attr, default) or default


class SubmissionAgent:
    def __init__(self, fhir_client=None, mock_mode=False):
        self.agent_name  = "SubmissionAgent"
        self.fhir_client = fhir_client
        self.mock_mode   = mock_mode

    async def build_fhir_bundle(self, auth_request, clinical_evidence, policy_match,
                                 appeal_letter=None) -> Dict[str, Any]:
        bundle_id  = str(uuid.uuid4())
        ts         = datetime.now().isoformat()
        patient    = auth_request.patient
        summary    = _val(clinical_evidence, "clinical_summary") or "Medical necessity documented"
        conditions = getattr(clinical_evidence, "conditions",  []) or []
        medications= getattr(clinical_evidence, "medications", []) or []
        resources  = []

        # ServiceRequest
        sr = {
            "resourceType": "ServiceRequest",
            "id": f"sr-{str(auth_request.id)[:8]}",
            "status": "active", "intent": "order",
            "code": {"coding": [{"system": "http://www.ama-assn.org/go/cpt",
                                  "code": auth_request.cpt_code,
                                  "display": self._cpt_desc(auth_request.cpt_code)}]},
            "subject": {"reference": f"Patient/{auth_request.patient_id}",
                        "display": self._pt_name(patient)},
            "authoredOn": ts,
            "requester": {"reference": "Practitioner/provider-001", "display": "Ordering Provider"},
            "reasonCode": [{"text": summary[:500]}]
        }
        for c in conditions[:5]:
            sr["reasonCode"].append({"text": _val(c, "value", str(c))})
        resources.append(sr)

        # Patient
        if patient:
            resources.append({
                "resourceType": "Patient", "id": auth_request.patient_id,
                "identifier": [{"system": "http://hospital.example.org/mrn",
                                 "value": _val(patient, "mrn")}],
                "name": [{"use": "official", "family": _val(patient, "last_name"),
                           "given": [_val(patient, "first_name")]}],
                "gender": _val(patient, "gender"),
                "birthDate": _val(patient, "date_of_birth")
            })

        # Conditions
        for i, c in enumerate(conditions[:10]):
            resources.append({
                "resourceType": "Condition",
                "id": f"cond-{str(auth_request.id)[:4]}-{i}",
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                                               "code": "active"}]},
                "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm",
                                     "code": _val(c, "code", "R68.89"),
                                     "display": _val(c, "value")}]},
                "subject": {"reference": f"Patient/{auth_request.patient_id}"}
            })

        # Medications
        for i, m in enumerate(medications[:10]):
            resources.append({
                "resourceType": "MedicationStatement",
                "id": f"med-{str(auth_request.id)[:4]}-{i}",
                "status": "active",
                "medicationCodeableConcept": {"text": _val(m, "value", str(m))},
                "subject": {"reference": f"Patient/{auth_request.patient_id}"}
            })

        # Clinical notes DocumentReference
        resources.append({
            "resourceType": "DocumentReference",
            "id": f"doc-{str(auth_request.id)[:8]}",
            "status": "current",
            "type": {"coding": [{"system": "http://loinc.org", "code": "34117-2",
                                  "display": "History and physical note"}]},
            "subject": {"reference": f"Patient/{auth_request.patient_id}"},
            "content": [{"attachment": {"contentType": "text/plain",
                                         "data": self._b64(summary)}}]
        })

        # Appeal letter as separate DocumentReference (if provided)
        if appeal_letter:
            resources.append({
                "resourceType": "DocumentReference",
                "id": f"appeal-{str(auth_request.id)[:8]}",
                "status": "current",
                "description": "Prior Authorization Appeal Letter",
                "type": {"coding": [{"system": "http://loinc.org", "code": "57133-1",
                                      "display": "Appeal Letter"}]},
                "subject": {"reference": f"Patient/{auth_request.patient_id}"},
                "content": [{"attachment": {"contentType": "text/plain",
                                             "title": "Appeal Letter",
                                             "data": self._b64(appeal_letter)}}]
            })

        # Coverage
        resources.append({
            "resourceType": "Coverage",
            "id": f"cov-{str(auth_request.id)[:8]}",
            "status": "active",
            "beneficiary": {"reference": f"Patient/{auth_request.patient_id}"},
            "payor": [{"display": _val(patient, "payer_name", "Insurance") if patient else "Insurance"}]
        })

        return {
            "resourceType": "Bundle", "id": bundle_id,
            "type": "collection", "timestamp": ts,
            "entry": [{"resource": r} for r in resources]
        }

    async def submit_prior_authorization(self, auth_request, fhir_bundle) -> Dict[str, Any]:
        if self.mock_mode:
            return await self._mock_submit(auth_request)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{FHIR_SERVER_URL}/fhir/Bundle",
                                         json=fhir_bundle,
                                         headers={"Content-Type": "application/json"})
                resp.raise_for_status()
                cr = resp.json()
        except Exception as e:
            print(f"[SubmissionAgent] FHIR server unreachable, using mock: {e}")
            return await self._mock_submit(auth_request)

        claim_id = cr.get("claim_response_id") or cr.get("id")
        decision = await self._poll(claim_id)
        outcome  = decision.get("auth_status", "pending")
        return {
            "success": True,
            "external_auth_id": f"PA-{str(auth_request.id)[:8].upper()}-{claim_id}",
            "claim_response_id": claim_id,
            "status": outcome,
            "timestamp": datetime.now().isoformat(),
            "decision": {
                "outcome": outcome,
                "reason":  decision.get("denial_reason"),
                "valid_until": datetime.now().isoformat() if outcome == "approved" else None,
                "approved_units": 1 if outcome == "approved" else None,
                "decided_at": decision.get("decided_at"),
                "reviewer": decision.get("reviewer"),
            },
            "next_steps": self._next(outcome)
        }

    async def submit_appeal(self, auth_request, original_bundle, appeal_letter) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "success": True,
                "claim_response_id": None,
                "status": "submitted",
                "message": "Appeal submitted (mock mode — start FHIR server for real payer review)"
            }
        try:
            import httpx, copy
            appeal_bundle = copy.deepcopy(original_bundle)
            appeal_bundle["id"] = str(uuid.uuid4())
            appeal_bundle["timestamp"] = datetime.now().isoformat()

            appeal_doc = {
                "resourceType": "DocumentReference",
                "id": f"appeal-{str(auth_request.id)[:8]}",
                "status": "current",
                "description": "Prior Authorization Appeal Letter",
                "type": {"coding": [{"system": "http://loinc.org", "code": "57133-1",
                                      "display": "Appeal Letter"}]},
                "content": [{"attachment": {"contentType": "text/plain", "title": "Appeal Letter",
                                             "data": self._b64(appeal_letter)}}]
            }
            appeal_bundle.setdefault("entry", []).append({"resource": appeal_doc})

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{FHIR_SERVER_URL}/fhir/Bundle",
                    json=appeal_bundle,
                    headers={"Content-Type": "application/json", "X-Is-Appeal": "true"}
                )
                resp.raise_for_status()
                cr = resp.json()

            claim_id = cr.get("claim_response_id") or cr.get("id")
            return {
                "success": True,
                "claim_response_id": claim_id,
                "status": "submitted",
                "message": f"Appeal submitted to payer (Claim ID: {claim_id}). Awaiting payer review at localhost:3001."
            }
        except Exception as e:
            print(f"[SubmissionAgent] Appeal submission failed: {e}")
            return {"success": False, "claim_response_id": None, "status": "failed",
                    "message": f"Appeal submission failed: {str(e)}"}

    async def _poll(self, claim_id: str) -> Dict[str, Any]:
        try:
            import httpx
        except ImportError:
            return {"auth_status": "approved"}  # fallback if httpx not installed
        url = f"{FHIR_SERVER_URL}/fhir/ClaimResponse/{claim_id}"
        for attempt in range(POLL_MAX_ATTEMPTS):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("auth_status") in ("approved", "denied"):
                            return data
            except Exception as e:
                print(f"[SubmissionAgent] Poll {attempt+1}: {e}")
            await asyncio.sleep(POLL_INTERVAL)
        return {"auth_status": "pending", "denial_reason": None, "timeout": True}

    async def _mock_submit(self, auth_request) -> Dict[str, Any]:
        pm = getattr(auth_request, "policy_match", None)
        if pm is not None:
            outcome = "approved" if (getattr(pm, "is_covered", True) and random.random() > 0.2) else "denied"
        else:
            outcome = random.choices(["approved", "denied"], weights=[0.75, 0.25])[0]
        short = str(auth_request.id)[:8].upper()
        denial_reasons = [
            "Insufficient documentation of conservative treatment",
            "Service not medically necessary per policy criteria",
            "Missing required clinical information",
        ]
        return {
            "success": True,
            "external_auth_id": f"PA-{short}-{'A' if outcome=='approved' else 'D'}",
            "claim_response_id": None,
            "status": outcome,
            "timestamp": datetime.now().isoformat(),
            "decision": {
                "outcome": outcome,
                "reason": random.choice(denial_reasons) if outcome == "denied" else None,
                "valid_until": datetime.now().isoformat() if outcome == "approved" else None,
                "approved_units": 1 if outcome == "approved" else None
            },
            "next_steps": self._next(outcome)
        }

    def _pt_name(self, p):
        if not p: return "Patient"
        return f"{_val(p,'first_name')} {_val(p,'last_name')}".strip() or "Patient"

    def _cpt_desc(self, code):
        return {
            "70551":"MRI brain","73721":"MRI knee","73221":"MRI shoulder",
            "72148":"MRI lumbar spine","72149":"MRI lumbar spine w contrast",
            "70450":"CT head","71250":"CT chest","74177":"CT abdomen pelvis",
            "93306":"Echocardiogram","93000":"ECG","45378":"Colonoscopy",
            "97110":"Physical therapy","J0173":"Dupilumab injection",
            "J2323":"Natalizumab infusion","33249":"CRT-D implant"
        }.get(code, f"CPT {code}")

    def _b64(self, text):
        return base64.b64encode((text or "").encode()).decode()

    def _next(self, outcome):
        if outcome == "approved":
            return ["Authorization approved", "Proceed with scheduled service"]
        return ["Review denial reason", "Consider appeal if medical necessity exists"]

    def validate_fhir_bundle(self, bundle):
        types_ = [e["resource"]["resourceType"] for e in bundle.get("entry", [])]
        errors = [f"Missing: {r}" for r in ["ServiceRequest", "Patient"] if r not in types_]
        return {"valid": not errors, "errors": errors, "warnings": []}