"""
Submission Agent - Maps data to FHIR resources and submits prior authorization
"""

import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from models.schemas import AuthorizationRequest, ClinicalEvidence, PolicyMatchResult


class SubmissionAgent:
    """
    Maps clinical data to FHIR resources and submits prior authorization requests
    to payer systems via FHIR APIs or X12 278.
    """
    
    def __init__(self, fhir_client=None, mock_mode: bool = True):
        self.agent_name = "SubmissionAgent"
        self.fhir_client = fhir_client
        self.mock_mode = mock_mode
        
    async def build_fhir_bundle(
        self,
        auth_request: AuthorizationRequest,
        clinical_evidence: ClinicalEvidence,
        policy_match: PolicyMatchResult
    ) -> Dict[str, Any]:
        """Build a FHIR Bundle with all necessary resources."""
        
        bundle_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Create FHIR resources
        resources = []
        
        # 1. ServiceRequest (the main prior auth request)
        service_request = {
            "resourceType": "ServiceRequest",
            "id": f"sr-{auth_request.id[:8]}",
            "status": "active",
            "intent": "order",
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/service-category",
                    "code": "17",
                    "display": "General Surgery"
                }]
            }],
            "code": {
                "coding": [{
                    "system": "http://www.ama-assn.org/go/cpt",
                    "code": auth_request.cpt_code,
                    "display": self._get_cpt_description(auth_request.cpt_code)
                }]
            },
            "subject": {
                "reference": f"Patient/{auth_request.patient_id}",
                "display": f"{auth_request.patient.first_name} {auth_request.patient.last_name}" if auth_request.patient else "Patient"
            },
            "authoredOn": timestamp,
            "requester": {
                "reference": "Practitioner/provider-001",
                "display": "Ordering Provider"
            },
            "reasonCode": [{
                "text": clinical_evidence.clinical_summary[:500] if clinical_evidence.clinical_summary else "Medical necessity documented"
            }],
            "supportingInfo": []
        }
        
        # Add clinical conditions as reasons
        for i, condition in enumerate(clinical_evidence.conditions[:5]):
            reason_ref = {
                "reference": f"Condition/cond-{auth_request.id[:4]}-{i}",
                "display": condition.value
            }
            service_request["reasonCode"].append({
                "text": condition.value
            })
        
        resources.append(service_request)
        
        # 2. Patient resource
        if auth_request.patient:
            patient_resource = {
                "resourceType": "Patient",
                "id": auth_request.patient_id,
                "identifier": [{
                    "system": "http://hospital.example.org/mrn",
                    "value": auth_request.patient.mrn
                }],
                "name": [{
                    "use": "official",
                    "family": auth_request.patient.last_name,
                    "given": [auth_request.patient.first_name]
                }],
                "gender": auth_request.patient.gender,
                "birthDate": auth_request.patient.date_of_birth
            }
            resources.append(patient_resource)
        
        # 3. Condition resources (from clinical evidence)
        for i, condition in enumerate(clinical_evidence.conditions[:10]):
            condition_resource = {
                "resourceType": "Condition",
                "id": f"cond-{auth_request.id[:4]}-{i}",
                "clinicalStatus": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active"
                    }]
                },
                "code": {
                    "coding": [{
                        "system": "http://hl7.org/fhir/sid/icd-10-cm",
                        "code": condition.code or "R68.89",
                        "display": condition.value
                    }]
                },
                "subject": {
                    "reference": f"Patient/{auth_request.patient_id}"
                },
                "assertedDate": timestamp
            }
            resources.append(condition_resource)
        
        # 4. MedicationStatement resources
        for i, med in enumerate(clinical_evidence.medications[:10]):
            med_resource = {
                "resourceType": "MedicationStatement",
                "id": f"med-{auth_request.id[:4]}-{i}",
                "status": "active",
                "medicationCodeableConcept": {
                    "text": med.value
                },
                "subject": {
                    "reference": f"Patient/{auth_request.patient_id}"
                }
            }
            resources.append(med_resource)
        
        # 5. DocumentReference (clinical notes summary)
        doc_ref = {
            "resourceType": "DocumentReference",
            "id": f"doc-{auth_request.id[:8]}",
            "status": "current",
            "type": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "34117-2",
                    "display": "History and physical note"
                }]
            },
            "subject": {
                "reference": f"Patient/{auth_request.patient_id}"
            },
            "content": [{
                "attachment": {
                    "contentType": "text/plain",
                    "data": self._encode_base64(clinical_evidence.clinical_summary)
                }
            }],
            "context": {
                "encounter": {
                    "reference": "Encounter/enc-001"
                }
            }
        }
        resources.append(doc_ref)
        
        # 6. Coverage resource
        coverage = {
            "resourceType": "Coverage",
            "id": f"cov-{auth_request.id[:8]}",
            "status": "active",
            "beneficiary": {
                "reference": f"Patient/{auth_request.patient_id}"
            },
            "payor": [{
                "display": auth_request.patient.payer_name if auth_request.patient else "Insurance Company"
            }]
        }
        resources.append(coverage)
        
        # Create the Bundle
        bundle = {
            "resourceType": "Bundle",
            "id": bundle_id,
            "type": "collection",
            "timestamp": timestamp,
            "entry": [
                {"resource": res} for res in resources
            ]
        }
        
        return bundle
    
    async def submit_prior_authorization(
        self,
        auth_request: AuthorizationRequest,
        fhir_bundle: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Submit the prior authorization request to the payer."""
        
        if self.mock_mode:
            return await self._mock_submit(auth_request)
        
        # Real submission would go here
        # In production, this would call the payer's FHIR API
        try:
            response = await self.fhir_client.post(
                "/PriorAuthorization",
                json=fhir_bundle
            )
            return {
                "success": True,
                "external_auth_id": response.get("id"),
                "status": "submitted",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "status": "failed"
            }
    
    async def _mock_submit(self, auth_request: AuthorizationRequest) -> Dict[str, Any]:
        """Simulate submission for demo purposes."""
        
        import random
        
        # Simulate different outcomes
        outcomes = ["approved", "pending", "denied"]
        weights = [0.6, 0.3, 0.1]
        
        # For demo, use the policy match to determine outcome
        if auth_request.policy_match:
            if auth_request.policy_match.is_covered:
                outcome = "approved" if random.random() > 0.1 else "pending"
            else:
                outcome = "denied" if random.random() > 0.3 else "pending"
        else:
            outcome = random.choices(outcomes, weights=weights)[0]
        
        external_ids = {
            "approved": f"PA-{auth_request.id[:8].upper()}-A",
            "pending": f"PA-{auth_request.id[:8].upper()}-P",
            "denied": f"PA-{auth_request.id[:8].upper()}-D"
        }
        
        denial_reasons = [
            "Insufficient documentation of conservative treatment",
            "Service not medically necessary per policy criteria",
            "Missing required clinical information",
            "Experimental/investigational procedure",
            "Plan benefit limitation exceeded"
        ]
        
        return {
            "success": True,
            "external_auth_id": external_ids[outcome],
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
    
    async def check_auth_status(
        self,
        external_auth_id: str,
        payer_name: str
    ) -> Dict[str, Any]:
        """Check the status of a submitted prior authorization."""
        
        if self.mock_mode:
            return await self._mock_status_check(external_auth_id)
        
        # Real status check would go here
        return {
            "external_auth_id": external_auth_id,
            "status": "pending",
            "last_updated": datetime.now().isoformat()
        }
    
    async def _mock_status_check(self, external_auth_id: str) -> Dict[str, Any]:
        """Simulate status check for demo."""
        
        status = "approved" if "-A" in external_auth_id else ("denied" if "-D" in external_auth_id else "pending")
        
        return {
            "external_auth_id": external_auth_id,
            "status": status,
            "last_updated": datetime.now().isoformat(),
            "decision": {
                "outcome": status,
                "reason": "Service meets medical necessity criteria" if status == "approved" else "Incomplete documentation"
            }
        }
    
    async def cancel_prior_authorization(
        self,
        external_auth_id: str
    ) -> Dict[str, Any]:
        """Cancel a submitted prior authorization."""
        
        if self.mock_mode:
            return {
                "success": True,
                "external_auth_id": external_auth_id,
                "status": "cancelled",
                "timestamp": datetime.now().isoformat()
            }
        
        return {"success": False, "error": "Not implemented"}
    
    def _get_cpt_description(self, cpt_code: str) -> str:
        """Get CPT code description."""
        cpt_descriptions = {
            "70551": "MRI brain",
            "70552": "MRI brain w contrast",
            "70553": "MRI brain w/o and w contrast",
            "73721": "MRI knee",
            "73221": "MRI shoulder",
            "72148": "MRI lumbar spine",
            "72149": "MRI lumbar spine w contrast",
            "70450": "CT head",
            "71250": "CT chest",
            "74177": "CT abdomen pelvis",
            "93306": "Echocardiogram",
            "93000": "ECG",
            "45378": "Colonoscopy",
            "97110": "Physical therapy"
        }
        return cpt_descriptions.get(cpt_code, f"CPT {cpt_code}")
    
    def _encode_base64(self, text: str) -> str:
        """Encode text to base64."""
        import base64
        return base64.b64encode(text.encode()).decode()
    
    def _get_next_steps(self, outcome: str) -> List[str]:
        """Get next steps based on outcome."""
        if outcome == "approved":
            return [
                "Authorization approved",
                "Proceed with scheduled service",
                "Document approval in patient record"
            ]
        elif outcome == "pending":
            return [
                "Additional review required",
                "Monitor for decision (typically 24-72 hours)",
                "Be prepared to submit additional documentation if requested"
            ]
        else:
            return [
                "Review denial reason carefully",
                "Consider appeal if medical necessity exists",
                "Consult with peer-to-peer reviewer if available"
            ]
    
    def validate_fhir_bundle(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        """Validate FHIR bundle before submission."""
        
        errors = []
        warnings = []
        
        # Check required resources
        required_types = ["ServiceRequest", "Patient"]
        existing_types = [entry["resource"]["resourceType"] for entry in bundle.get("entry", [])]
        
        for req_type in required_types:
            if req_type not in existing_types:
                errors.append(f"Missing required resource: {req_type}")
        
        # Check ServiceRequest has required fields
        sr = next((e["resource"] for e in bundle.get("entry", []) 
                   if e["resource"]["resourceType"] == "ServiceRequest"), None)
        
        if sr:
            if not sr.get("code"):
                errors.append("ServiceRequest missing code")
            if not sr.get("subject"):
                errors.append("ServiceRequest missing subject")
            if not sr.get("requester"):
                warnings.append("ServiceRequest missing requester")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
