'use client';
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  X, CheckCircle2, XCircle, User, FileText, Stethoscope,
  Pill, Activity, AlertTriangle, Loader2, ChevronDown, ChevronUp, Copy, Check
} from 'lucide-react';

const FHIR_BASE = '/payer-api';

interface QueueItem {
  claim_id: string; status: string; received_at: string; is_appeal: boolean;
  patient_name: string; patient_dob: string; cpt_code: string;
  cpt_description: string; payer_name: string;
  diagnoses: {code:string;display:string}[];
  conditions_count: number; medications_count: number; has_appeal_letter?: boolean;
}

interface Detail {
  claim_id: string; is_appeal: boolean; status: string; received_at: string;
  decided_at: string|null; decision: string|null; denial_reason: string|null;
  reviewer_notes: string|null; reviewer: string|null;
  extracted: {
    patient_name: string; patient_dob: string; patient_gender: string;
    cpt_code: string; cpt_description: string; payer_name: string;
    diagnoses: {code:string;display:string}[];
    clinical_summary: string; appeal_letter: string;
    medications_count: number; conditions_count: number;
  };
}

interface Props { item: QueueItem; onClose: () => void; onDecision: () => void; }

const DENIAL_REASONS = [
  'Insufficient documentation of conservative treatment',
  'Service not medically necessary per policy criteria',
  'Missing required clinical information',
  'Requested service not covered under plan',
  'Experimental or investigational procedure',
];

