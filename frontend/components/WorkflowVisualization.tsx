'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CheckCircle2, XCircle, ArrowRight, Sparkles, Brain, Shield,
  Send, Activity, FileText, Search, Copy, Check,
  ChevronDown, ChevronUp, TrendingUp, AlertTriangle, Zap, BarChart2
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface Agent {
  name: string;
  status: 'idle'|'running'|'completed'|'failed'|'waiting';
  output_data?: Record<string, any>;
}

interface Prediction {
  approval_probability: number;
  risk_level: 'low'|'medium'|'high';
  strategy: string;
  reasoning: string;
  policy_match_score: number;
  necessity_score: number;
  missing_criteria: number;
  satisfied_criteria: number;
  payer: string;
}

interface WorkflowState {
  auth_id: string;
  current_state: string;
  agents: Record<string, Agent>;
  processing_log: any[];
  submission_result?: any;
  appeal_letter?: string;
  appeal_submission_result?: any;
  appeal_decision?: { outcome: string; decided_at?: string; reviewer?: string };
  denial_analysis?: any;
  prediction?: Prediction;
}

interface Props { authId: string | null; }

const STAGES = [
  { id:'triage',             name:'Triage',      icon:Activity,  color:'pink',   agent:'TriageAgent' },
  { id:'evidence_extraction',name:'Clinical',    icon:Brain,     color:'purple', agent:'ClinicalReaderAgent' },
  { id:'policy_lookup',      name:'Policy',      icon:Shield,    color:'cyan',   agent:'PolicyAgent' },
  { id:'validation',         name:'Validate',    icon:Search,    color:'blue',   agent:'ValidationAgent' },
  { id:'prediction',         name:'Predict',     icon:BarChart2, color:'violet', agent:'PredictionAgent' },
  { id:'decision_engine',    name:'Strategy',    icon:Zap,       color:'indigo', agent:'DecisionEngine' },
  { id:'preemptive_appeal',  name:'Pre-Appeal',  icon:FileText,  color:'amber',  agent:'AppealAgent' },
  { id:'submission',         name:'Submit',      icon:Send,      color:'green',  agent:'SubmissionAgent' },
  { id:'monitoring',         name:'Decision',    icon:Activity,  color:'yellow', agent:'MonitoringAgent' },
  { id:'appeal_generation',  name:'Appeal',      icon:FileText,  color:'amber',  agent:'AppealAgent' },
  { id:'appeal_submission',  name:'Resubmit',    icon:Send,      color:'orange', agent:'AppealSubmissionAgent' },
  { id:'appeal_monitoring',  name:'Appeal Wait', icon:Activity,  color:'rose',   agent:'AppealMonitoringAgent' },
];

// Only show stages that have been reached or are upcoming in current path
const STANDARD_PATH  = ['triage','evidence_extraction','policy_lookup','validation','prediction','decision_engine','submission','monitoring'];
const PREEMPTIVE_PATH= ['triage','evidence_extraction','policy_lookup','validation','prediction','decision_engine','preemptive_appeal','submission','monitoring'];
const APPEAL_PATH    = ['appeal_generation','appeal_submission','appeal_monitoring'];

const COLORS: Record<string,{border:string;text:string;bg:string}> = {
  pink:   {border:'border-pink-500',   text:'text-pink-600',   bg:'bg-pink-100'},
  purple: {border:'border-purple-500', text:'text-purple-600', bg:'bg-purple-100'},
  cyan:   {border:'border-cyan-500',   text:'text-cyan-600',   bg:'bg-cyan-100'},
  blue:   {border:'border-blue-500',   text:'text-blue-600',   bg:'bg-blue-100'},
  violet: {border:'border-violet-500', text:'text-violet-600', bg:'bg-violet-100'},
  indigo: {border:'border-indigo-500', text:'text-indigo-600', bg:'bg-indigo-100'},
  green:  {border:'border-green-500',  text:'text-green-600',  bg:'bg-green-100'},
  yellow: {border:'border-yellow-500', text:'text-yellow-600', bg:'bg-yellow-100'},
  amber:  {border:'border-amber-500',  text:'text-amber-600',  bg:'bg-amber-100'},
  orange: {border:'border-orange-500', text:'text-orange-600', bg:'bg-orange-100'},
  rose:   {border:'border-rose-500',   text:'text-rose-600',   bg:'bg-rose-100'},
  gray:   {border:'border-slate-200',  text:'text-slate-400',  bg:'bg-slate-100'},
};

