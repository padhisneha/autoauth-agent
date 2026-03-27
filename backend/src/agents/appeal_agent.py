"""
Appeal Agent - Auto-generates appeal letters when requests are denied.
Uses gpt-4.5-mini to write clinically accurate, legally structured appeal letters.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional

MODEL = "gpt-4.5-mini"


class AppealAgent:
    """
    Autonomous appeal letter generation when prior authorization is denied.
    Analyses denial reasons, gathers supporting evidence, and drafts appeals via LLM.
    """

    def __init__(self, llm_client=None):
        self.agent_name = "AppealAgent"
        self.llm_client = llm_client

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    async def analyze_denial(
        self,
        auth_request: Any,
        denial_reason: str,
        clinical_evidence: Any,
        policy_match: Any
    ) -> Dict[str, Any]:
        """Analyse the denial and build a structured appeal strategy."""

        analysis = {
            "denial_reason": denial_reason,
            "primary_appeal_argument": "",
            "supporting_evidence": [],
            "missing_documentation": [],
            "urgency_indicators": [],
            "peer_review_recommended": False,
            "success_probability": 0.5
        }

        denial_argument_map = {
            "insufficient conservative treatment": {
                "argument": "The patient has documented prior treatments demonstrating medical necessity and failure of conservative management.",
                "evidence_needed": ["prior_procedures", "medications", "physician_notes"]
            },
            "not medically necessary": {
                "argument": "The requested service is medically necessary based on the patient's specific clinical presentation, diagnosis, and failure of conservative management.",
                "evidence_needed": ["conditions", "clinical_summary", "lab_results"]
            },
            "incomplete documentation": {
                "argument": "This appeal provides additional clinical documentation not included in the original submission.",
                "evidence_needed": ["clinical_summary", "physician_notes"]
            },
            "experimental": {
                "argument": "The requested service is a standard, evidence-based treatment covered under the patient's plan benefits.",
                "evidence_needed": ["guidelines", "clinical_trials"]
            },
        }

        denial_lower = denial_reason.lower()
        for key, data in denial_argument_map.items():
            if key in denial_lower:
                analysis["primary_appeal_argument"] = data["argument"]
                analysis["missing_documentation"] = data["evidence_needed"]
                break

        if not analysis["primary_appeal_argument"]:
            analysis["primary_appeal_argument"] = (
                "The clinical documentation provided demonstrates clear medical necessity "
                "for the requested service based on the patient's diagnosis and clinical presentation."
            )

        conditions = getattr(clinical_evidence, "conditions", []) or []
        procedures = getattr(clinical_evidence, "procedures", []) or []
        medications = getattr(clinical_evidence, "medications", []) or []
        lab_results = getattr(clinical_evidence, "lab_results", []) or []
        clinical_summary = getattr(clinical_evidence, "clinical_summary", "") or ""

        if conditions:
            analysis["supporting_evidence"].append({
                "type": "diagnoses",
                "details": [getattr(c, "value", str(c)) for c in conditions[:5]]
            })
        if procedures:
            analysis["supporting_evidence"].append({
                "type": "prior_treatments",
                "details": [getattr(p, "value", str(p)) for p in procedures[:5]]
            })
        if medications:
            analysis["supporting_evidence"].append({
                "type": "current_medications",
                "details": [getattr(m, "value", str(m)) for m in medications[:5]]
            })
        if lab_results:
            analysis["supporting_evidence"].append({
                "type": "lab_results",
                "details": [getattr(l, "value", str(l)) for l in lab_results[:3]]
            })

        urgency_terms = ["progressive", "worsening", "severe", "acute", "debilitating", "chronic pain", "cancer", "malignancy"]
        analysis["urgency_indicators"] = [t for t in urgency_terms if t in clinical_summary.lower()]

        if analysis["urgency_indicators"]:
            analysis["peer_review_recommended"] = True

        analysis["success_probability"] = self._calculate_success_probability(analysis, policy_match)
        return analysis

    async def generate_appeal_letter(
        self,
        auth_request: Any,
        denial_analysis: Dict[str, Any],
        clinical_evidence: Any,
        policy_match: Any
    ) -> str:
        """Generate a complete appeal letter — LLM if available, template fallback otherwise."""

        if self.llm_client:
            return await self._generate_appeal_letter_llm(auth_request, denial_analysis, clinical_evidence, policy_match)
        return self._generate_appeal_letter_template(auth_request, denial_analysis, clinical_evidence, policy_match)

    # ------------------------------------------------------------------ #
    #  LLM-powered letter generation                                      #
    # ------------------------------------------------------------------ #

    async def _generate_appeal_letter_llm(
        self,
        auth_request: Any,
        denial_analysis: Dict[str, Any],
        clinical_evidence: Any,
        policy_match: Any
    ) -> str:

        patient = auth_request.patient
        current_date = datetime.now().strftime("%B %d, %Y")

        cond_str = ", ".join(
            getattr(c, "value", str(c)) for c in (getattr(clinical_evidence, "conditions", []) or [])[:6]
        ) or "none documented"
        med_str = ", ".join(
            getattr(m, "value", str(m)) for m in (getattr(clinical_evidence, "medications", []) or [])[:5]
        ) or "none"
        proc_str = ", ".join(
            getattr(p, "value", str(p)) for p in (getattr(clinical_evidence, "procedures", []) or [])[:4]
        ) or "none"
        lab_str = ", ".join(
            getattr(l, "value", str(l)) for l in (getattr(clinical_evidence, "lab_results", []) or [])[:3]
        ) or "none"
        clinical_summary = getattr(clinical_evidence, "clinical_summary", "") or ""

        payer = getattr(patient, "payer_name", "Insurance Company") if patient else "Insurance Company"
        first = getattr(patient, "first_name", "") if patient else ""
        last = getattr(patient, "last_name", "") if patient else ""
        dob = getattr(patient, "date_of_birth", "") if patient else ""
        member_id = getattr(patient, "insurance_id", "") if patient else ""

        satisfied = getattr(policy_match, "satisfied_requirements", []) if policy_match else []
        satisfied_str = "\n".join(f"- {s}" for s in satisfied[:5]) or "- See clinical documentation"

        urgency = denial_analysis.get("urgency_indicators", [])
        urgency_str = (
            f"CLINICAL URGENCY NOTE: Patient exhibits the following urgency indicators: {', '.join(urgency)}."
            if urgency else ""
        )

        prompt = f"""You are a physician writing a prior authorization appeal letter. Write a professional, formal, and clinically detailed appeal letter.

