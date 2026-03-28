'use client';
import { createPortal } from 'react-dom';
import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, CheckCircle2, XCircle, FileText, RefreshCw, ChevronRight, AlertCircle, Activity } from 'lucide-react';
import { ReviewModal } from '@/components/ReviewModal';

const FHIR_BASE = '/payer-api';

interface QueueItem {
  claim_id: string; status: string; received_at: string; decided_at: string|null;
  is_appeal: boolean; has_appeal_letter: boolean;
  patient_name: string; patient_dob: string;
  cpt_code: string; cpt_description: string; payer_name: string;
  diagnoses: {code:string;display:string}[];
  conditions_count: number; medications_count: number;
}

interface Stats { total: number; pending: number; approved: number; denied: number; appeals: number; }

const statusBadge = (s: string) => ({
  pending:      'bg-yellow-100 text-yellow-800',
  under_review: 'bg-blue-100 text-blue-800',
  approved:     'bg-green-100 text-green-800',
  denied:       'bg-red-100 text-red-800',
}[s] ?? 'bg-slate-100 text-slate-700');

const statusIcon = (s: string) => {
  if (s==='approved')     return <CheckCircle2 className="w-4 h-4 text-green-500"/>;
  if (s==='denied')       return <XCircle className="w-4 h-4 text-red-500"/>;
  if (s==='under_review') return <Activity className="w-4 h-4 text-blue-500"/>;
  return <Clock className="w-4 h-4 text-yellow-500"/>;
};

const elapsed = (iso: string) => {
  const m = Math.floor((Date.now()-new Date(iso).getTime())/60000);
  if (m<1) return 'just now'; if (m<60) return `${m}m ago`;
  return `${Math.floor(m/60)}h ago`;
};

export default function PayerDashboard() {
  const [queue, setQueue]       = useState<QueueItem[]>([]);
  const [stats, setStats]       = useState<Stats>({total:0,pending:0,approved:0,denied:0,appeals:0});
  const [filter, setFilter]     = useState('all');
  const [selected, setSelected] = useState<QueueItem|null>(null);
  const [loading, setLoading]   = useState(true);
  const [lastRefresh, setLastRefresh] = useState(new Date());

  const fetchData = useCallback(async () => {
    try {
      const [qR, sR] = await Promise.all([
        fetch(`${FHIR_BASE}/payer/queue`),
        fetch(`${FHIR_BASE}/payer/stats`),
      ]);
      const qD = await qR.json(); const sD = await sR.json();
      setQueue(qD.queue||[]); setStats(sD);
      setLastRefresh(new Date());
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); const t=setInterval(fetchData,3000); return ()=>clearInterval(t); },[fetchData]);

  const filtered = queue.filter(item => {
    if (filter==='all') return true;
    if (filter==='appeals') return item.is_appeal;
    if (filter==='pending') return item.status==='pending'||item.status==='under_review';
    return item.status===filter;
  });

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { label:'Total',    value:stats.total,    color:'bg-slate-800',   icon:<FileText className="w-5 h-5 text-white"/> },
          { label:'Pending',  value:stats.pending,  color:'bg-yellow-500',  icon:<Clock className="w-5 h-5 text-white"/> },
          { label:'Approved', value:stats.approved, color:'bg-emerald-500', icon:<CheckCircle2 className="w-5 h-5 text-white"/> },
          { label:'Denied',   value:stats.denied,   color:'bg-red-500',     icon:<XCircle className="w-5 h-5 text-white"/> },
          { label:'Appeals',  value:stats.appeals,  color:'bg-amber-500',   icon:<FileText className="w-5 h-5 text-white"/> },
        ].map(s=>(
          <div key={s.label} className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-3">
            <div className={`w-9 h-9 rounded-lg ${s.color} flex items-center justify-center flex-shrink-0`}>{s.icon}</div>
            <div><p className="text-xl font-bold text-slate-900">{s.value}</p><p className="text-xs text-slate-500">{s.label}</p></div>
          </div>
        ))}
      </div>

      {/* Queue */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Authorization Queue</h2>
            <p className="text-xs text-slate-500 mt-0.5">Refreshed {elapsed(lastRefresh.toISOString())}</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex bg-slate-100 rounded-lg p-1 gap-1">
              {['all','pending','approved','denied','appeals'].map(f=>(
                <button key={f} onClick={()=>setFilter(f)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium capitalize transition-colors ${
                    filter===f?'bg-white text-slate-900 shadow-sm':'text-slate-500 hover:text-slate-700'}`}>
                  {f}
                </button>
              ))}
            </div>
            <button onClick={fetchData} className="p-2 rounded-lg hover:bg-slate-100"><RefreshCw className="w-4 h-4 text-slate-500"/></button>
          </div>
        </div>

        {loading ? (
          <div className="p-12 text-center text-slate-400"><RefreshCw className="w-8 h-8 animate-spin mx-auto mb-2"/><p className="text-sm">Loading...</p></div>
        ) : filtered.length===0 ? (
          <div className="p-12 text-center">
            <AlertCircle className="w-12 h-12 text-slate-300 mx-auto mb-3"/>
            <p className="text-slate-500 font-medium">No requests in queue</p>
            <p className="text-sm text-slate-400 mt-1">Waiting for provider submissions...</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            <AnimatePresence>
              {filtered.map((item,i)=>(
                <motion.button key={item.claim_id}
                  initial={{opacity:0,y:6}} animate={{opacity:1,y:0}} transition={{delay:i*0.04}}
                  onClick={()=>setSelected(item)}
                  className="w-full px-6 py-4 flex items-center gap-4 hover:bg-slate-50 transition-colors text-left group">
                  <div className="flex-shrink-0">{statusIcon(item.status)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-semibold text-slate-900">{item.patient_name}</p>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${statusBadge(item.status)}`}>
                        {item.status.replace('_',' ')}
                      </span>
                      {item.is_appeal && (
                        <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-amber-200 text-amber-800">⚡ APPEAL</span>
                      )}
                      {item.has_appeal_letter && !item.is_appeal && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">Letter attached</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono">{item.cpt_code}</span>
                      <span className="text-xs text-slate-500 truncate">{item.cpt_description}</span>
                      {item.payer_name && <span className="text-xs text-slate-400">· {item.payer_name}</span>}
                    </div>
                    {item.diagnoses.length>0 && (
                      <p className="text-xs text-slate-400 mt-0.5 truncate">
                        {item.diagnoses.slice(0,2).map(d=>d.display||d.code).join(' · ')}
                      </p>
                    )}
                  </div>
                  <div className="flex-shrink-0 text-right">
                    <p className="text-xs text-slate-400">{elapsed(item.received_at)}</p>
                    {item.decided_at && <p className="text-xs text-slate-400">Decided {elapsed(item.decided_at)}</p>}
                    {(item.status==='pending'||item.status==='under_review') && (
                      <p className="text-xs font-semibold text-yellow-600 mt-1">
                        {item.is_appeal ? '⚡ Appeal needs review' : 'Needs Review'}
                      </p>
                    )}
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-500 flex-shrink-0"/>
                </motion.button>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>

      {typeof window !== 'undefined' && createPortal(
        <AnimatePresence>
          {selected && <ReviewModal item={selected} onClose={()=>setSelected(null)} onDecision={()=>{setSelected(null);fetchData();}}/>}
        </AnimatePresence>
      , document.body)}
    </div>
  );
}