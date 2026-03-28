"""
Appeal Agent - generates clinically accurate appeal letters.
Uses real provider info from auth_request (provider_name, provider_facility, etc.)
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional

MODEL = "gpt-4.5-mini"


class AppealAgent:
    def __init__(self, llm_client=None):
        self.agent_name = "AppealAgent"
        self.llm_client = llm_client

    async def analyze_denial(self, auth_request, denial_reason, clinical_evidence, policy_match):
        analysis = {
            "denial_reason": denial_reason,
            "primary_appeal_argument": "",
            "supporting_evidence": [],
            "missing_documentation": [],
            "urgency_indicators": [],
            "peer_review_recommended": False,
            "success_probability": 0.5
        }

        denial_map = {
            "insufficient conservative treatment": {
                "argument": "The patient has documented prior conservative treatments that demonstrate medical necessity and failure of non-invasive management.",
                "evidence_needed": ["prior_procedures", "medications", "physician_notes"]
            },
            "not medically necessary": {
                "argument": "The requested service is medically necessary based on the patient's specific clinical presentation, diagnosis, and documented failure of conservative management.",
                "evidence_needed": ["conditions", "clinical_summary", "lab_results"]
            },
            "incomplete documentation": {
                "argument": "This appeal provides comprehensive clinical documentation that fully supports medical necessity.",
                "evidence_needed": ["clinical_summary", "physician_notes"]
            },
            "experimental": {
                "argument": "The requested service is a standard, evidence-based treatment supported by peer-reviewed literature and applicable clinical guidelines.",
                "evidence_needed": ["guidelines", "clinical_trials"]
            },
            "anticipated": {
                "argument": "This proactive appeal package provides comprehensive documentation demonstrating that all policy criteria are met prior to payer review.",
                "evidence_needed": ["clinical_summary", "conditions", "medications"]
            },
        }

        dl = denial_reason.lower()
        for key, data in denial_map.items():
            if key in dl:
                analysis["primary_appeal_argument"] = data["argument"]
                analysis["missing_documentation"]   = data["evidence_needed"]
                break

        if not analysis["primary_appeal_argument"]:
            analysis["primary_appeal_argument"] = (
                "The clinical documentation provided demonstrates clear medical necessity "
                "for the requested service based on the patient's diagnosis and clinical presentation."
            )

        conditions  = getattr(clinical_evidence, "conditions",  []) or []
        procedures  = getattr(clinical_evidence, "procedures",  []) or []
        medications = getattr(clinical_evidence, "medications", []) or []
        lab_results = getattr(clinical_evidence, "lab_results", []) or []
        summary     = getattr(clinical_evidence, "clinical_summary", "") or ""

        if conditions:
            analysis["supporting_evidence"].append({
                "type": "diagnoses",
                "details": [getattr(c,"value",str(c)) for c in conditions[:5]]
            })
        if procedures:
            analysis["supporting_evidence"].append({
                "type": "prior_treatments",
                "details": [getattr(p,"value",str(p)) for p in procedures[:5]]
            })
        if medications:
            analysis["supporting_evidence"].append({
                "type": "current_medications",
                "details": [getattr(m,"value",str(m)) for m in medications[:5]]
            })
        if lab_results:
            analysis["supporting_evidence"].append({
                "type": "lab_results",
                "details": [getattr(l,"value",str(l)) for l in lab_results[:3]]
            })

        urgency_terms = ["progressive","worsening","severe","acute","debilitating","chronic pain","cancer","malignancy","stage","gleason"]
        analysis["urgency_indicators"] = [t for t in urgency_terms if t in summary.lower()]

        if analysis["urgency_indicators"]:
            analysis["peer_review_recommended"] = True

        analysis["success_probability"] = self._calc_prob(analysis, policy_match)
        return analysis

    async def generate_appeal_letter(self, auth_request, denial_analysis, clinical_evidence, policy_match):
        if self.llm_client:
            return await self._llm_letter(auth_request, denial_analysis, clinical_evidence, policy_match)
        return self._template_letter(auth_request, denial_analysis, clinical_evidence, policy_match)

    # ── LLM letter ────────────────────────────────────────────────────────────

    async def _llm_letter(self, auth_request, denial_analysis, clinical_evidence, policy_match):
        patient  = auth_request.patient
        cur_date = datetime.now().strftime("%B %d, %Y")

        # Real provider info from auth_request
        provider_name     = getattr(auth_request, "provider_name",     "Dr. Attending Physician, MD")
        provider_facility = getattr(auth_request, "provider_facility",  "Boston Medical Center")
        provider_address  = getattr(auth_request, "provider_address",   "100 Medical Dr, Boston MA 02101")
        provider_phone    = getattr(auth_request, "provider_phone",     "(617) 555-0000")
        provider_fax      = getattr(auth_request, "provider_fax",      "(617) 555-0001")

        payer   = getattr(patient, "payer_name",   "Insurance Company") if patient else "Insurance Company"
        first   = getattr(patient, "first_name",   "") if patient else ""
        last    = getattr(patient, "last_name",    "") if patient else ""
        dob     = getattr(patient, "date_of_birth","") if patient else ""
        member  = getattr(patient, "insurance_id", "") if patient else ""
        cpt     = getattr(auth_request, "cpt_code", "N/A")
        auth_ref= getattr(auth_request, "id", "N/A")

        cond_str = ", ".join(getattr(c,"value",str(c)) for c in (getattr(clinical_evidence,"conditions",[]) or [])[:6]) or "none documented"
        med_str  = ", ".join(getattr(m,"value",str(m)) for m in (getattr(clinical_evidence,"medications",[]) or [])[:5]) or "none"
        proc_str = ", ".join(getattr(p,"value",str(p)) for p in (getattr(clinical_evidence,"procedures",[]) or [])[:4]) or "none"
        lab_str  = ", ".join(getattr(l,"value",str(l)) for l in (getattr(clinical_evidence,"lab_results",[]) or [])[:3]) or "none"
        summary  = getattr(clinical_evidence, "clinical_summary", "") or ""

        satisfied     = getattr(policy_match, "satisfied_requirements", []) if policy_match else []
        satisfied_str = "\n".join(f"- {s}" for s in satisfied[:5]) or "- See clinical documentation"

        urgency = denial_analysis.get("urgency_indicators", [])
        urgency_str = (
            f"CLINICAL URGENCY: Patient exhibits: {', '.join(urgency)}. Expedited review warranted."
            if urgency else ""
        )

        prompt = f"""You are a physician writing a formal prior authorization appeal letter.

