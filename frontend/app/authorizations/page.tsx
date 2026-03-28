'use client';
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FileCheck, Clock, CheckCircle2, XCircle, Filter, X, ChevronRight, FileText, Send } from 'lucide-react';
import { cn, getStatusColor } from '@/lib/utils';

interface Auth {
  id: string; status: string; service_type: string; cpt_code: string; icd10_code: string;
  priority: string; created_at: string; updated_at: string;
  patient: {first_name:string;last_name:string;payer_name:string;insurance_id:string} | null;
  workflow_result?: {
    appeal_letter?: string;
    denial_analysis?: {denial_reason?:string};
    submission_result?: {external_auth_id?:string;claim_response_id?:string};
    appeal_submission_result?: {claim_response_id?:string};
  };
}

function clean(s: string) { return (s||'').split('.').pop()?.toLowerCase() || 'pending'; }

function statusIcon(s: string) {
  const cs = clean(s);
  if (cs==='approved') return <CheckCircle2 className="w-4 h-4 text-green-500"/>;
  if (cs==='denied')   return <XCircle className="w-4 h-4 text-red-500"/>;
  if (cs.includes('appeal')) return <FileText className="w-4 h-4 text-amber-500"/>;
  return <Clock className="w-4 h-4 text-yellow-500"/>;
}

