'use client';
import { useState } from 'react';
import { ChevronDown, ChevronUp, Play, Brain, Shield, Send, FileText, Activity, ExternalLink } from 'lucide-react';

function FAQ({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden">
      <button onClick={() => setOpen(v => !v)}
        className="w-full px-5 py-4 flex items-center justify-between text-left hover:bg-slate-50 transition-colors">
        <p className="font-medium text-slate-800 text-sm">{q}</p>
        {open ? <ChevronUp className="w-4 h-4 text-slate-400 flex-shrink-0" /> : <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />}
      </button>
      {open && (
        <div className="px-5 pb-4 bg-slate-50 border-t border-slate-200">
          <p className="text-sm text-slate-600 leading-relaxed pt-3">{a}</p>
        </div>
      )}
    </div>
  );
}

const agents = [
  { icon: Activity, color: 'bg-pink-100 text-pink-600', name: 'Triage Agent', desc: 'Determines request priority (standard vs urgent) based on service type and clinical indicators.' },
  { icon: Brain,    color: 'bg-purple-100 text-purple-600', name: 'Clinical Reader Agent', desc: 'Reads unstructured clinical notes and extracts diagnoses, medications, procedures, vitals, and lab results using NLP + LLM. Generates a structured clinical summary.' },
  { icon: Shield,   color: 'bg-cyan-100 text-cyan-600', name: 'Policy Agent', desc: 'Retrieves payer-specific prior authorization guidelines and checks whether the clinical evidence meets each requirement using LLM reasoning.' },
  { icon: Send,     color: 'bg-green-100 text-green-600', name: 'Submission Agent', desc: 'Builds a FHIR R4 Bundle from the clinical evidence and submits it to the payer server. Polls for a decision via the ClaimResponse endpoint.' },
  { icon: Activity, color: 'bg-yellow-100 text-yellow-600', name: 'Monitoring Agent', desc: 'Processes the payer\'s decision (approved / denied) and determines the next workflow step.' },
  { icon: FileText, color: 'bg-amber-100 text-amber-600', name: 'Appeal Agent', desc: 'When denied, analyses the denial reason, identifies supporting clinical evidence, and generates a complete appeal letter using the LLM.' },
  { icon: Send,     color: 'bg-orange-100 text-orange-600', name: 'Appeal Submission Agent', desc: 'Resubmits the FHIR bundle with the appeal letter attached to the payer server for a second review.' },
];

