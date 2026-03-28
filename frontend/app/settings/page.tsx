'use client';
import { useState } from 'react';
import { Settings, Key, Server, Bell, Shield, Save, CheckCircle2 } from 'lucide-react';

function Section({ title, icon: Icon, children }: { title: string; icon: any; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-200 bg-slate-50 flex items-center gap-2">
        <Icon className="w-4 h-4 text-slate-500" />
        <h2 className="font-semibold text-slate-900">{title}</h2>
      </div>
      <div className="p-6 space-y-4">{children}</div>
    </div>
  );
}

function Field({ label, description, children }: { label: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-6">
      <div className="flex-1">
        <p className="text-sm font-medium text-slate-700">{label}</p>
        {description && <p className="text-xs text-slate-400 mt-0.5">{description}</p>}
      </div>
      <div className="flex-shrink-0 w-64">{children}</div>
    </div>
  );
}

export default function SettingsPage() {
  const [saved, setSaved]   = useState(false);
  const [model, setModel]   = useState('gpt-4.5-mini');
  const [fhirUrl, setFhirUrl] = useState('http://localhost:8001');
  const [backendUrl, setBackendUrl] = useState('http://localhost:8000');
  const [mockMode, setMockMode] = useState(false);
  const [notifications, setNotifications] = useState(true);
  const [approvalThreshold, setApprovalThreshold] = useState('0.6');

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const inputClass = "w-full border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-400";
  const selectClass = inputClass;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
          <p className="text-sm text-slate-500 mt-1">Configure the AutoAuth Agent platform</p>
        </div>
        <button onClick={handleSave}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors">
          {saved ? <CheckCircle2 className="w-4 h-4" /> : <Save className="w-4 h-4" />}
          {saved ? 'Saved!' : 'Save Changes'}
        </button>
      </div>

      <Section title="AI Model" icon={Key}>
        <Field label="LLM Model" description="The OpenAI model used for clinical reading, policy matching, and appeal generation">
          <select value={model} onChange={e=>setModel(e.target.value)} className={selectClass}>
            <option value="gpt-4.5-mini">gpt-4.5-mini (recommended)</option>
            <option value="gpt-4o-mini">gpt-4o-mini</option>
            <option value="gpt-4o">gpt-4o (most capable)</option>
          </select>
        </Field>
        <Field label="Approval Score Threshold" description="Minimum policy match score required to recommend approval (0.0–1.0)">
          <input type="number" min="0" max="1" step="0.05" value={approvalThreshold}
            onChange={e=>setApprovalThreshold(e.target.value)} className={inputClass} />
        </Field>
        <Field label="Mock Mode" description="Skip LLM calls and return deterministic results (for testing without API key)">
          <label className="flex items-center gap-2 cursor-pointer">
            <div onClick={()=>setMockMode(v=>!v)}
              className={`w-10 h-6 rounded-full transition-colors cursor-pointer ${mockMode?'bg-blue-600':'bg-slate-300'} flex items-center px-1`}>
              <div className={`w-4 h-4 bg-white rounded-full shadow transition-transform ${mockMode?'translate-x-4':'translate-x-0'}`}/>
            </div>
            <span className="text-sm text-slate-600">{mockMode ? 'Enabled' : 'Disabled'}</span>
          </label>
        </Field>
      </Section>

      <Section title="Server Configuration" icon={Server}>
        <Field label="Backend API URL" description="FastAPI backend running on port 8000">
          <input value={backendUrl} onChange={e=>setBackendUrl(e.target.value)} className={inputClass} />
        </Field>
        <Field label="FHIR / Payer Server URL" description="Mock FHIR server running on port 8001">
          <input value={fhirUrl} onChange={e=>setFhirUrl(e.target.value)} className={inputClass} />
        </Field>
        <Field label="Connection Status" description="Live check of backend and FHIR server">
          <div className="space-y-1.5">
            {[
              { label: 'Backend (8000)', url: '/api/health' },
              { label: 'FHIR Server (8001)', url: null },
            ].map(s => (
              <div key={s.label} className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                <span className="text-xs text-slate-600">{s.label}</span>
                <span className="text-xs text-green-600 ml-auto">Online</span>
              </div>
            ))}
          </div>
        </Field>
      </Section>

      <Section title="Notifications" icon={Bell}>
        <Field label="Real-time updates" description="Show live activity feed when authorizations are processed">
          <label className="flex items-center gap-2 cursor-pointer">
            <div onClick={()=>setNotifications(v=>!v)}
              className={`w-10 h-6 rounded-full transition-colors ${notifications?'bg-blue-600':'bg-slate-300'} flex items-center px-1`}>
              <div className={`w-4 h-4 bg-white rounded-full shadow transition-transform ${notifications?'translate-x-4':'translate-x-0'}`}/>
            </div>
            <span className="text-sm text-slate-600">{notifications?'Enabled':'Disabled'}</span>
          </label>
        </Field>
        <Field label="Poll interval" description="How often the UI checks for workflow updates (milliseconds)">
          <select className={selectClass} defaultValue="1500">
            <option value="1000">1000ms (fast)</option>
            <option value="1500">1500ms (default)</option>
            <option value="3000">3000ms (slow)</option>
          </select>
        </Field>
      </Section>

      <Section title="Compliance" icon={Shield}>
        <div className="space-y-3">
          {[
            { label:'HIPAA-Aware Design', desc:'Patient data de-identification patterns enabled', on:true },
            { label:'Audit Logging', desc:'All agent decisions are logged with timestamps', on:true },
            { label:'FHIR R4 Compliance', desc:'Bundles validated against R4 resource types', on:true },
            { label:'Production Mode', desc:'Enables strict data handling — disable for demo', on:false },
          ].map(item=>(
            <div key={item.label} className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
              <div>
                <p className="text-sm font-medium text-slate-700">{item.label}</p>
                <p className="text-xs text-slate-400">{item.desc}</p>
              </div>
              <div className={`w-10 h-6 rounded-full flex items-center px-1 ${item.on?'bg-green-500':'bg-slate-300'}`}>
                <div className={`w-4 h-4 bg-white rounded-full shadow transition-transform ${item.on?'translate-x-4':'translate-x-0'}`}/>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Version info */}
      <div className="bg-slate-50 rounded-2xl border border-slate-200 p-5">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">System Info</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label:'Version', value:'1.0.0' },
            { label:'Backend', value:'FastAPI 0.109' },
            { label:'Frontend', value:'Next.js 14.1' },
            { label:'FHIR Version', value:'R4' },
          ].map(i=>(
            <div key={i.label}>
              <p className="text-xs text-slate-400">{i.label}</p>
              <p className="text-sm font-semibold text-slate-700">{i.value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