export default function AuthorizationsPage() {
  const [auths, setAuths]     = useState<Auth[]>([]);
  const [filter, setFilter]   = useState('all');
  const [selected, setSelected] = useState<Auth|null>(null);
  const [loading, setLoading] = useState(true);
  const [letterOpen, setLetterOpen] = useState(false);

  const fetchAuths = () => {
    fetch('/api/auth').then(r=>r.json()).then(d=>{
      setAuths((d.authorizations||[]).reverse());
      setLoading(false);
    });
  };

  useEffect(() => {
    fetchAuths();
    const t = setInterval(fetchAuths, 4000);
    return () => clearInterval(t);
  }, []);

  const filtered = auths.filter(a => {
    if (filter==='all') return true;
    return clean(a.status) === filter || (filter==='appeal' && clean(a.status).includes('appeal'));
  });

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Authorizations</h1>
        <p className="text-sm text-slate-500 mt-1">Track all prior authorization requests and their outcomes</p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2">
        <Filter className="w-4 h-4 text-slate-400"/>
        {['all','pending','approved','denied','appeal'].map(f => (
          <button key={f} onClick={()=>setFilter(f)}
            className={cn("px-3 py-1.5 rounded-lg text-sm font-medium capitalize transition-colors",
              filter===f ? 'bg-blue-600 text-white' : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50')}>
            {f}
          </button>
        ))}
        <span className="ml-auto text-sm text-slate-500">{filtered.length} requests</span>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-slate-400">Loading authorizations...</div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center">
            <FileCheck className="w-12 h-12 text-slate-300 mx-auto mb-3"/>
            <p className="text-slate-500">No authorizations match this filter</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {filtered.map((a,i)=>(
              <motion.button key={a.id} initial={{opacity:0}} animate={{opacity:1}} transition={{delay:i*0.03}}
                onClick={()=>{setSelected(a);setLetterOpen(false);}}
                className="w-full px-6 py-4 flex items-center gap-4 hover:bg-slate-50 transition-colors text-left group">
                <div className="flex-shrink-0">{statusIcon(a.status)}</div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-900">
                    {a.patient ? `${a.patient.first_name} ${a.patient.last_name}` : a.id}
                  </p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs font-mono bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">{a.cpt_code}</span>
                    <span className="text-xs text-slate-500 capitalize">{(a.service_type||'').replace(/_/g,' ')}</span>
                    <span className="text-xs text-slate-400">· ICD {a.icd10_code}</span>
                    {a.priority === 'urgent' && <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded-full">Urgent</span>}
                  </div>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <div className="text-right">
                    <span className={cn("text-xs px-2 py-1 rounded-full font-medium capitalize", getStatusColor(clean(a.status)))}>
                      {clean(a.status).replace(/_/g,' ')}
                    </span>
                    <p className="text-xs text-slate-400 mt-1">{new Date(a.created_at).toLocaleDateString()}</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-500"/>
                </div>
              </motion.button>
            ))}
          </div>
        )}
      </div>

      {/* Detail modal */}
      <AnimatePresence>
        {selected && (
          <motion.div initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}
            className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
            onClick={e=>{if(e.target===e.currentTarget)setSelected(null);}}>
            <motion.div initial={{scale:0.95}} animate={{scale:1}} exit={{scale:0.95}}
              className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden">
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">Authorization Detail</h2>
                  <p className="text-xs text-slate-500 font-mono">{selected.id}</p>
                </div>
                <button onClick={()=>setSelected(null)} className="p-2 hover:bg-slate-200 rounded-lg">
                  <X className="w-5 h-5 text-slate-500"/>
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {/* Status + patient */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
                    <p className="text-xs text-slate-500 mb-1">Status</p>
                    <span className={cn("text-sm px-2 py-1 rounded-full font-semibold capitalize", getStatusColor(clean(selected.status)))}>
                      {clean(selected.status).replace(/_/g,' ')}
                    </span>
                  </div>
                  <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
                    <p className="text-xs text-slate-500 mb-1">Patient</p>
                    <p className="font-semibold text-slate-900 text-sm">
                      {selected.patient ? `${selected.patient.first_name} ${selected.patient.last_name}` : '—'}
                    </p>
                    {selected.patient && <p className="text-xs text-slate-500">{selected.patient.payer_name}</p>}
                  </div>
                </div>

                {/* Service */}
                <div className="bg-blue-50 rounded-xl p-4 border border-blue-200">
                  <p className="text-xs text-blue-600 font-semibold mb-1">Requested Service</p>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-blue-800 bg-blue-100 px-2 py-1 rounded">CPT {selected.cpt_code}</span>
                    <span className="text-sm text-blue-700 capitalize">{(selected.service_type||'').replace(/_/g,' ')}</span>
                    <span className="text-xs text-blue-500">ICD-10: {selected.icd10_code}</span>
                  </div>
                </div>

                {/* Submission result */}
                {selected.workflow_result?.submission_result && (
                  <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
                    <p className="text-xs text-slate-500 font-semibold mb-1 flex items-center gap-1.5">
                      <Send className="w-3.5 h-3.5"/> Payer Reference
                    </p>
                    <p className="text-sm font-mono text-slate-700">
                      {selected.workflow_result.submission_result.external_auth_id ||
                       selected.workflow_result.submission_result.claim_response_id || '—'}
                    </p>
                  </div>
                )}

                {/* Denial reason */}
                {selected.workflow_result?.denial_analysis?.denial_reason && (
                  <div className="bg-red-50 rounded-xl p-4 border border-red-200">
                    <p className="text-xs text-red-600 font-semibold mb-1">Denial Reason</p>
                    <p className="text-sm text-red-800">{selected.workflow_result.denial_analysis.denial_reason}</p>
                  </div>
                )}

                {/* Appeal letter */}
                {selected.workflow_result?.appeal_letter && (
                  <div className="border border-amber-200 rounded-xl overflow-hidden">
                    <div className="bg-amber-50 px-4 py-3 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-amber-600"/>
                        <p className="font-semibold text-amber-900 text-sm">Appeal Letter</p>
                      </div>
                      <button onClick={()=>setLetterOpen(v=>!v)}
                        className="text-xs px-2 py-1 bg-white border border-amber-300 text-amber-700 rounded-lg hover:bg-amber-50">
                        {letterOpen ? 'Collapse' : 'View Full'}
                      </button>
                    </div>
                    <div className="bg-white p-4" style={{maxHeight: letterOpen?'400px':'100px', overflow:'auto', transition:'max-height 0.3s'}}>
                      <pre className="text-xs text-slate-700 whitespace-pre-wrap font-mono leading-relaxed">
                        {selected.workflow_result.appeal_letter}
                      </pre>
                    </div>
                    {selected.workflow_result?.appeal_submission_result?.claim_response_id && (
                      <div className="px-4 py-2 bg-blue-50 border-t border-amber-200">
                        <p className="text-xs text-blue-700">
                          Appeal sent to payer · Claim ID: <span className="font-mono">{selected.workflow_result.appeal_submission_result.claim_response_id}</span>
                        </p>
                      </div>
                    )}
                  </div>
                )}

                <div className="text-xs text-slate-400 pt-2 border-t border-slate-100">
                  Created: {new Date(selected.created_at).toLocaleString()} ·
                  Updated: {new Date(selected.updated_at).toLocaleString()}
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
