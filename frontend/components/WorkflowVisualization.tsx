'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CheckCircle2, XCircle, ArrowRight, Sparkles, Brain, Shield,
  Send, Activity, FileText, Search, Copy, Check, ChevronDown, ChevronUp
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface Agent {
  name: string;
  status: 'idle'|'running'|'completed'|'failed'|'waiting';
  output_data?: Record<string, any>;
}

interface WorkflowState {
  auth_id: string;
  current_state: string;
  agents: Record<string, Agent>;
  processing_log: any[];
  submission_result?: any;
  appeal_letter?: string;
  appeal_submission_result?: any;
  denial_analysis?: any;
}

interface Props { authId: string | null; }

const STAGES = [
  { id: 'triage',              name: 'Triage',       icon: Activity,  color: 'pink',   agent: 'TriageAgent' },
  { id: 'evidence_extraction', name: 'Clinical',     icon: Brain,     color: 'purple', agent: 'ClinicalReaderAgent' },
  { id: 'policy_lookup',       name: 'Policy',       icon: Shield,    color: 'cyan',   agent: 'PolicyAgent' },
  { id: 'validation',          name: 'Validate',     icon: Search,    color: 'blue',   agent: 'ValidationAgent' },
  { id: 'submission',          name: 'Submit',       icon: Send,      color: 'green',  agent: 'SubmissionAgent' },
  { id: 'monitoring',          name: 'Decision',     icon: Activity,  color: 'yellow', agent: 'MonitoringAgent' },
  { id: 'appeal_generation',   name: 'Appeal',       icon: FileText,  color: 'amber',  agent: 'AppealAgent' },
  { id: 'appeal_submission',   name: 'Resubmit',     icon: Send,      color: 'orange', agent: 'AppealSubmissionAgent' },
];

const COLORS: Record<string,{border:string;text:string;bg:string}> = {
  pink:   {border:'border-pink-500',   text:'text-pink-600',   bg:'bg-pink-100'},
  purple: {border:'border-purple-500', text:'text-purple-600', bg:'bg-purple-100'},
  cyan:   {border:'border-cyan-500',   text:'text-cyan-600',   bg:'bg-cyan-100'},
  blue:   {border:'border-blue-500',   text:'text-blue-600',   bg:'bg-blue-100'},
  green:  {border:'border-green-500',  text:'text-green-600',  bg:'bg-green-100'},
  yellow: {border:'border-yellow-500', text:'text-yellow-600', bg:'bg-yellow-100'},
  amber:  {border:'border-amber-500',  text:'text-amber-600',  bg:'bg-amber-100'},
  orange: {border:'border-orange-500', text:'text-orange-600', bg:'bg-orange-100'},
  gray:   {border:'border-slate-200',  text:'text-slate-400',  bg:'bg-slate-100'},
};

const ORDER = [
  'pending','triage','evidence_extraction','policy_lookup','validation',
  'submission','monitoring','approved','denied',
  'appeal_analysis','appeal_generation','appeal_submission',
];