Date: {current_date}
Payer: {payer} — Appeals Department
Patient: {first} {last}
Date of Birth: {dob}
Member ID: {member_id}
Auth Reference: {getattr(auth_request, 'id', 'N/A')}
CPT Code Requested: {getattr(auth_request, 'cpt_code', 'N/A')}

Denial Reason: {denial_analysis['denial_reason']}
Primary Appeal Argument: {denial_analysis['primary_appeal_argument']}
{urgency_str}

Clinical Summary:
{clinical_summary}

Supporting Clinical Evidence:
- Diagnoses: {cond_str}
- Current Medications: {med_str}
- Prior Treatments / Procedures: {proc_str}
- Lab Results: {lab_str}

Policy Requirements Already Satisfied:
{satisfied_str}

Write a complete, formal appeal letter with these sections:
1. Header (date, from/to, re: block)
2. Opening statement citing the denial
3. Patient history and clinical presentation (use the evidence above)
4. Direct rebuttal of the denial reason with clinical justification
5. Policy criteria that are satisfied
6. Urgency argument (if applicable)
7. Conclusion requesting approval with peer-to-peer review offer
8. Signature block with [Provider Name], [Credentials], [Date]

Be specific, clinical, and persuasive. Use proper medical terminology."""

        try:
            response = await self.llm_client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1200,
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return self._generate_appeal_letter_template(auth_request, denial_analysis, clinical_evidence, policy_match)

    # ------------------------------------------------------------------ #
    #  Template fallback                                                   #
    # ------------------------------------------------------------------ #

    def _generate_appeal_letter_template(
        self,
        auth_request: Any,
        denial_analysis: Dict[str, Any],
        clinical_evidence: Any,
        policy_match: Any
    ) -> str:
        patient = auth_request.patient
        current_date = datetime.now().strftime("%B %d, %Y")

        first = getattr(patient, "first_name", "") if patient else ""
        last = getattr(patient, "last_name", "") if patient else ""
        dob = getattr(patient, "date_of_birth", "") if patient else ""
        member_id = getattr(patient, "insurance_id", "") if patient else ""
        payer = getattr(patient, "payer_name", "Insurance Company") if patient else "Insurance Company"
        cpt = getattr(auth_request, "cpt_code", "N/A")
        auth_ref = getattr(auth_request, "id", "N/A")

        letter = f"""PRIOR AUTHORIZATION APPEAL LETTER

Date: {current_date}

From: [Provider Name]
      [Provider Address]
      [Provider Phone / Fax]

To: {payer}
    Appeals Department

Re: Appeal of Prior Authorization Denial
    Patient: {first} {last}
    DOB: {dob}
    Member ID: {member_id}
    Prior Auth Reference: {auth_ref}
    Service Requested: CPT {cpt}