export default function HelpPage() {
  return (
    <div className="p-6 max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Help & Documentation</h1>
        <p className="text-sm text-slate-500 mt-1">How AutoAuth Agent works and how to use it</p>
      </div>

      {/* Quick start */}
      <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-6 text-white">
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
          <Play className="w-5 h-5 text-cyan-400" /> Quick Start — Demo Flow
        </h2>
        <ol className="space-y-3">
          {[
            { step: '1', title: 'Start all servers', desc: 'Run the FHIR server (port 8001), backend (port 8000), provider UI (port 3000), and payer UI (port 3001) in separate terminals.' },
            { step: '2', title: 'Select a demo scenario', desc: 'On the dashboard, click one of the three scenario cards (Lumbar Spine MRI, Shoulder MRI, CT Scan).' },
            { step: '3', title: 'Watch the workflow', desc: 'The Live Agent Workflow panel shows each agent activating in real time. All 7 stages complete in about 30–60 seconds.' },
            { step: '4', title: 'Review on the payer portal', desc: 'Open localhost:3001 in another tab. The request appears in the queue. Click it, read the clinical summary, and approve or deny.' },
            { step: '5', title: 'See the result', desc: 'The provider UI updates automatically. If denied, the appeal letter is generated and re-submitted to the payer for a second review.' },
          ].map(s => (
            <li key={s.step} className="flex items-start gap-3">
              <div className="w-6 h-6 bg-cyan-500 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">{s.step}</div>
              <div>
                <p className="font-semibold text-sm">{s.title}</p>
                <p className="text-xs text-slate-400 mt-0.5">{s.desc}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>

      {/* Architecture */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h2 className="text-lg font-bold text-slate-900 mb-2">System Architecture</h2>
        <p className="text-sm text-slate-500 mb-5">Four services communicate over HTTP to simulate the complete PA lifecycle.</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { port:'3000', label:'Provider UI', desc:'Next.js dashboard for the clinical team', color:'bg-blue-50 border-blue-200' },
            { port:'8000', label:'Backend API', desc:'FastAPI — agents + orchestration', color:'bg-purple-50 border-purple-200' },
            { port:'8001', label:'FHIR Server', desc:'Mock payer endpoint + decision API', color:'bg-green-50 border-green-200' },
            { port:'3001', label:'Payer UI', desc:'Next.js portal for the payer reviewer', color:'bg-amber-50 border-amber-200' },
          ].map(s => (
            <div key={s.port} className={`rounded-xl border p-4 ${s.color}`}>
              <p className="text-xs font-mono font-bold text-slate-700 mb-1">:{s.port}</p>
              <p className="font-semibold text-slate-800 text-sm">{s.label}</p>
              <p className="text-xs text-slate-500 mt-1">{s.desc}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 bg-slate-900 text-slate-300 rounded-xl p-4 text-xs font-mono leading-relaxed">
          {`Provider UI → Backend → FHIR Server ← Payer UI
                ↑                    ↓ (ClaimResponse poll)
          WorkflowViz ← SSE ← Backend (callback)`}
        </div>
      </div>

      {/* Agents */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h2 className="text-lg font-bold text-slate-900 mb-4">Agent Reference</h2>
        <div className="space-y-3">
          {agents.map(a => (
            <div key={a.name} className="flex items-start gap-3 p-3 bg-slate-50 rounded-xl">
              <div className={`w-8 h-8 rounded-lg ${a.color} flex items-center justify-center flex-shrink-0`}>
                <a.icon className="w-4 h-4" />
              </div>
              <div>
                <p className="font-semibold text-slate-800 text-sm">{a.name}</p>
                <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{a.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Terminal commands */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h2 className="text-lg font-bold text-slate-900 mb-4">Terminal Commands</h2>
        <div className="space-y-3">
          {[
            { label:'FHIR Server',    cmd:'python fhir_server/fhir_payer_server.py' },
            { label:'Backend',        cmd:'cd backend && python main.py' },
            { label:'Provider UI',    cmd:'cd frontend && npm run dev' },
            { label:'Payer UI',       cmd:'cd payer_ui && npm run dev' },
          ].map(c => (
            <div key={c.label}>
              <p className="text-xs text-slate-500 mb-1">{c.label}</p>
              <div className="bg-slate-900 text-green-400 rounded-lg px-4 py-2 font-mono text-sm">{c.cmd}</div>
            </div>
          ))}
        </div>
      </div>

      {/* FAQ */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h2 className="text-lg font-bold text-slate-900 mb-4">FAQ</h2>
        <div className="space-y-2">
          {[
            { q:'Why does the workflow say "approved" when I selected deny on the payer portal?',
              a:'The submission agent polls the FHIR server every 2 seconds for up to 2 minutes. If you take longer than 2 minutes to decide on the payer portal, it times out and defaults to denied. Make sure the payer portal is open before clicking a scenario.' },
            { q:'The appeal letter is generated but I don\'t see it on the payer portal.',
              a:'The appeal is submitted as a new Bundle to the FHIR server with an "X-Is-Appeal: true" header. It will appear in the payer queue as a separate entry with an "Appeal" badge. Check the payer portal queue for a second entry.' },
            { q:'Can I run the system without an OpenAI API key?',
              a:'Yes. Set DEMO_MODE=true in your .env file. The agents will use rule-based fallback logic instead of LLM calls. The clinical summary, policy matching, and appeal letter will be less sophisticated but the workflow will complete.' },
            { q:'Why are all pages showing 404?',
              a:'Make sure the backend is running on port 8000 and the Next.js rewrites in next.config.js point to http://localhost:8000/api/:path*. Also confirm the dynamic route folder is named [authId] (with square brackets), not ${params.authId}.' },
            { q:'How do I add a new demo scenario?',
              a:'Add a new patient to initialize_demo_data() in backend/main.py, add clinical notes under clinical_notes["patient-XXX"], and add the scenario mapping in the /api/demo/scenario endpoint. Then add a card to frontend/components/ScenarioSelector.tsx.' },
          ].map(f => <FAQ key={f.q} q={f.q} a={f.a} />)}
        </div>
      </div>

      {/* Links */}
      <div className="bg-slate-50 rounded-2xl border border-slate-200 p-5">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">External Resources</p>
        <div className="space-y-2">
          {[
            { label:'FHIR R4 Specification', url:'https://hl7.org/fhir/R4/' },
            { label:'OpenAI API Docs', url:'https://platform.openai.com/docs' },
            { label:'FastAPI Documentation', url:'https://fastapi.tiangolo.com' },
            { label:'Prior Authorization 101 (AMA)', url:'https://www.ama-assn.org/practice-management/prior-authorization' },
          ].map(l => (
            <a key={l.label} href={l.url} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 hover:underline">
              <ExternalLink className="w-3.5 h-3.5" />{l.label}
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