export function WorkflowVisualization({ authId }: Props) {
  const [ws, setWs]             = useState<WorkflowState|null>(null);
  const [polling, setPolling]   = useState(false);
  const [letterOpen, setLetterOpen] = useState(false);
  const [copied, setCopied]     = useState(false);
  const intervalRef             = useRef<NodeJS.Timeout|null>(null);

  useEffect(() => {
    if (!authId) return;
    setWs(null); setPolling(true);

    const poll = async () => {
      try {
        const res = await fetch(`/api/auth/${authId}/trace`);
        if (!res.ok) return;
        const data = await res.json();
        setWs(data);
        const cur = (data.current_state || '').toLowerCase();
        if (['approved','appeal_submission','requires_human_review'].includes(cur)) {
          setPolling(false);
          if (intervalRef.current) clearInterval(intervalRef.current);
        }
      } catch {}
    };

    poll();
    intervalRef.current = setInterval(poll, 1500);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [authId]);

  const cur = (ws?.current_state || '').toLowerCase();

  const stageStatus = (id: string) => {
    if (!ws) return 'pending' as const;
    const ci = ORDER.indexOf(cur);
    const si = ORDER.indexOf(id);
    if (cur === 'approved') { if (si <= ORDER.indexOf('monitoring')) return 'completed' as const; }
    if (cur === 'appeal_submission') { if (si <= ORDER.indexOf('appeal_submission')) return 'completed' as const; }
    if (si < ci) return 'completed' as const;
    if (si === ci) return 'active' as const;
    return 'pending' as const;
  };

  const copyLetter = () => {
    if (!ws?.appeal_letter) return;
    navigator.clipboard.writeText(ws.appeal_letter);
    setCopied(true); setTimeout(() => setCopied(false), 2000);
  };

  const isApproved      = cur === 'approved';
  const appealGenerated = !!(ws?.appeal_letter);
  const appealSubmitted = cur === 'appeal_submission' || !!(ws?.appeal_submission_result);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-white/10 rounded-lg"><Sparkles className="w-5 h-5 text-cyan-400" /></div>
          <div>
            <h2 className="text-white font-semibold">Live Agent Workflow</h2>
            <p className="text-slate-400 text-sm">Real-time processing visualization</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className={cn("w-3 h-3 rounded-full", polling ? "bg-green-500 animate-pulse" : "bg-gray-400")} />
          <span className="text-sm text-slate-400">
            {polling ? 'Processing...' : isApproved ? 'Approved ✓' : appealSubmitted ? 'Appeal Sent' : cur}
          </span>
        </div>
      </div>

      <div className="p-6 space-y-5">
        {/* Stage pipeline */}
        <div className="flex items-start overflow-x-auto pb-2">
          {STAGES.map((stage, idx) => {
            const status = stageStatus(stage.id);
            const col    = COLORS[status === 'active' ? stage.color : 'gray'];
            const agent  = ws?.agents?.[stage.agent];
            return (
              <div key={stage.id} className="flex items-center flex-shrink-0">
                <div className="flex flex-col items-center" style={{minWidth:80}}>
                  <motion.div
                    className={cn(
                      "relative w-12 h-12 rounded-xl border-2 flex items-center justify-center",
                      status==='completed' && "bg-green-50 border-green-500",
                      status==='active'    && `bg-white shadow-lg ${col.border}`,
                      status==='pending'   && "border-slate-200 bg-slate-50"
                    )}
                    animate={status==='active' ? {scale:[1,1.07,1]} : {}}
                    transition={{duration:2,repeat:Infinity}}
                  >
                    {status==='completed' && <CheckCircle2 className="w-5 h-5 text-green-500" />}
                    {status==='active' && (
                      <>
                        <stage.icon className={cn("w-5 h-5 relative z-10", col.text)} />
                        <motion.div className={cn("absolute inset-0 rounded-xl", col.bg)}
                          animate={{opacity:[0.2,0.6,0.2]}} transition={{duration:1.5,repeat:Infinity}} />
                      </>
                    )}
                    {status==='pending' && <stage.icon className="w-5 h-5 text-slate-300" />}
                  </motion.div>
                  <p className={cn("text-xs font-medium mt-1.5 text-center",
                    status==='active' ? 'text-slate-900' : 'text-slate-400')}>{stage.name}</p>
                  {agent && status==='active' && (
                    <motion.span initial={{opacity:0}} animate={{opacity:1}}
                      className="mt-1 text-xs px-1.5 py-0.5 bg-purple-50 text-purple-600 rounded-full font-medium">
                      {agent.status}
                    </motion.span>
                  )}
                </div>
                {idx < STAGES.length-1 && (
                  <ArrowRight className={cn("w-4 h-4 mx-0.5 flex-shrink-0 mt-[-14px]",
                    stageStatus(stage.id)==='completed' ? 'text-green-400' : 'text-slate-200')} />
                )}
              </div>
            );
          })}
        </div>

        {/* Agent cards */}
        {ws?.agents && Object.keys(ws.agents).length > 0 && (
          <div className="border-t border-slate-100 pt-4">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Agent Output</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {Object.values(ws.agents).map(a => <AgentCard key={a.name} agent={a} />)}
            </div>
          </div>
        )}

        {/* Results */}
        <AnimatePresence>
          {/* Approved */}
          {isApproved && (
            <motion.div initial={{opacity:0,y:8}} animate={{opacity:1,y:0}}
              className="p-4 bg-green-50 border border-green-200 rounded-xl flex items-center gap-3">
              <CheckCircle2 className="w-6 h-6 text-green-500 flex-shrink-0" />
              <div>
                <p className="font-semibold text-green-900">Authorization Approved!</p>
                <p className="text-sm text-green-700">
                  Ref: {ws?.submission_result?.external_auth_id || ws?.submission_result?.claim_response_id || 'See payer portal'}
                </p>
              </div>
            </motion.div>
          )}

          {/* Appeal letter */}
          {appealGenerated && (
            <motion.div initial={{opacity:0,y:8}} animate={{opacity:1,y:0}}
              className="border border-amber-200 rounded-xl overflow-hidden">

              {/* Top bar */}
              <div className="bg-amber-50 px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <FileText className="w-5 h-5 text-amber-600 flex-shrink-0" />
                  <p className="font-semibold text-amber-900 text-sm">Appeal Letter Generated</p>
                  {ws?.denial_analysis?.success_probability != null && (
                    <span className="flex-shrink-0 text-xs bg-amber-200 text-amber-800 px-2 py-0.5 rounded-full">
                      ~{Math.round((ws.denial_analysis.success_probability)*100)}% success
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button onClick={copyLetter}
                    className="flex items-center gap-1 text-xs px-2 py-1 bg-white border border-amber-300 text-amber-700 rounded-lg hover:bg-amber-50">
                    {copied ? <Check className="w-3 h-3"/> : <Copy className="w-3 h-3"/>}
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                  <button onClick={()=>setLetterOpen(v=>!v)}
                    className="flex items-center gap-1 text-xs px-2 py-1 bg-white border border-amber-300 text-amber-700 rounded-lg hover:bg-amber-50">
                    {letterOpen ? <ChevronUp className="w-3 h-3"/> : <ChevronDown className="w-3 h-3"/>}
                    {letterOpen ? 'Collapse' : 'Read Full'}
                  </button>
                </div>
              </div>

              {/* Letter preview / full */}
              <div className="bg-white px-4 py-3">
                <pre className="text-xs text-slate-600 whitespace-pre-wrap font-mono leading-relaxed"
                  style={{maxHeight: letterOpen ? '500px' : '80px', overflow:'hidden',
                          transition:'max-height 0.3s ease'}}>
                  {ws.appeal_letter}
                </pre>
                {!letterOpen && ws.appeal_letter && ws.appeal_letter.length > 200 && (
                  <p className="text-xs text-amber-600 mt-1">… click "Read Full" to see complete letter</p>
                )}
              </div>

              {/* Appeal submission status */}
              {appealSubmitted && ws.appeal_submission_result && (
                <div className="px-4 py-3 bg-blue-50 border-t border-amber-200 flex items-center gap-3">
                  <Send className="w-4 h-4 text-blue-600 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-semibold text-blue-800">Appeal submitted to payer for review</p>
                    {ws.appeal_submission_result.claim_response_id && (
                      <p className="text-xs text-blue-600 mt-0.5">
                        Payer Claim ID: <span className="font-mono">{ws.appeal_submission_result.claim_response_id}</span>
                        <span className="ml-2 text-blue-500">→ Check Payer Portal at localhost:3001</span>
                      </p>
                    )}
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function AgentCard({ agent }: { agent: Agent }) {
  const colors: Record<string,string> = {
    idle:'bg-gray-100 text-gray-600', running:'bg-blue-100 text-blue-600',
    completed:'bg-green-100 text-green-600', failed:'bg-red-100 text-red-600',
    waiting:'bg-yellow-100 text-yellow-600',
  };
  return (
    <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs font-semibold text-slate-700 truncate">
          {agent.name.replace('Agent','').replace('Submission','Submit')}
        </p>
        <span className={cn("text-xs px-1.5 py-0.5 rounded-full font-medium capitalize",
          colors[agent.status] || colors.idle)}>{agent.status}</span>
      </div>
      {agent.output_data && Object.entries(agent.output_data).slice(0,2).map(([k,v]) => (
        <div key={k} className="flex justify-between text-xs mt-0.5">
          <span className="text-slate-400 truncate capitalize">{k.replace(/_/g,' ')}</span>
          <span className="text-slate-600 font-medium ml-1">
            {typeof v==='boolean'?(v?'Yes':'No'):String(v).substring(0,15)}
          </span>
        </div>
      ))}
    </div>
  );
}
