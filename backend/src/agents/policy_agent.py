"""
Policy Agent - Retrieves and matches payer policies.
Uses gpt-4.5-mini to reason about whether clinical evidence satisfies policy criteria.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from models.schemas import PolicyRequirement, PolicyMatchResult, AgentTrace

MODEL = "gpt-4.5-mini"


class PolicyAgent:
    """
    Retrieves real-time payer guidelines and matches clinical evidence
    to policy requirements using rule-based lookup + LLM reasoning.
    """

    def __init__(self, vector_store=None, llm_client=None):
        self.agent_name = "PolicyAgent"
        self.vector_store = vector_store
        self.llm_client = llm_client
        self.policy_knowledge_base = self._initialize_policy_knowledge_base()

    def _initialize_policy_knowledge_base(self) -> Dict[str, Any]:
        return {
            "blue_cross": {
                "name": "Blue Cross Blue Shield",
                "policies": [
                    {
                        "id": "BC-MRI-001",
                        "name": "MRI Coverage Guidelines",
                        "service_type": "mri",
                        "cpt_codes": ["70551", "70552", "70553", "73721", "73221", "72148", "72149", "72156"],
                        "requirements": [
                            "Clinical notes documenting symptoms > 4 weeks",
                            "Prior conservative treatment failed (unless red flag)",
                            "Clear clinical indication documented"
                        ],
                        "criteria": [
                            "Suspected structural abnormality or tumor",
                            "Unexplained neurological symptoms",
                            "Suspected ligament or meniscal tear",
                            "Unexplained chronic pain unresponsive to therapy",
                        ],
                        "coverage_type": "prior_auth_required",
                        "denial_reasons": [
                            "Insufficient conservative treatment",
                            "Incomplete clinical documentation",
                            "Service not medically necessary",
                        ]
                    },
                    {
                        "id": "BC-CT-001",
                        "name": "CT Scan Coverage Guidelines",
                        "service_type": "ct_scan",
                        "cpt_codes": ["70450", "70460", "70470", "71250", "71260", "71270", "74177", "74178"],
                        "requirements": [
                            "Clinical indication documented",
                            "Prior imaging results if applicable",
                        ],
                        "criteria": [
                            "Tumor evaluation and staging",
                            "Acute trauma evaluation",
                            "Suspected hemorrhage or appendicitis",
                        ],
                        "coverage_type": "prior_auth_required",
                        "denial_reasons": [
                            "Insufficient clinical indication",
                            "Alternative imaging more appropriate",
                        ]
                    },
                ]
            },
            "aetna": {
                "name": "Aetna",
                "policies": [
                    {
                        "id": "AET-MRI-001",
                        "name": "MRI Prior Authorization",
                        "service_type": "mri",
                        "cpt_codes": ["70551", "70552", "70553", "73721", "73221", "72148"],
                        "requirements": [
                            "Clinical notes with history and physical",
                            "Duration of symptoms documented",
                            "Treatments attempted and response",
                        ],
                        "criteria": [
                            "Clinical suspicion of structural abnormality",
                            "Failed 6 weeks conservative therapy",
                            "Red flag symptoms requiring urgent evaluation",
                        ],
                        "coverage_type": "prior_auth_required",
                        "denial_reasons": [
                            "Inadequate conservative care",
                            "Missing clinical documentation",
                        ]
                    }
                ]
            },
            "united": {
                "name": "UnitedHealthcare",
                "policies": [
                    {
                        "id": "UHC-MRI-001",
                        "name": "Imaging Services - Commercial",
                        "service_type": "mri",
                        "cpt_codes": ["70551", "70552", "70553", "73721", "73221", "72148", "72149"],
                        "requirements": [
                            "Clinical indication with specific diagnosis",
                            "Conservative treatment duration and response",
                        ],
                        "criteria": [
                            "Clinical suspicion for structural abnormality",
                            "Documented failure of conservative treatment (6 weeks min)",
                            "Emergent indications exempt from conservative care requirement",
                        ],
                        "coverage_type": "prior_auth_required",
                        "denial_reasons": [
                            "Does not meet medical necessity criteria",
                            "Insufficient trial of conservative treatment",
                        ]
                    },
                    {
                        "id": "UHC-CT-001",
                        "name": "CT Imaging - Commercial",
                        "service_type": "ct_scan",
                        "cpt_codes": ["74177", "74178", "71250", "71260"],
                        "requirements": [
                            "Physician order with specific diagnosis code",
                            "Clinical documentation supporting need",
                        ],
                        "criteria": [
                            "Oncology staging or restaging",
                            "Unexplained abnormal findings on prior imaging",
                        ],
                        "coverage_type": "prior_auth_required",
                        "denial_reasons": [
                            "Not medically necessary",
                            "Missing documentation",
                        ]
                    }
                ]
            },
        }

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    async def retrieve_policy_requirements(
        self,
        payer_name: str,
        service_type: str,
        cpt_code: str
    ) -> PolicyRequirement:
        payer_key = self._normalize_payer_name(payer_name)
        payer_data = self.policy_knowledge_base.get(payer_key, {})
        policies = payer_data.get("policies", [])

        for policy in policies:
            if policy["service_type"] == service_type.lower():
                if not policy["cpt_codes"] or cpt_code in policy["cpt_codes"]:
                    return PolicyRequirement(
                        requirement_id=policy["id"],
                        description=policy["name"],
                        required_documentation=policy["requirements"],
                        min_clinical_criteria=policy["criteria"],
                        coverage_type=policy["coverage_type"],
                        applicable_cpt_codes=policy.get("cpt_codes", []),
                        applicable_icd_codes=[]
                    )

        return PolicyRequirement(
            requirement_id=f"{payer_key.upper()}-GEN-001",
            description=f"General {service_type} Prior Authorization",
            required_documentation=[
                "Clinical notes documenting medical necessity",
                "Relevant history and physical",
                "Prior treatment attempts and response"
            ],
            min_clinical_criteria=[
                "Documented clinical indication",
                "Evidence of medical necessity"
            ],
            coverage_type="prior_auth_required",
            applicable_cpt_codes=[],
            applicable_icd_codes=[]
        )

    async def match_policy(
        self,
        clinical_evidence: Any,
        policy_requirement: PolicyRequirement,
        payer_name: str
    ) -> PolicyMatchResult:
        """Match clinical evidence to policy — use LLM if available, otherwise rule-based."""

        if self.llm_client:
            return await self._match_policy_llm(clinical_evidence, policy_requirement, payer_name)
        return await self._match_policy_rules(clinical_evidence, policy_requirement, payer_name)

    # ------------------------------------------------------------------ #
    #  LLM-powered matching                                               #
    # ------------------------------------------------------------------ #

    async def _match_policy_llm(
        self,
        clinical_evidence: Any,
        policy_requirement: PolicyRequirement,
        payer_name: str
    ) -> PolicyMatchResult:

        cond_str = ", ".join(
            getattr(c, "value", str(c)) for c in (getattr(clinical_evidence, "conditions", []) or [])[:6]
        ) or "none"
        med_str = ", ".join(
            getattr(m, "value", str(m)) for m in (getattr(clinical_evidence, "medications", []) or [])[:5]
        ) or "none"
        proc_str = ", ".join(
            getattr(p, "value", str(p)) for p in (getattr(clinical_evidence, "procedures", []) or [])[:4]
        ) or "none"
        summary = getattr(clinical_evidence, "clinical_summary", "") or ""

        req_list = "\n".join(f"- {r}" for r in policy_requirement.required_documentation)
        crit_list = "\n".join(f"- {c}" for c in policy_requirement.min_clinical_criteria)

        prompt = f"""You are a payer medical director reviewing a prior authorization request.