const ORDER = [
  'pending','triage','evidence_extraction','policy_lookup','validation',
  'prediction','decision_engine','preemptive_appeal',
  'submission','monitoring','approved','denied',
  'appeal_analysis','appeal_generation','appeal_submission','appeal_monitoring',
  'appeal_approved','appeal_denied',
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
        const cur = (data.current_state||'').toLowerCase();
        const terminal = ['approved','appeal_approved','appeal_denied','appeal_submission','requires_human_review'];
        if (terminal.includes(cur)) {
          setPolling(false);
          if (intervalRef.current) clearInterval(intervalRef.current);
        }
      } catch {}
    };

    poll();
    intervalRef.current = setInterval(poll, 1500);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [authId]);

  const cur = (ws?.current_state||'').toLowerCase();

  // Determine which stages to display
  const hasPreemptive = !!(ws?.agents?.['AppealAgent'] && ORDER.indexOf(cur) <= ORDER.indexOf('decision_engine') + 2);
  const inAppalPath   = ORDER.indexOf(cur) >= ORDER.indexOf('appeal_analysis');
  const strategy      = ws?.prediction?.strategy || 'direct_submit';

  let visibleStageIds: string[] = [];
  if (strategy === 'preemptive_appeal' || ws?.agents?.['AppealAgent']?.output_data?.type === 'preemptive') {
    visibleStageIds = [...PREEMPTIVE_PATH];
  } else {
    visibleStageIds = [...STANDARD_PATH];
  }
  if (inAppalPath) {
    visibleStageIds = [...visibleStageIds, ...APPEAL_PATH];
  }
  // Deduplicate while keeping order
  const seen = new Set<string>();
  const displayStages = visibleStageIds
    .filter(id => { if (seen.has(id)) return false; seen.add(id); return true; })
    .map(id => STAGES.find(s => s.id === id)!)
    .filter(Boolean);

  const stageStatus = (id: string): 'pending'|'active'|'completed' => {
    if (!ws) return 'pending';
    const ci = ORDER.indexOf(cur);
    const si = ORDER.indexOf(id);
    if (cur === 'approved' || cur === 'appeal_approved') {
      if (si <= ORDER.indexOf('monitoring')) return 'completed';
    }
    if (cur === 'appeal_submission' || cur === 'appeal_approved' || cur === 'appeal_denied') {
      if (si <= ORDER.indexOf('appeal_submission')) return 'completed';
    }
    if (si < ci) return 'completed';
    if (si === ci) return 'active';
    return 'pending';
  };

  const copyLetter = () => {
    if (!ws?.appeal_letter) return;
    navigator.clipboard.writeText(ws.appeal_letter);
    setCopied(true); setTimeout(() => setCopied(false), 2000);
  };

  const isApproved       = cur === 'approved';
  const isAppealApproved = cur === 'appeal_approved';
  const isAppealDenied   = cur === 'appeal_denied';
  const appealGenerated  = !!(ws?.appeal_letter);
  const appealSubmitted  = ['appeal_submission','appeal_monitoring','appeal_approved','appeal_denied'].includes(cur);
  const pred             = ws?.prediction;
  const isTerminal = ['approved','denied','appeal_approved','appeal_denied','appeal_submission'].includes(cur);
  const showFullPrediction = pred && !isTerminal;

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-lg">
      {/* Header */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-white/10 rounded-lg"><Sparkles className="w-5 h-5 text-cyan-400"/></div>
          <div>
            <h2 className="text-white font-semibold">Live Agent Workflow</h2>
            <p className="text-slate-400 text-sm">Real-time processing visualization</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className={cn("w-3 h-3 rounded-full", polling?"bg-green-500 animate-pulse":"bg-gray-400")}/>
          <span className="text-sm text-slate-400">
            {polling ? 'Processing...'
             : isApproved ? '✓ Approved'
             : isAppealApproved ? '✓ Appeal Approved'
             : isAppealDenied ? '✗ Appeal Denied'
             : appealSubmitted ? 'Appeal Sent'
             : cur || 'Idle'}
          </span>
        </div>
      </div>

      <div className="p-6 space-y-5">
        {/* Stage pipeline */}
        <div className="overflow-x-auto pb-2 pt-2">
          <div className="flex items-start min-w-max">
            {displayStages.map((stage, idx) => {
              const status = stageStatus(stage.id);
              const col    = COLORS[status === 'active' ? stage.color : 'gray'];
              const agent  = ws?.agents?.[stage.agent];

              return (
                <div key={stage.id} className="flex items-center flex-shrink-0">
                  <div className="flex flex-col items-center" style={{minWidth:76}}>
                    <motion.div
                      className={cn(
                        "relative w-11 h-11 rounded-xl border-2 flex items-center justify-center transition-all duration-500",
                        status==='completed' && "bg-green-50 border-green-500",
                        status==='active'    && `bg-white shadow-lg ${col.border}`,
                        status==='pending'   && "border-slate-200 bg-slate-50"
                      )}
                      animate={status==='active'?{scale:[1,1.04,1]}:{}}
                      transition={{duration:2,repeat:Infinity}}
                    >
                      {status==='completed' && <CheckCircle2 className="w-5 h-5 text-green-500"/>}
                      {status==='active' && (
                        <>
                          <stage.icon className={cn("w-4 h-4 relative z-10",col.text)}/>
                          <motion.div className={cn("absolute inset-0 rounded-xl",col.bg)}
                            animate={{opacity:[0.2,0.6,0.2]}} transition={{duration:1.5,repeat:Infinity}}/>
                        </>
                      )}
                      {status==='pending' && <stage.icon className="w-4 h-4 text-slate-300"/>}
                    </motion.div>
                    <p className={cn("text-xs font-medium mt-1 text-center leading-tight px-1",
                      status==='active'?'text-slate-900':'text-slate-400')} style={{maxWidth:72}}>
                      {stage.name}
                    </p>
                    {agent && status==='active' && (
                      <motion.span initial={{opacity:0}} animate={{opacity:1}}
                        className="mt-1 text-xs px-1.5 py-0.5 bg-purple-50 text-purple-600 rounded-full">
                        {agent.status}
                      </motion.span>
                    )}
                  </div>
                  {idx < displayStages.length-1 && (
                    <ArrowRight className={cn("w-3.5 h-3.5 mx-0.5 flex-shrink-0 mt-[-16px]",
                      stageStatus(stage.id)==='completed'?'text-green-400':'text-slate-200')}/>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* 🔮 Prediction Panel */}
        <AnimatePresence>
          {showFullPrediction && (
            <motion.div initial={{opacity:0,y:6}} animate={{opacity:1,y:0}}
              className={cn("rounded-xl border p-4",
                pred.risk_level==='low'    ? "bg-green-50 border-green-200"  :
                pred.risk_level==='medium' ? "bg-yellow-50 border-yellow-200":
                                             "bg-red-50 border-red-200")}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <BarChart2 className={cn("w-4 h-4",
                    pred.risk_level==='low'?'text-green-600':pred.risk_level==='medium'?'text-yellow-600':'text-red-600')}/>
                  <p className="font-semibold text-slate-800 text-sm">Prediction Engine</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className={cn("text-lg font-bold",
                    pred.risk_level==='low'?'text-green-700':pred.risk_level==='medium'?'text-yellow-700':'text-red-700')}>
                    {Math.round(pred.approval_probability*100)}%
                  </span>
                  <span className="text-xs text-slate-500">approval probability</span>
                </div>
              </div>

              {/* Probability bar */}
              <div className="w-full bg-slate-200 rounded-full h-2 mb-3">
                <motion.div
                  className={cn("h-2 rounded-full",
                    pred.risk_level==='low'?'bg-green-500':pred.risk_level==='medium'?'bg-yellow-500':'bg-red-500')}
                  initial={{width:0}}
                  animate={{width:`${pred.approval_probability*100}%`}}
                  transition={{duration:0.8, ease:"easeOut"}}
                />
              </div>

              <p className="text-xs text-slate-600 mb-3 leading-relaxed">{pred.reasoning}</p>

              <div className="grid grid-cols-3 gap-2 mb-2">
                {[
                  { label:'Policy Match', value:`${Math.round(pred.policy_match_score*100)}%` },
                  { label:'Necessity',    value:`${Math.round(pred.necessity_score*100)}%` },
                  { label:'Missing',      value:`${pred.missing_criteria} criteria` },
                ].map(m=>(
                  <div key={m.label} className="bg-white/70 rounded-lg px-2 py-1.5 text-center">
                    <p className="text-xs text-slate-500">{m.label}</p>
                    <p className="text-sm font-bold text-slate-800">{m.value}</p>
                  </div>
                ))}
              </div>

              <div className={cn("flex items-center gap-1.5 text-xs font-semibold rounded-lg px-3 py-2",
                pred.strategy==='direct_submit'          ? 'bg-green-100 text-green-800' :
                pred.strategy==='submit_with_justification'?'bg-yellow-100 text-yellow-800':
                                                            'bg-red-100 text-red-800')}>
                <Zap className="w-3.5 h-3.5"/>
                Strategy: {
                  pred.strategy==='direct_submit'            ? '✓ Direct Submit — high confidence' :
                  pred.strategy==='submit_with_justification'? '⚡ Submit with Enhanced Justification' :
                                                               '🛡 Preemptive Appeal — generated before submission'
                }
              </div>
            </motion.div>
          )}
        </AnimatePresence>


        {/* Compact prediction badge — shown once terminal */}
        {pred && isTerminal && (
          <div className={cn("flex items-center gap-3 rounded-xl px-4 py-2.5 border text-sm",
            pred.risk_level==='low'    ? "bg-green-50 border-green-200 text-green-800" :
            pred.risk_level==='medium' ? "bg-yellow-50 border-yellow-200 text-yellow-800" :
                                         "bg-red-50 border-red-200 text-red-800")}>
            <BarChart2 className="w-4 h-4 flex-shrink-0"/>
            <span className="font-semibold">{Math.round(pred.approval_probability*100)}% predicted approval</span>
            <span className="text-xs opacity-60 ml-1">· {pred.strategy.replace(/_/g,' ')}</span>
          </div>
        )}
        {/* Agent output cards */}
        {ws?.agents && Object.keys(ws.agents).length > 0 && (
          <div className="border-t border-slate-100 pt-3">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Agent Output</p>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
              {Object.values(ws.agents).map(a => <AgentCard key={a.name} agent={a}/>)}
            </div>
          </div>
        )}

        {/* Result banners */}
        <AnimatePresence>
          {(isApproved || isAppealApproved) && (
            <motion.div initial={{opacity:0,y:8}} animate={{opacity:1,y:0}}
              className="p-4 bg-green-50 border border-green-200 rounded-xl flex items-center gap-3">
              <CheckCircle2 className="w-6 h-6 text-green-500 flex-shrink-0"/>
              <div>
                <p className="font-semibold text-green-900">
                  {isAppealApproved ? 'Appeal Approved! 🎉' : 'Authorization Approved!'}
                </p>
                <p className="text-sm text-green-700">
                  Ref: {ws?.submission_result?.external_auth_id || ws?.submission_result?.claim_response_id || 'See payer portal'}
                </p>
                {isAppealApproved && ws?.appeal_decision?.reviewer && (
                  <p className="text-xs text-green-600 mt-0.5">Reviewed by: {ws.appeal_decision.reviewer}</p>
                )}
              </div>
            </motion.div>
          )}

          {isAppealDenied && (
            <motion.div initial={{opacity:0,y:8}} animate={{opacity:1,y:0}}
              className="p-4 bg-red-50 border border-red-200 rounded-xl flex items-center gap-3">
              <XCircle className="w-6 h-6 text-red-500 flex-shrink-0"/>
              <div>
                <p className="font-semibold text-red-900">Appeal Denied</p>
                <p className="text-sm text-red-700">Please contact the payer for manual peer-to-peer review.</p>
              </div>
            </motion.div>
          )}

          {/* Appeal letter panel */}
          {appealGenerated && !isApproved && !isAppealApproved && (
            <motion.div initial={{opacity:0,y:8}} animate={{opacity:1,y:0}}
              className="border border-amber-200 rounded-xl">

              {/* Header bar */}
              <div className="bg-amber-50 px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-2 flex-wrap">
                  <FileText className="w-4 h-4 text-amber-600"/>
                  <p className="font-semibold text-amber-900 text-sm">
                    {ws?.agents?.['AppealAgent']?.output_data?.type === 'preemptive'
                      ? '🛡 Preemptive Appeal Letter'
                      : '📄 Appeal Letter Generated'}
                  </p>
                  {ws?.denial_analysis?.success_probability != null && (
                    <span className="text-xs bg-amber-200 text-amber-800 px-2 py-0.5 rounded-full font-medium">
                      ~{Math.round(ws.denial_analysis.success_probability * 100)}% success est.
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button onClick={copyLetter}
                    className="flex items-center gap-1 text-xs px-2 py-1 bg-white border border-amber-300 text-amber-700 rounded-lg hover:bg-amber-50 transition-colors">
                    {copied ? <Check className="w-3 h-3"/> : <Copy className="w-3 h-3"/>}
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                  <button onClick={() => setLetterOpen(v=>!v)}
                    className="flex items-center gap-1 text-xs px-2 py-1 bg-white border border-amber-300 text-amber-700 rounded-lg hover:bg-amber-50 transition-colors">
                    {letterOpen ? <ChevronUp className="w-3 h-3"/> : <ChevronDown className="w-3 h-3"/>}
                    {letterOpen ? 'Collapse' : 'Read Full'}
                  </button>
                </div>
              </div>

              {/* Letter body — scrollable when open */}
              <div className="bg-white">
                {!letterOpen ? (
                  <div className="px-4 py-3">
                    <pre className="text-xs text-slate-600 whitespace-pre-wrap font-mono leading-relaxed line-clamp-3 overflow-hidden">
                      {ws.appeal_letter!.substring(0, 300)}
                    </pre>
                    <p className="text-xs text-amber-600 mt-1 cursor-pointer hover:underline"
                       onClick={() => setLetterOpen(true)}>
                      → Click "Read Full" to read the complete letter
                    </p>
                  </div>
                ) : (
                  <div className="px-4 py-3" style={{maxHeight:'480px', overflowY:'auto'}}>
                    <pre className="text-xs text-slate-700 whitespace-pre-wrap font-mono leading-relaxed">
                      {ws.appeal_letter}
                    </pre>
                  </div>
                )}
              </div>

              {/* Submission status */}
              {appealSubmitted && ws.appeal_submission_result && (
                <div className="px-4 py-3 bg-blue-50 border-t border-amber-200 flex items-center gap-3">
                  <Send className="w-4 h-4 text-blue-600 flex-shrink-0"/>
                  <div>
                    <p className="text-sm font-semibold text-blue-800">Appeal submitted to payer for review</p>
                    {ws.appeal_submission_result.claim_response_id && (
                      <p className="text-xs text-blue-600 mt-0.5">
                        Payer Claim ID: <span className="font-mono font-bold">{ws.appeal_submission_result.claim_response_id}</span>
                        <span className="ml-2 text-blue-400">→ Review on Payer Portal (localhost:3001)</span>
                      </p>
                    )}
                    {ws.appeal_submission_result.message && (
                      <p className="text-xs text-blue-500 mt-0.5">{ws.appeal_submission_result.message}</p>
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
  const shortName = agent.name
    .replace('Agent','').replace('Submission','Submit')
    .replace('Monitoring','Monitor').replace('Prediction','Predict');
  return (
    <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs font-semibold text-slate-700 truncate">{shortName}</p>
        <span className={cn("text-xs px-1.5 py-0.5 rounded-full font-medium capitalize flex-shrink-0",
          colors[agent.status]||colors.idle)}>{agent.status}</span>
      </div>
      {agent.output_data && Object.entries(agent.output_data).slice(0,2).map(([k,v])=>(
        <div key={k} className="flex justify-between text-xs mt-0.5">
          <span className="text-slate-400 truncate capitalize">{k.replace(/_/g,' ')}</span>
          <span className="text-slate-600 font-medium ml-1 truncate max-w-[80px]">
            {typeof v==='boolean'?(v?'Yes':'No'):String(v).substring(0,18)}
          </span>
        </div>
      ))}
    </div>
  );
}