export function ReviewModal({ item, onClose, onDecision }: Props) {
  const [detail, setDetail]         = useState<Detail|null>(null);
  const [loading, setLoading]       = useState(true);
  const [decision, setDecision]     = useState<'approved'|'denied'|null>(null);
  const [reason, setReason]         = useState('');
  const [notes, setNotes]           = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted]   = useState(false);
  const [error, setError]           = useState('');
  const [letterOpen, setLetterOpen] = useState(false);
  const [copied, setCopied]         = useState(false);

  useEffect(() => {
    fetch(`${FHIR_BASE}/payer/review/${item.claim_id}`, { method: 'POST' }).catch(() => {});
    fetch(`${FHIR_BASE}/payer/request/${item.claim_id}`)
      .then(r => r.json()).then(setDetail).catch(() => {})
      .finally(() => setLoading(false));
  }, [item.claim_id]);

  const isDecided = item.status === 'approved' || item.status === 'denied';

  const copyLetter = () => {
    const letter = detail?.extracted?.appeal_letter;
    if (!letter) return;
    navigator.clipboard.writeText(letter);
    setCopied(true); setTimeout(() => setCopied(false), 2000);
  };

  const handleSubmit = async () => {
    if (!decision) { setError('Please select a decision.'); return; }
    if (decision === 'denied' && !reason) { setError('Please provide a denial reason.'); return; }
    setError(''); setSubmitting(true);
    try {
      const resp = await fetch(`${FHIR_BASE}/payer/decide/${item.claim_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, reason: reason||null, notes: notes||null, reviewer: 'Dr. Payer Reviewer' }),
      });
      if (!resp.ok) throw new Error();
      setSubmitted(true);
      setTimeout(() => onDecision(), 1500);
    } catch { setError('Failed to submit. Try again.'); }
    finally { setSubmitting(false); }
  };

  const appealLetter = detail?.extracted?.appeal_letter;

  return (
    <motion.div initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <motion.div initial={{scale:0.95}} animate={{scale:1}} exit={{scale:0.95}}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden">

        {/* Header */}
        <div className={`flex items-center justify-between px-6 py-4 border-b ${item.is_appeal ? 'bg-amber-50 border-amber-200' : 'bg-slate-50 border-slate-200'}`}>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-slate-900">
                {item.is_appeal ? '⚡ Appeal Review' : 'Prior Authorization Review'}
              </h2>
              {item.is_appeal && (
                <span className="text-xs bg-amber-200 text-amber-800 px-2 py-0.5 rounded-full font-semibold">APPEAL</span>
              )}
            </div>
            <p className="text-xs text-slate-500 font-mono mt-0.5">{item.claim_id}</p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-200 rounded-lg">
            <X className="w-5 h-5 text-slate-500"/>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {loading ? (
            <div className="py-12 flex items-center justify-center">
              <Loader2 className="w-8 h-8 animate-spin text-slate-400"/>
            </div>
          ) : (
            <>
              {/* Patient */}
              <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
                <div className="flex items-center gap-2 mb-3"><User className="w-4 h-4 text-slate-500"/>
                  <h3 className="font-semibold text-slate-800 text-sm">Patient</h3>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div><p className="text-xs text-slate-500">Name</p><p className="font-semibold text-slate-900">{item.patient_name}</p></div>
                  <div><p className="text-xs text-slate-500">DOB</p><p className="font-medium text-slate-700">{item.patient_dob||'—'}</p></div>
                  <div><p className="text-xs text-slate-500">Payer</p><p className="font-medium text-slate-700">{item.payer_name||'—'}</p></div>
                </div>
              </div>

              {/* Service */}
              <div className="bg-blue-50 rounded-xl p-4 border border-blue-200">
                <div className="flex items-center gap-2 mb-2"><Activity className="w-4 h-4 text-blue-600"/>
                  <h3 className="font-semibold text-blue-800 text-sm">Requested Service</h3>
                </div>
                <div className="flex items-center gap-2">
                  <span className="px-3 py-1.5 bg-blue-100 text-blue-800 rounded-lg font-mono font-bold text-sm">CPT {item.cpt_code}</span>
                  <span className="text-blue-700 font-medium">{item.cpt_description}</span>
                </div>
              </div>

              {/* Diagnoses */}
              {item.diagnoses.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2"><Stethoscope className="w-4 h-4 text-slate-500"/>
                    <h3 className="font-semibold text-slate-800 text-sm">Diagnoses</h3>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {item.diagnoses.map((d,i) => (
                      <span key={i} className="px-2 py-1 bg-purple-50 border border-purple-200 text-purple-800 rounded-lg text-xs">
                        <span className="font-mono font-bold">{d.code}</span>
                        {d.display && <span className="ml-1 text-purple-600">· {d.display}</span>}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Clinical summary */}
              {detail?.extracted?.clinical_summary && (
                <div>
                  <div className="flex items-center gap-2 mb-2"><FileText className="w-4 h-4 text-slate-500"/>
                    <h3 className="font-semibold text-slate-800 text-sm">Clinical Summary</h3>
                  </div>
                  <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 max-h-40 overflow-y-auto">
                    <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{detail.extracted.clinical_summary}</p>
                  </div>
                </div>
              )}

              {/* Appeal letter — shown when is_appeal */}
              {appealLetter && (
                <div className="border border-amber-200 rounded-xl overflow-hidden">
                  <div className="bg-amber-50 px-4 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-amber-600"/>
                      <p className="font-semibold text-amber-900 text-sm">Appeal Letter from Provider</p>
                    </div>
                    <div className="flex items-center gap-2">
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
                  <div className="bg-white p-4" style={{maxHeight:letterOpen?'400px':'80px',overflow:'hidden',transition:'max-height 0.3s'}}>
                    <pre className="text-xs text-slate-700 whitespace-pre-wrap font-mono leading-relaxed">{appealLetter}</pre>
                  </div>
                  {!letterOpen && <p className="text-xs text-amber-600 px-4 pb-2">→ Click "Read Full" to see the complete letter</p>}
                </div>
              )}

              {/* Evidence counts */}
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-green-50 rounded-xl p-3 border border-green-200 text-center">
                  <p className="text-2xl font-bold text-green-700">{item.conditions_count}</p>
                  <p className="text-xs text-green-600">Clinical Conditions</p>
                </div>
                <div className="bg-amber-50 rounded-xl p-3 border border-amber-200 text-center">
                  <Pill className="w-4 h-4 text-amber-600 mx-auto mb-1"/>
                  <p className="text-2xl font-bold text-amber-700">{item.medications_count}</p>
                  <p className="text-xs text-amber-600">Medications</p>
                </div>
              </div>

              {/* Already decided */}
              {isDecided && (
                <div className={`rounded-xl p-4 border ${item.status==='approved'?'bg-green-50 border-green-200':'bg-red-50 border-red-200'}`}>
                  <div className="flex items-center gap-2">
                    {item.status==='approved' ? <CheckCircle2 className="w-5 h-5 text-green-600"/> : <XCircle className="w-5 h-5 text-red-600"/>}
                    <p className={`font-semibold capitalize ${item.status==='approved'?'text-green-800':'text-red-800'}`}>Already {item.status}</p>
                  </div>
                  {detail?.denial_reason && <p className="text-sm text-red-700 mt-1">Reason: {detail.denial_reason}</p>}
                </div>
              )}

              {/* Decision form */}
              {!isDecided && !submitted && (
                <div className="border-t border-slate-200 pt-4">
                  <h3 className="font-semibold text-slate-800 mb-3">
                    {item.is_appeal ? 'Your Decision on This Appeal' : 'Your Decision'}
                  </h3>
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    {(['approved','denied'] as const).map(d => (
                      <button key={d} onClick={()=>{setDecision(d);setError('');}}
                        className={`flex items-center justify-center gap-2 py-3 rounded-xl border-2 font-semibold transition-all ${
                          decision===d
                            ? d==='approved' ? 'border-green-500 bg-green-50 text-green-700' : 'border-red-500 bg-red-50 text-red-700'
                            : 'border-slate-200 text-slate-500 hover:border-slate-300'
                        }`}>
                        {d==='approved' ? <CheckCircle2 className="w-5 h-5"/> : <XCircle className="w-5 h-5"/>}
                        {d.charAt(0).toUpperCase()+d.slice(1)}
                      </button>
                    ))}
                  </div>

                  {decision==='denied' && (
                    <div className="mb-3">
                      <label className="text-xs font-semibold text-slate-600 mb-1 block">Denial Reason <span className="text-red-500">*</span></label>
                      <select value={reason} onChange={e=>setReason(e.target.value)}
                        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400">
                        <option value="">Select a reason...</option>
                        {DENIAL_REASONS.map(r=><option key={r} value={r}>{r}</option>)}
                      </select>
                    </div>
                  )}

                  <textarea value={notes} onChange={e=>setNotes(e.target.value)} rows={2}
                    placeholder="Reviewer notes (optional)..."
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none mb-3"/>

                  {error && (
                    <div className="flex items-center gap-2 text-red-600 text-sm mb-3">
                      <AlertTriangle className="w-4 h-4"/>{error}
                    </div>
                  )}
                </div>
              )}

              {submitted && (
                <motion.div initial={{scale:0.9}} animate={{scale:1}}
                  className={`rounded-xl p-4 text-center border ${decision==='approved'?'bg-green-50 border-green-200':'bg-red-50 border-red-200'}`}>
                  {decision==='approved'
                    ? <CheckCircle2 className="w-8 h-8 text-green-500 mx-auto mb-2"/>
                    : <XCircle className="w-8 h-8 text-red-500 mx-auto mb-2"/>}
                  <p className={`font-bold text-lg capitalize ${decision==='approved'?'text-green-800':'text-red-800'}`}>
                    {item.is_appeal ? 'Appeal ' : ''}{decision}
                  </p>
                  <p className="text-sm text-slate-500 mt-1">Provider will be notified automatically.</p>
                </motion.div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        {!isDecided && !submitted && (
          <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
            <button onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-200 rounded-lg">Cancel</button>
            <button onClick={handleSubmit} disabled={!decision||submitting}
              className={`px-6 py-2 rounded-xl text-sm font-semibold flex items-center gap-2 transition-all ${
                decision==='approved' ? 'bg-green-600 hover:bg-green-700 text-white disabled:opacity-40'
                : decision==='denied' ? 'bg-red-600 hover:bg-red-700 text-white disabled:opacity-40'
                : 'bg-slate-300 text-slate-500 cursor-not-allowed'
              }`}>
              {submitting && <Loader2 className="w-4 h-4 animate-spin"/>}
              {submitting ? 'Submitting...' : `Submit ${item.is_appeal ? 'Appeal ' : ''}Decision`}
            </button>
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}
