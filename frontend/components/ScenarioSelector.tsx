'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Play, FileText, Heart, Bone, Brain, Wind, Activity, Zap } from 'lucide-react';

interface Scenario {
  id: string; title: string; description: string;
  patient: { name: string; age: number; condition: string };
  service: { type: string; cpt: string; icd10: string };
  badge?: string; badgeColor?: string;
}

const scenarios: Scenario[] = [
  {
    id:'cardiology-mri', title:'Lumbar Spine MRI',
    description:'Chronic back pain with radiculopathy — failed 6 weeks PT',
    patient:{name:'John Smith', age:58, condition:'Low back pain, radiculopathy'},
    service:{type:'MRI', cpt:'72148', icd10:'M54.5'},
  },
  {
    id:'orthopedics-mri', title:'Shoulder MRI',
    description:'Suspected rotator cuff tear — failed conservative treatment',
    patient:{name:'Sarah Johnson', age:45, condition:'Rotator cuff tear'},
    service:{type:'MRI', cpt:'73221', icd10:'M75.10'},
  },
  {
    id:'oncology-ct', title:'CT Abdomen/Pelvis',
    description:'Prostate cancer staging workup per NCCN guidelines',
    patient:{name:'Michael Chen', age:70, condition:'Prostate cancer'},
    service:{type:'CT Scan', cpt:'74177', icd10:'C61'},
    badge:'Oncology', badgeColor:'bg-purple-100 text-purple-700',
  },
  {
    id:'asthma-biologic', title:'Dupilumab — Asthma',
    description:'Step 5 biologic therapy, failed high-dose ICS + 2 ED visits',
    patient:{name:'Maria Rodriguez', age:52, condition:'Uncontrolled moderate asthma'},
    service:{type:'Biologic Rx', cpt:'J0173', icd10:'J45.50'},
    badge:'High Denial Risk', badgeColor:'bg-red-100 text-red-700',
  },
  {
    id:'cardiology-device', title:'CRT-D Implant',
    description:'CHF EF 30%, NYHA Class III, LBBB — ACC/AHA Class I indication',
    patient:{name:'James Williams', age:76, condition:'Decompensated CHF'},
    service:{type:'Surgery', cpt:'33249', icd10:'I50.9'},
    badge:'Complex', badgeColor:'bg-orange-100 text-orange-700',
  },
  {
    id:'ms-biologic', title:'Natalizumab — MS',
    description:'Active RRMS, 2 relapses + new MRI lesions on interferon',
    patient:{name:'Emily Patel', age:34, condition:'Relapsing-remitting MS'},
    service:{type:'Infusion Rx', cpt:'J2323', icd10:'G35'},
    badge:'High Denial Risk', badgeColor:'bg-red-100 text-red-700',
  },
];

const iconMap: Record<string, React.ElementType> = {
  'cardiology-mri':   Brain,
  'orthopedics-mri':  Bone,
  'oncology-ct':      FileText,
  'asthma-biologic':  Wind,
  'cardiology-device':Activity,
  'ms-biologic':      Zap,
};

interface Props { onProcessingStarted: (authId: string) => void; }

export function ScenarioSelector({ onProcessingStarted }: Props) {
  const [selectedId, setSelectedId] = useState<string|null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleStart = async (scenarioId: string) => {
    setSelectedId(scenarioId); setSubmitting(true);
    try {
      const sr = await fetch('/api/demo/scenario', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({scenario_id: scenarioId}),
      });
      const sd = await sr.json();

      const ar = await fetch('/api/auth/initiate', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          patient_id:   sd.scenario.patient_id,
          service_type: sd.scenario.service_type,
          cpt_code:     sd.scenario.cpt_code,
          icd10_code:   sd.scenario.icd10_code,
        }),
      });
      const ad = await ar.json();
      onProcessingStarted(ad.auth_id);
    } catch (e) {
      console.error('Scenario failed:', e);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
      <div className="mb-5">
        <h2 className="text-lg font-semibold text-slate-900">Demo Scenarios</h2>
        <p className="text-sm text-slate-500">Select a clinical scenario — the Prediction Engine will assess approval probability before submitting</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {scenarios.map(s => {
          const Icon      = iconMap[s.id] || FileText;
          const isSelected = selectedId === s.id;
          const isLoading  = isSelected && submitting;

          return (
            <motion.button key={s.id}
              whileHover={{scale:1.02}} whileTap={{scale:0.98}}
              onClick={() => handleStart(s.id)}
              disabled={submitting}
              className={`relative p-4 rounded-xl border-2 text-left transition-all duration-200
                ${isSelected ? 'border-blue-500 bg-blue-50' : 'border-slate-200 hover:border-blue-300 hover:shadow-md'}
                ${submitting ? 'opacity-60 cursor-wait' : 'cursor-pointer'}`}>

              <div className="flex items-start justify-between mb-2">
                <div className={`p-2 rounded-lg ${isSelected?'bg-blue-100':'bg-slate-100'}`}>
                  <Icon className={`w-4 h-4 ${isSelected?'text-blue-600':'text-slate-600'}`}/>
                </div>
                <div className="flex items-center gap-1">
                  {s.badge && (
                    <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${s.badgeColor}`}>
                      {s.badge}
                    </span>
                  )}
                  {isLoading
                    ? <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"/>
                    : <Play className={`w-4 h-4 ${isSelected?'text-blue-500':'text-slate-300'}`}/>
                  }
                </div>
              </div>

              <h3 className="font-semibold text-slate-900 text-sm mb-0.5">{s.title}</h3>
              <p className="text-xs text-slate-500 mb-2 line-clamp-2">{s.description}</p>

              <div className="border-t border-slate-100 pt-2 space-y-1">
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                  <Heart className="w-3 h-3"/>
                  <span>{s.patient.name}, {s.patient.age}y</span>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-slate-400">
                  <span className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">{s.service.cpt}</span>
                  <span>{s.service.icd10}</span>
                  <span className="ml-auto text-slate-300">{s.service.type}</span>
                </div>
              </div>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}