PROVIDER LETTERHEAD:
{provider_name}
{provider_facility}
{provider_address}
Phone: {provider_phone} | Fax: {provider_fax}

Date: {cur_date}

TO:
{payer} — Prior Authorization Appeals Department

RE: Appeal of Prior Authorization Denial
    Patient: {first} {last}
    Date of Birth: {dob}
    Member ID: {member}
    Auth Reference: {auth_ref}
    CPT Code: {cpt}

Denial Reason: {denial_analysis['denial_reason']}
Appeal Argument: {denial_analysis['primary_appeal_argument']}
{urgency_str}

Clinical Summary:
{summary}

Supporting Evidence:
- Diagnoses: {cond_str}
- Medications: {med_str}
- Prior Procedures/Treatments: {proc_str}
- Lab Results: {lab_str}

Policy Criteria Already Satisfied:
{satisfied_str}

Write a complete, professional appeal letter using the above information. Include:
1. The full header as shown above (use exact provider name, facility, address, phone, fax)
2. Professional salutation to the Appeals Reviewer
3. Opening paragraph citing the denial and requesting reconsideration
4. Detailed clinical narrative (use the patient's actual diagnoses and treatments)
5. Direct rebuttal of the denial reason with clinical justification
6. Statement of which policy criteria are satisfied
7. Urgency section if applicable
8. Conclusion requesting approval and offering peer-to-peer review
9. Full signature block with {provider_name}, {provider_facility}, {cur_date}

Be specific, clinical, and persuasive. Use the real names and data provided — do not use placeholder brackets."""

        try:
            resp = await self.llm_client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.2
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return self._template_letter(auth_request, denial_analysis, clinical_evidence, policy_match)

    # ── Template fallback ─────────────────────────────────────────────────────

    def _template_letter(self, auth_request, denial_analysis, clinical_evidence, policy_match):
        patient  = auth_request.patient
        cur_date = datetime.now().strftime("%B %d, %Y")

        provider_name     = getattr(auth_request, "provider_name",     "Dr. Attending Physician, MD")
        provider_facility = getattr(auth_request, "provider_facility",  "Boston Medical Center")
        provider_address  = getattr(auth_request, "provider_address",   "100 Medical Dr, Boston MA 02101")
        provider_phone    = getattr(auth_request, "provider_phone",     "(617) 555-0000")
        provider_fax      = getattr(auth_request, "provider_fax",      "(617) 555-0001")

        payer   = getattr(patient, "payer_name",   "Insurance Company") if patient else "Insurance Company"
        first   = getattr(patient, "first_name",   "") if patient else ""
        last    = getattr(patient, "last_name",    "") if patient else ""
        dob     = getattr(patient, "date_of_birth","") if patient else ""
        member  = getattr(patient, "insurance_id", "") if patient else ""
        cpt     = getattr(auth_request, "cpt_code", "N/A")
        auth_ref= getattr(auth_request, "id", "N/A")
        summary = getattr(clinical_evidence, "clinical_summary", "See attached clinical documentation.") or ""
        conditions = getattr(clinical_evidence, "conditions", []) or []

        letter = f"""{provider_name}
{provider_facility}
{provider_address}
Phone: {provider_phone} | Fax: {provider_fax}

Date: {cur_date}

{payer}
Prior Authorization Appeals Department

RE: Appeal of Prior Authorization Denial
    Patient: {first} {last}
    Date of Birth: {dob}
    Member ID: {member}
    Auth Reference: {auth_ref}
    CPT Code Requested: {cpt}

Dear Prior Authorization Appeals Reviewer,

I am writing to formally appeal the denial of prior authorization for the above-referenced service. After careful review of the denial and the patient's complete medical record, I respectfully request that this decision be reconsidered.

The denial stated: "{denial_analysis['denial_reason']}"

{denial_analysis['primary_appeal_argument']}

CLINICAL SUMMARY:
{summary}

"""
        if conditions:
            letter += "DIAGNOSES:\n"
            for i, c in enumerate(conditions, 1):
                code = getattr(c, "code", "") or ""
                val  = getattr(c, "value", str(c))
                letter += f"  {i}. {val}" + (f" (ICD-10: {code})" if code else "") + "\n"
            letter += "\n"

        for ev in denial_analysis.get("supporting_evidence", []):
            letter += f"{ev['type'].upper().replace('_',' ')}:\n"
            for d in ev["details"]:
                letter += f"  - {d}\n"
            letter += "\n"

        if denial_analysis.get("urgency_indicators"):
            letter += f"CLINICAL URGENCY:\nThe patient presents with: {', '.join(denial_analysis['urgency_indicators'])}. This warrants expedited review.\n\n"

        letter += f"""CONCLUSION:
Based on the clinical documentation provided, I respectfully request that this prior authorization be approved. The requested service is medically necessary and appropriate for this patient's condition.

I am available for peer-to-peer review at your convenience. Please contact our office at {provider_phone} to schedule.

Thank you for your consideration.

Sincerely,

{provider_name}
{provider_facility}
{cur_date}

cc: Patient File
Enclosures: Clinical Notes, Lab Results, Prior Treatment Records
"""
        return letter

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def generate_appeal_summary(self, auth_request, denial_analysis, appeal_letter):
        return {
            "appeal_id":              f"APPEAL-{getattr(auth_request,'id','')[:8].upper()}",
            "original_auth_id":       getattr(auth_request, "id", ""),
            "denial_reason":          denial_analysis["denial_reason"],
            "primary_argument":       denial_analysis["primary_appeal_argument"],
            "success_probability":    denial_analysis["success_probability"],
            "peer_review_recommended":denial_analysis["peer_review_recommended"],
            "urgency_level":          "high" if denial_analysis["urgency_indicators"] else "standard",
            "word_count":             len(appeal_letter.split()),
            "created_at":             datetime.now().isoformat(),
            "status":                 "draft"
        }

    def _calc_prob(self, analysis, policy_match):
        base = 0.3
        if analysis["supporting_evidence"]:   base += 0.15
        if analysis["peer_review_recommended"]:base += 0.10
        if policy_match and getattr(policy_match, "match_score", 0) > 0.5: base += 0.15
        if analysis["urgency_indicators"]:     base += 0.10
        return min(base, 0.85)