Dear Appeals Reviewer,

I am writing to formally appeal the denial of prior authorization for the above-referenced service.
The denial cited: "{denial_analysis['denial_reason']}"

{denial_analysis['primary_appeal_argument']}

CLINICAL SUMMARY:
{getattr(clinical_evidence, 'clinical_summary', 'See attached clinical documentation.')}

SUPPORTING EVIDENCE:
"""
        for evidence in denial_analysis["supporting_evidence"]:
            letter += f"\n{evidence['type'].upper().replace('_', ' ')}:\n"
            for detail in evidence["details"]:
                letter += f"  - {detail}\n"

        if denial_analysis["urgency_indicators"]:
            letter += f"""
CLINICAL URGENCY:
The patient exhibits the following urgency indicators: {', '.join(denial_analysis['urgency_indicators'])}.
This warrants expedited review.
"""

        letter += f"""
CONCLUSION:
Based on the clinical documentation provided, I respectfully request that this prior authorization be approved.
I am available for a peer-to-peer review at your convenience.

Sincerely,

[Provider Signature]
[Provider Name]
[Credentials]
{current_date}

cc: Patient
Enclosures: Clinical Documentation, Prior Medical Records
"""
        return letter

    # ------------------------------------------------------------------ #
    #  Supplementary helpers                                               #
    # ------------------------------------------------------------------ #

    async def generate_appeal_summary(
        self,
        auth_request: Any,
        denial_analysis: Dict[str, Any],
        appeal_letter: str
    ) -> Dict[str, Any]:
        return {
            "appeal_id": f"APPEAL-{getattr(auth_request, 'id', 'UNKNOWN')[:8].upper()}",
            "original_auth_id": getattr(auth_request, "id", ""),
            "denial_reason": denial_analysis["denial_reason"],
            "primary_argument": denial_analysis["primary_appeal_argument"],
            "success_probability": denial_analysis["success_probability"],
            "peer_review_recommended": denial_analysis["peer_review_recommended"],
            "urgency_level": "high" if denial_analysis["urgency_indicators"] else "standard",
            "letter_preview": appeal_letter[:500] + "...",
            "word_count": len(appeal_letter.split()),
            "created_at": datetime.now().isoformat(),
            "status": "draft"
        }

    async def submit_appeal(
        self,
        auth_request: Any,
        appeal_letter: str,
        payer_name: str
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "appeal_id": f"APPEAL-{getattr(auth_request, 'id', 'UNKNOWN')[:8].upper()}",
            "status": "submitted",
            "submitted_at": datetime.now().isoformat(),
            "expected_resolution": "Within 30 days (expedited: 72 hours if approved)",
            "payer_reference": f"APP-{payer_name[:3].upper()}-{datetime.now().strftime('%Y%m%d')}-001"
        }

    def _calculate_success_probability(
        self,
        denial_analysis: Dict[str, Any],
        policy_match: Any
    ) -> float:
        base = 0.3
        if denial_analysis["supporting_evidence"]:
            base += 0.15
        if denial_analysis["peer_review_recommended"]:
            base += 0.10
        if policy_match and getattr(policy_match, "match_score", 0) > 0.5:
            base += 0.15
        if denial_analysis["urgency_indicators"]:
            base += 0.10
        return min(base, 0.85)

    async def draft_peer_to_peer_summary(
        self,
        auth_request: Any,
        denial_analysis: Dict[str, Any],
        clinical_evidence: Any
    ) -> str:
        patient = auth_request.patient
        first = getattr(patient, "first_name", "") if patient else ""
        last = getattr(patient, "last_name", "") if patient else ""
        dob = getattr(patient, "date_of_birth", "") if patient else ""
        cpt = getattr(auth_request, "cpt_code", "N/A")

        conditions = getattr(clinical_evidence, "conditions", []) or []

        summary = f"""PEER-TO-PEER REVIEW SUMMARY

Patient: {first} {last}
DOB: {dob}
Requested Service: CPT {cpt}

KEY CLINICAL POINTS:
"""
        if conditions:
            summary += "\nDiagnoses:\n"
            for cond in conditions[:3]:
                summary += f"  - {getattr(cond, 'value', str(cond))}\n"

        if denial_analysis["urgency_indicators"]:
            summary += f"\nUrgency Factors: {', '.join(denial_analysis['urgency_indicators'])}\n"

        summary += f"\nAppeal Argument:\n{denial_analysis['primary_appeal_argument']}\n"
        summary += f"\nEstimated Success Probability: {denial_analysis['success_probability']*100:.0f}%"
        return summary