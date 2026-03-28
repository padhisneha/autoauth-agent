"""
Submission Agent - Maps data to FHIR resources and submits prior authorization.
Works with both real Pydantic objects and proxy/dict-based evidence objects.
"""

import json
import uuid
import random
from datetime import datetime
from typing import Dict, Any, List, Optional


def _val(entity, attr: str, default="") -> str:
    """Safely get an attribute from an entity that may be a dict, object, or proxy."""
    if isinstance(entity, dict):
        return entity.get(attr, default)
    return getattr(entity, attr, default) or default


class SubmissionAgent:
    def __init__(self, fhir_client=None, mock_mode: bool = True):
        self.agent_name = "SubmissionAgent"
        self.fhir_client = fhir_client
        self.mock_mode   = mock_mode

    async def build_fhir_bundle(
        self,
        auth_request: Any,
        clinical_evidence: Any,
        policy_match: Any
    ) -> Dict[str, Any]:

        bundle_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        resources = []

        # ── 1. ServiceRequest ──
        summary = _val(clinical_evidence, "clinical_summary") or "Medical necessity documented"
        service_request = {
            "resourceType": "ServiceRequest",
            "id": f"sr-{str(auth_request.id)[:8]}",
            "status": "active",
            "intent": "order",
            "code": {
                "coding": [{
                    "system": "http://www.ama-assn.org/go/cpt",
                    "code": auth_request.cpt_code,
                    "display": self._get_cpt_description(auth_request.cpt_code)
                }]
            },
            "subject": {
                "reference": f"Patient/{auth_request.patient_id}",
                "display": self._patient_display(auth_request.patient)
            },
            "authoredOn": timestamp,
            "reasonCode": [{"text": summary[:500]}]
        }

        conditions = getattr(clinical_evidence, "conditions", []) or []
        for cond in conditions[:5]:
            service_request["reasonCode"].append({"text": _val(cond, "value", str(cond))})

        resources.append(service_request)

        # ── 2. Patient resource ──
        patient = auth_request.patient
        if patient:
            resources.append({
                "resourceType": "Patient",
                "id": auth_request.patient_id,
                "identifier": [{"system": "http://hospital.example.org/mrn", "value": _val(patient, "mrn")}],
                "name": [{"use": "official", "family": _val(patient, "last_name"), "given": [_val(patient, "first_name")]}],
                "gender": _val(patient, "gender"),
                "birthDate": _val(patient, "date_of_birth")
            })

        # ── 3. Condition resources ──
        for i, cond in enumerate(conditions[:10]):
            resources.append({
                "resourceType": "Condition",
                "id": f"cond-{str(auth_request.id)[:4]}-{i}",
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
                "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": _val(cond, "code", "R68.89"), "display": _val(cond, "value")}]},
                "subject": {"reference": f"Patient/{auth_request.patient_id}"}
            })

        # ── 4. MedicationStatement resources ──
        medications = getattr(clinical_evidence, "medications", []) or []
        for i, med in enumerate(medications[:10]):
            resources.append({
                "resourceType": "MedicationStatement",
                "id": f"med-{str(auth_request.id)[:4]}-{i}",
                "status": "active",
                "medicationCodeableConcept": {"text": _val(med, "value", str(med))},
                "subject": {"reference": f"Patient/{auth_request.patient_id}"}
            })

        # ── 5. DocumentReference ──
        resources.append({
            "resourceType": "DocumentReference",
            "id": f"doc-{str(auth_request.id)[:8]}",
            "status": "current",
            "type": {"coding": [{"system": "http://loinc.org", "code": "34117-2", "display": "History and physical note"}]},
            "subject": {"reference": f"Patient/{auth_request.patient_id}"},
            "content": [{"attachment": {"contentType": "text/plain", "data": self._encode_base64(summary)}}]
        })

        # ── 6. Coverage ──
        resources.append({
            "resourceType": "Coverage",
            "id": f"cov-{str(auth_request.id)[:8]}",
            "status": "active",
            "beneficiary": {"reference": f"Patient/{auth_request.patient_id}"},
            "payor": [{"display": _val(patient, "payer_name", "Insurance Company") if patient else "Insurance Company"}]
        })

        return {
            "resourceType": "Bundle",
            "id": bundle_id,
            "type": "collection",
            "timestamp": timestamp,
            "entry": [{"resource": r} for r in resources]
        }

    async def submit_prior_authorization(
        self,
        auth_request: Any,
        fhir_bundle: Dict[str, Any]
    ) -> Dict[str, Any]:
        if self.mock_mode:
            return await self._mock_submit(auth_request)
        try:
            response = await self.fhir_client.post("/PriorAuthorization", json=fhir_bundle)
            return {"success": True, "external_auth_id": response.get("id"), "status": "submitted",
                    "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"success": False, "error": str(e), "status": "failed"}

    async def _mock_submit(self, auth_request: Any) -> Dict[str, Any]:
        # Use policy_match if available, otherwise default to approved (demo-friendly)
        policy_match = getattr(auth_request, "policy_match", None)
        if policy_match is not None:
            is_covered = getattr(policy_match, "is_covered", True)
            outcome = "approved" if (is_covered and random.random() > 0.15) else "denied"
        else:
            # No policy info → bias toward approval so demo always produces a result
            outcome = random.choices(["approved", "denied"], weights=[0.75, 0.25])[0]

        auth_id_short = str(auth_request.id)[:8].upper()
        external_ids  = {"approved": f"PA-{auth_id_short}-A", "denied": f"PA-{auth_id_short}-D"}

        denial_reasons = [
            "Insufficient documentation of conservative treatment",
            "Service not medically necessary per policy criteria",
            "Missing required clinical information",
        ]

        return {
            "success": True,
            "external_auth_id": external_ids.get(outcome, f"PA-{auth_id_short}-A"),
            "status": outcome,
            "timestamp": datetime.now().isoformat(),
            "decision": {
                "outcome": outcome,
                "reason": random.choice(denial_reasons) if outcome == "denied" else None,
                "valid_until": datetime.now().isoformat() if outcome == "approved" else None,
                "approved_units": 1 if outcome == "approved" else None
            },
            "next_steps": self._get_next_steps(outcome)
        }

    async def check_auth_status(self, external_auth_id: str, payer_name: str) -> Dict[str, Any]:
        if self.mock_mode:
            status = "approved" if "-A" in external_auth_id else ("denied" if "-D" in external_auth_id else "pending")
            return {"external_auth_id": external_auth_id, "status": status,
                    "last_updated": datetime.now().isoformat(),
                    "decision": {"outcome": status}}
        return {"external_auth_id": external_auth_id, "status": "pending",
                "last_updated": datetime.now().isoformat()}

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _patient_display(self, patient) -> str:
        if not patient:
            return "Patient"
        return f"{_val(patient, 'first_name')} {_val(patient, 'last_name')}".strip() or "Patient"

    def _get_cpt_description(self, cpt_code: str) -> str:
        return {
            "70551": "MRI brain", "73721": "MRI knee", "73221": "MRI shoulder",
            "72148": "MRI lumbar spine", "72149": "MRI lumbar spine w contrast",
            "70450": "CT head", "71250": "CT chest", "74177": "CT abdomen pelvis",
            "93306": "Echocardiogram", "93000": "ECG", "45378": "Colonoscopy",
            "97110": "Physical therapy"
        }.get(cpt_code, f"CPT {cpt_code}")

    def _encode_base64(self, text: str) -> str:
        import base64
        return base64.b64encode((text or "").encode()).decode()

    def _get_next_steps(self, outcome: str) -> List[str]:
        if outcome == "approved":
            return ["Authorization approved", "Proceed with scheduled service", "Document approval in patient record"]
        elif outcome == "pending":
            return ["Additional review required", "Monitor for decision (24-72 hours)"]
        else:
            return ["Review denial reason carefully", "Consider appeal if medical necessity exists"]

    def validate_fhir_bundle(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        errors, warnings = [], []
        types = [e["resource"]["resourceType"] for e in bundle.get("entry", [])]
        for req in ["ServiceRequest", "Patient"]:
            if req not in types:
                errors.append(f"Missing required resource: {req}")
        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}