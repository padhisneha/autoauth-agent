'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Play, FileText, Heart, Bone, Brain } from 'lucide-react';

interface Scenario {
  id: string;
  title: string;
  description: string;
  patient: {
    name: string;
    age: number;
    condition: string;
  };
  service: {
    type: string;
    cpt: string;
    icd10: string;
  };
}

const scenarios: Scenario[] = [
  {
    id: 'cardiology-mri',
    title: 'Lumbar Spine MRI',
    description: 'Chronic back pain with radiculopathy - failed 6 weeks PT',
    patient: { name: 'John Smith', age: 58, condition: 'Low back pain with radiculopathy' },
    service: { type: 'MRI', cpt: '72148', icd10: 'M54.5' },
  },
  {
    id: 'orthopedics-mri',
    title: 'Shoulder MRI',
    description: 'Suspected rotator cuff tear - failed conservative treatment',
    patient: { name: 'Sarah Johnson', age: 45, condition: 'Rotator cuff tear' },
    service: { type: 'MRI', cpt: '73221', icd10: 'M75.10' },
  },
  {
    id: 'oncology-ct',
    title: 'CT Abdomen/Pelvis',
    description: 'Prostate cancer staging workup',
    patient: { name: 'Michael Chen', age: 70, condition: 'Prostate cancer staging' },
    service: { type: 'CT Scan', cpt: '74177', icd10: 'C61' },
  },
];

const iconMap: Record<string, React.ElementType> = {
  'cardiology-mri': Brain,
  'orthopedics-mri': Bone,
  'oncology-ct': FileText,
};

interface ScenarioSelectorProps {
  onProcessingStarted: (authId: string) => void;
}

export function ScenarioSelector({ onProcessingStarted }: ScenarioSelectorProps) {
  const [selectedScenario, setSelectedScenario] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleStartScenario = async (scenarioId: string) => {
    setSelectedScenario(scenarioId);
    setIsSubmitting(true);

    try {
      // Get scenario details
      const scenarioRes = await fetch('/api/demo/scenario', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: scenarioId }),
      });
      const scenarioData = await scenarioRes.json();

      // Initiate authorization
      const authRes = await fetch('/api/auth/initiate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id: scenarioData.scenario.patient_id,
          service_type: scenarioData.scenario.service_type,
          cpt_code: scenarioData.scenario.cpt_code,
          icd10_code: scenarioData.scenario.icd10_code,
        }),
      });
      const authData = await authRes.json();

      // Pass auth_id back to parent — no localStorage needed
      onProcessingStarted(authData.auth_id);

    } catch (error) {
      console.error('Failed to start scenario:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Demo Scenarios</h2>
          <p className="text-sm text-slate-500">Select a scenario to see AutoAuth in action</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {scenarios.map((scenario) => {
          const Icon = iconMap[scenario.id] || FileText;
          const isSelected = selectedScenario === scenario.id;
          
          return (
            <motion.button
              key={scenario.id}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => handleStartScenario(scenario.id)}
              disabled={isSubmitting}
              className={`
                relative p-4 rounded-xl border-2 text-left transition-all duration-200
                ${isSelected 
                  ? 'border-blue-500 bg-blue-50' 
                  : 'border-slate-200 hover:border-blue-300 hover:shadow-md'
                }
                ${isSubmitting ? 'opacity-50 cursor-wait' : 'cursor-pointer'}
              `}
            >
              <div className="flex items-start justify-between mb-3">
                <div className={`
                  p-2 rounded-lg
                  ${isSelected ? 'bg-blue-100' : 'bg-slate-100'}
                `}>
                  <Icon className={`w-5 h-5 ${isSelected ? 'text-blue-600' : 'text-slate-600'}`} />
                </div>
                {isSubmitting && isSelected && (
                  <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                )}
                {!isSubmitting && (
                  <Play className={`w-5 h-5 ${isSelected ? 'text-blue-500' : 'text-slate-300'}`} />
                )}
              </div>

              <h3 className="font-semibold text-slate-900 mb-1">{scenario.title}</h3>
              <p className="text-sm text-slate-500 mb-3">{scenario.description}</p>

              <div className="pt-3 border-t border-slate-200">
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <Heart className="w-3 h-3" />
                  <span>{scenario.patient.name}, {scenario.patient.age}y</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-500 mt-1">
                  <span className="px-1.5 py-0.5 bg-slate-100 rounded">{scenario.service.cpt}</span>
                  <span>{scenario.service.icd10}</span>
                </div>
              </div>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}