Payer: {payer_name}
Policy: {policy_requirement.description} (ID: {policy_requirement.requirement_id})

REQUIRED DOCUMENTATION:
{req_list}

CLINICAL CRITERIA THAT MUST BE MET:
{crit_list}

CLINICAL EVIDENCE SUBMITTED:
- Summary: {summary}
- Diagnoses: {cond_str}
- Medications / conservative treatments: {med_str}
- Prior procedures: {proc_str}

For EACH requirement and criterion, determine if the submitted evidence satisfies it.
Respond ONLY with a JSON object in this exact format:
{{
  "satisfied_requirements": ["<list of requirements/criteria that ARE met>"],
  "missing_requirements": ["<list of requirements/criteria that are NOT met>"],
  "additional_documentation_needed": ["<plain English list of what to add>"],
  "match_score": <float 0.0-1.0>,
  "is_covered": <true|false>,
  "reasoning": "<two sentence explanation>"
}}"""

        try:
            response = await self.llm_client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)

            return PolicyMatchResult(
                policy_id=policy_requirement.requirement_id,
                policy_name=policy_requirement.description,
                is_covered=result.get("is_covered", False),
                match_score=float(result.get("match_score", 0.5)),
                satisfied_requirements=result.get("satisfied_requirements", []),
                missing_requirements=result.get("missing_requirements", []),
                additional_documentation_needed=result.get("additional_documentation_needed", []),
                policy_text=self._get_policy_text(payer_name, policy_requirement.requirement_id)
            )
        except Exception:
            return await self._match_policy_rules(clinical_evidence, policy_requirement, payer_name)

    async def _match_policy_rules(
        self,
        clinical_evidence: Any,
        policy_requirement: PolicyRequirement,
        payer_name: str
    ) -> PolicyMatchResult:
        satisfied = []
        missing = []
        additional_docs = []

        for req in policy_requirement.required_documentation:
            if self._check_documentation_requirement(clinical_evidence, req):
                satisfied.append(req)
            else:
                missing.append(req)
                additional_docs.append(f"Please provide: {req.lower()}")

        for criterion in policy_requirement.min_clinical_criteria:
            if self._check_clinical_criterion(clinical_evidence, criterion):
                satisfied.append(criterion)
            else:
                missing.append(criterion)

        total = len(policy_requirement.required_documentation) + len(policy_requirement.min_clinical_criteria)
        match_score = len(satisfied) / max(total, 1)
        is_covered = match_score >= 0.6

        return PolicyMatchResult(
            policy_id=policy_requirement.requirement_id,
            policy_name=policy_requirement.description,
            is_covered=is_covered,
            match_score=match_score,
            satisfied_requirements=satisfied,
            missing_requirements=missing,
            additional_documentation_needed=additional_docs,
            policy_text=self._get_policy_text(payer_name, policy_requirement.requirement_id)
        )

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _normalize_payer_name(self, payer_name: str) -> str:
        payer_lower = payer_name.lower().strip()
        mappings = {
            "blue": "blue_cross", "bcbs": "blue_cross", "aetna": "aetna",
            "united": "united", "uhc": "united", "unitedhealthcare": "united",
            "cigna": "cigna", "medicare": "medicare",
        }
        for key, value in mappings.items():
            if key in payer_lower:
                return value
        return payer_lower.replace(" ", "_")

    def _check_documentation_requirement(self, clinical_evidence: Any, requirement: str) -> bool:
        rl = requirement.lower()
        if "clinical notes" in rl or "documentation" in rl:
            return bool(getattr(clinical_evidence, "clinical_summary", None))
        if "lab" in rl:
            return len(getattr(clinical_evidence, "lab_results", []) or []) > 0
        if "treatment" in rl or "therapy" in rl:
            return (
                len(getattr(clinical_evidence, "procedures", []) or []) > 0
                or len(getattr(clinical_evidence, "medications", []) or []) > 0
            )
        if "diagnosis" in rl or "condition" in rl:
            return len(getattr(clinical_evidence, "conditions", []) or []) > 0
        return bool(getattr(clinical_evidence, "clinical_summary", None))

    def _check_clinical_criterion(self, clinical_evidence: Any, criterion: str) -> bool:
        cl = criterion.lower()
        conditions = getattr(clinical_evidence, "conditions", []) or []
        medications = getattr(clinical_evidence, "medications", []) or []
        lab_results = getattr(clinical_evidence, "lab_results", []) or []
        vital_signs = getattr(clinical_evidence, "vital_signs", []) or []

        if conditions and any(t in cl for t in ["symptom", "condition", "diagnosis", "disease", "suspicion", "abnormality"]):
            return True
        if medications and any(t in cl for t in ["treatment", "therapy", "medication", "conservative"]):
            return True
        if lab_results and "lab" in cl:
            return True
        if vital_signs and ("vital" in cl or "clinical" in cl):
            return True
        return False

    def _get_policy_text(self, payer_name: str, policy_id: str) -> str:
        payer_key = self._normalize_payer_name(payer_name)
        payer_data = self.policy_knowledge_base.get(payer_key, {})
        for policy in payer_data.get("policies", []):
            if policy["id"] == policy_id:
                return (
                    f"Policy: {policy['name']}\nID: {policy['id']}\n\n"
                    f"Required Documentation:\n"
                    + "\n".join(f"- {r}" for r in policy["requirements"])
                    + f"\n\nClinical Criteria:\n"
                    + "\n".join(f"- {c}" for c in policy["criteria"])
                    + f"\n\nCoverage Type: {policy['coverage_type']}"
                )
        return "Policy details not available."