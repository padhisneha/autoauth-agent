"""
Clinical Reader Agent
Extracts medical necessity and clinical evidence from unstructured patient notes.
Uses gpt-4.5-mini for AI-powered summarisation and necessity scoring.
"""

import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from models.schemas import (
    ClinicalEvidence,
    ExtractedEntity,
    ClinicalNote,
    AgentTrace
)

MODEL = "gpt-4.5-mini"


class ClinicalReaderAgent:
    """
    Analyses clinical notes to extract structured medical information
    and determine medical necessity for prior authorization requests.
    """

    def __init__(self, llm_client=None):
        self.agent_name = "ClinicalReader"
        self.llm_client = llm_client

        self.entity_patterns = {
            "condition": [
                r"(?:diagnosed with|has|history of|presents with|suffering from)\s+([^\.]+)",
                r"(?:hypertension|diabetes|cancer|asthma|copd|chf|chd|cva|tia|mi|cad|pad|arrhythmia|epilepsy|parkinson|alzheimer|depression|anxiety|schizophrenia|bipolar|add|adhd|gerd|uti|pneumonia|bronchitis|arthritis|osteoporosis|fibromyalgia|lupus|multiple sclerosis|afib)"
            ],
            "medication": [
                r"(?:prescribed|on|taking|medicated with)\s+([^\.]+)",
                r"\b(metoprolol|lisinopril|amlodipine|metformin|insulin|atorvastatin|simvastatin|omeprazole|pantoprazole|levothyroxine|sertraline|fluoxetine|escitalopram|duloxetine|gabapentin|pregabalin|losartan|hydrochlorothiazide|furosemide|warfarin|apixaban|rivaroxaban|clopidogrel|aspirin|ibuprofen|naproxen|acetaminophen)\b"
            ],
            "procedure": [
                r"(?:performed|conducted|underwent|scheduled for)\s+([^\.]+)",
                r"\b(mri|ct scan|echocardiogram|ecg|ekg|catheterization|biopsy|laparoscopy|endoscopy|colonoscopy|bronchoscopy|angioplasty|stent|replacement|resection|excision|dialysis|transfusion|infusion|therapy|rehab)\b"
            ],
        }

    async def extract_clinical_evidence(
        self,
        clinical_notes: List[ClinicalNote],
        patient_id: str,
        requested_service: str,
        requested_cpt: str
    ) -> ClinicalEvidence:
        """Main entry point for clinical evidence extraction."""

        combined_text = "\n\n".join([note.content for note in clinical_notes])

        conditions = await self._extract_conditions(combined_text, requested_service)
        procedures = await self._extract_procedures(combined_text, requested_service)
        medications = await self._extract_medications(combined_text)
        lab_results = await self._extract_lab_results(combined_text)
        vital_signs = await self._extract_vital_signs(combined_text)
        allergies = await self._extract_allergies(combined_text)

        clinical_summary = await self._generate_clinical_summary_llm(
            combined_text, conditions, procedures, medications, requested_service, requested_cpt
        )

        extraction_confidence = self._calculate_confidence(conditions, procedures, medications)

        return ClinicalEvidence(
            patient_id=patient_id,
            conditions=conditions,
            procedures=procedures,
            medications=medications,
            lab_results=lab_results,
            vital_signs=vital_signs,
            allergies=allergies,
            clinical_summary=clinical_summary,
            extraction_confidence=extraction_confidence
        )

    # ------------------------------------------------------------------ #
    #  LLM-powered methods                                                 #
    # ------------------------------------------------------------------ #

    async def _generate_clinical_summary_llm(
        self,
        raw_notes: str,
        conditions: List[ExtractedEntity],
        procedures: List[ExtractedEntity],
        medications: List[ExtractedEntity],
        requested_service: str,
        requested_cpt: str
    ) -> str:
        """Use gpt-4.5-mini to write a tight clinical summary for the PA request."""

        if not self.llm_client:
            return self._generate_clinical_summary_fallback(
                conditions, procedures, medications, requested_service
            )

        cond_str = ", ".join(c.value for c in conditions[:6]) or "none documented"
        med_str = ", ".join(m.value for m in medications[:5]) or "none documented"
        proc_str = ", ".join(p.value for p in procedures[:4]) or "none documented"

        prompt = f"""You are a clinical documentation specialist preparing a prior authorization summary.

Clinical notes (verbatim):
\"\"\"
{raw_notes[:3000]}
\"\"\"

Extracted entities:
- Diagnoses: {cond_str}
- Medications: {med_str}
- Prior procedures/treatments: {proc_str}
- Requested service: {requested_service} (CPT {requested_cpt})

Write a concise 3–5 sentence clinical summary that:
1. States the primary diagnosis and duration of symptoms
2. Lists prior conservative treatments tried and their outcomes
3. Explains why the requested service is medically necessary
4. Includes any relevant urgency indicators

Be factual. Use only information present in the notes above."""

        try:
            response = await self.llm_client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.2
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return self._generate_clinical_summary_fallback(
                conditions, procedures, medications, requested_service
            )

    async def analyze_medical_necessity(
        self,
        clinical_evidence: ClinicalEvidence,
        requested_service: str,
        cpt_code: str
    ) -> Dict[str, Any]:
        """Use gpt-4.5-mini to score medical necessity and generate reasoning."""

        if not self.llm_client:
            return self._analyze_medical_necessity_fallback(clinical_evidence, requested_service)

        cond_str = ", ".join(c.value for c in clinical_evidence.conditions[:6]) or "none"
        med_str = ", ".join(m.value for m in clinical_evidence.medications[:5]) or "none"
        proc_str = ", ".join(p.value for p in clinical_evidence.procedures[:4]) or "none"

        prompt = f"""You are a utilization management nurse reviewing a prior authorization request.

Service requested: {requested_service} (CPT {cpt_code})
Clinical summary: {clinical_evidence.clinical_summary}
Diagnoses: {cond_str}
Current medications: {med_str}
Prior treatments: {proc_str}

Evaluate medical necessity and respond ONLY with a JSON object in this exact format:
{{
  "necessity_score": <float 0.0-1.0>,
  "recommendation": "<approved|needs_review|denied>",
  "factors": [
    {{"factor": "<name>", "supported": <true|false>, "details": "<one sentence>"}}
  ],
  "summary": "<two sentence medical necessity justification>"
}}"""

        try:
            response = await self.llm_client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            return result
        except Exception:
            return self._analyze_medical_necessity_fallback(clinical_evidence, requested_service)

    # ------------------------------------------------------------------ #
    #  Pattern-based extraction (unchanged, still fast + reliable)         #
    # ------------------------------------------------------------------ #

    async def _extract_conditions(self, text: str, requested_service: str) -> List[ExtractedEntity]:
        conditions = []
        condition_patterns = [
            r"diagnosed with ([^\.]+)",
            r"history of ([^\.]+)",
            r"presents with ([^\.]+)",
            r"suffering from ([^\.]+)",
            r"has been diagnosed with ([^\.]+)",
            r"active problems?: ([^\.]+)"
        ]
        for pattern in condition_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                val = match.group(1).strip()
                if val and len(val) > 2:
                    conditions.append(ExtractedEntity(
                        type="condition",
                        value=val,
                        code=self._map_to_icd10(val),
                        code_system="ICD-10-CM",
                        confidence=0.85,
                        is_negated=self._is_negated(text, val)
                    ))

        if requested_service:
            related = self._infer_related_condition(requested_service)
            if related:
                conditions.append(ExtractedEntity(
                    type="condition",
                    value=related["condition"],
                    code=related["icd10"],
                    code_system="ICD-10-CM",
                    confidence=0.7,
                    context=f"Reason for {requested_service}"
                ))
        return conditions

    async def _extract_procedures(self, text: str, requested_service: str) -> List[ExtractedEntity]:
        procedures = []
        patterns = [
            r"procedure(?:s)?: ([^\.]+)",
            r"performed ([^\.]+)",
            r"underwent ([^\.]+)",
            r"scheduled for ([^\.]+)",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                val = match.group(1).strip()
                if val and len(val) > 2:
                    procedures.append(ExtractedEntity(
                        type="procedure",
                        value=val,
                        code=self._map_to_cpt(val),
                        code_system="CPT",
                        confidence=0.8
                    ))
        return procedures

    async def _extract_medications(self, text: str) -> List[ExtractedEntity]:
        medications = []
        patterns = [
            r"medications?: ([^\.]+)",
            r"prescribed ([^\.]+)",
            r"currently taking ([^\.]+)",
            r"on (?:the following )?medications?: ([^\.]+)"
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                val = match.group(1).strip()
                if val and len(val) > 2:
                    medications.append(ExtractedEntity(type="medication", value=val, confidence=0.75))
        return medications

    async def _extract_lab_results(self, text: str) -> List[ExtractedEntity]:
        labs = []
        pattern = r"(glucose|hba1c|creatinine|bnp|troponin|wbc|rbc|hemoglobin|hematocrit|platelets|sodium|potassium|chloride|bun|alt|ast|alp|ggt|bilirubin|total protein|albumin|tsh|ft4|psa)\s*:?\s*(\d+\.?\d*)"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            labs.append(ExtractedEntity(
                type="lab_result",
                value=f"{match.group(1)}: {match.group(2)}",
                confidence=0.9
            ))
        return labs

    async def _extract_vital_signs(self, text: str) -> List[ExtractedEntity]:
        vitals = []
        patterns = [
            r"(?:blood pressure|bp):\s*(\d+/\d+)",
            r"(?:heart rate|hr|pulse):\s*(\d+)\s*(?:bpm)?",
            r"(?:temperature|temp):\s*(\d+\.?\d*)\s*(?:°|degrees)?\s*(f|c)",
            r"(?:oxygen saturation|spo2|o2 sat|o2):\s*(\d+)%?",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                vitals.append(ExtractedEntity(
                    type="vital_sign",
                    value=" ".join(g for g in match.groups() if g),
                    confidence=0.9
                ))
        return vitals

    async def _extract_allergies(self, text: str) -> List[ExtractedEntity]:
        allergies = []
        patterns = [
            r"(?:allergic to|allergy to)\s+([^\.]+)",
            r"allergies?:\s*([^\.]+)",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                val = match.group(1).strip()
                if val:
                    allergies.append(ExtractedEntity(type="allergy", value=val, confidence=0.85))
        return allergies

    # ------------------------------------------------------------------ #
    #  Fallbacks (no LLM key)                                              #
    # ------------------------------------------------------------------ #

    def _generate_clinical_summary_fallback(self, conditions, procedures, medications, requested_service):
        cond_str = ", ".join(c.value for c in conditions[:5]) or "documented conditions"
        med_str = ", ".join(m.value for m in medications[:3])
        proc_str = ", ".join(p.value for p in procedures[:2])
        summary = f"Patient presents with {cond_str}. "
        if med_str:
            summary += f"Current medications include {med_str}. "
        if proc_str:
            summary += f"Prior treatment history includes {proc_str}. "
        summary += f"The requested service is {requested_service}."
        return summary

    def _analyze_medical_necessity_fallback(self, clinical_evidence, requested_service):
        factors = []
        if clinical_evidence.conditions:
            factors.append({"factor": "documented_conditions", "supported": True, "details": f"{len(clinical_evidence.conditions)} conditions documented"})
        else:
            factors.append({"factor": "documented_conditions", "supported": False, "details": "No conditions found"})
        if clinical_evidence.procedures or clinical_evidence.medications:
            factors.append({"factor": "prior_treatments", "supported": True, "details": "Prior treatments documented"})
        urgency = any(t in clinical_evidence.clinical_summary.lower() for t in ["emergency", "urgent", "acute", "severe"])
        factors.append({"factor": "urgency", "supported": urgency, "details": "Urgent indicators present" if urgency else "Standard priority"})
        score = sum(1 for f in factors if f["supported"]) / len(factors)
        return {
            "necessity_score": score,
            "factors": factors,
            "recommendation": "approved" if score >= 0.6 else "needs_review",
            "summary": clinical_evidence.clinical_summary
        }

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _calculate_confidence(self, conditions, procedures, medications) -> float:
        base = 0.5
        if conditions: base += 0.2
        if procedures: base += 0.15
        if medications: base += 0.15
        return min(base, 0.95)

    def _map_to_icd10(self, condition: str) -> Optional[str]:
        icd10_map = {
            "chest pain": "R07.9", "hypertension": "I10", "diabetes": "E11.9",
            "type 2 diabetes": "E11.9", "back pain": "M54.5", "low back pain": "M54.5",
            "headache": "R51", "migraine": "G43.909", "depression": "F32.9",
            "anxiety": "F41.9", "asthma": "J45.909", "copd": "J44.9",
            "heart failure": "I50.9", "coronary artery disease": "I25.10",
            "atrial fibrillation": "I48.91", "stroke": "I63.9", "cancer": "C80.1",
            "knee pain": "M25.56", "shoulder pain": "M25.51", "abdominal pain": "R10.9",
            "gerd": "K21.0", "uti": "N39.0", "pneumonia": "J18.9",
            "arthritis": "M19.90", "osteoporosis": "M81.0", "fibromyalgia": "M79.7",
            "kidney disease": "N18.9", "prostate cancer": "C61",
            "rotator cuff": "M75.10", "radiculopathy": "M54.4",
        }
        cl = condition.lower()
        for key, code in icd10_map.items():
            if key in cl:
                return code
        return None

    def _map_to_cpt(self, procedure: str) -> Optional[str]:
        cpt_map = {
            "mri": "70551", "mri knee": "73721", "mri shoulder": "73221",
            "mri spine": "72148", "ct scan": "70450", "ct abdomen": "74177",
            "echocardiogram": "93306", "ecg": "93000", "colonoscopy": "45378",
            "physical therapy": "97110",
        }
        pl = procedure.lower()
        for key, code in cpt_map.items():
            if key in pl:
                return code
        return None

    def _infer_related_condition(self, service: str) -> Optional[Dict]:
        mapping = {
            "mri": {"condition": "Imaging evaluation required", "icd10": "Z03.89"},
            "ct_scan": {"condition": "CT imaging evaluation required", "icd10": "Z03.89"},
            "surgery": {"condition": "Surgical intervention required", "icd10": "Z98.890"},
            "physical_therapy": {"condition": "Rehabilitation required", "icd10": "M53.9"},
        }
        sl = service.lower()
        for key, data in mapping.items():
            if key in sl:
                return data
        return None

    def _is_negated(self, text: str, entity: str) -> bool:
        pattern = r"(?:no|not|without|denies|negative|ruled? ?out|absence of)\s+" + re.escape(entity)
        return bool(re.search(pattern, text, re.IGNORECASE))