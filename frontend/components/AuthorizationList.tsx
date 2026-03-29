'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FileCheck, Clock, CheckCircle2, XCircle, ChevronRight, Filter, FileText } from 'lucide-react';
import { cn, getStatusColor } from '@/lib/utils';

interface Authorization {
  id: string; patient_id: string; status: string; service_type: string;
  cpt_code: string; created_at: string; updated_at?: string;
  patient?: { first_name?: string; last_name?: string } | null;
}

interface Props { onSelectAuth?: (authId: string) => void; }

function clean(s: string) { return (s||'').split('.').pop()?.toLowerCase() || 'pending'; }

function ptName(auth: Authorization) {
  const p = auth.patient;
  if (!p) return auth.patient_id || '—';
  return `${p.first_name||''} ${p.last_name||''}`.trim() || auth.patient_id || '—';
}

function statusIcon(s: string) {
  const cs = clean(s);
  if (cs==='approved' || cs==='appeal_approved') return <CheckCircle2 className="w-4 h-4 text-green-500"/>;
  if (cs==='denied' || cs==='appeal_denied') return <XCircle className="w-4 h-4 text-red-500"/>;
  if (cs.includes('appeal')) return <FileText className="w-4 h-4 text-amber-500"/>;
  return <Clock className="w-4 h-4 text-yellow-500"/>;
}

export function AuthorizationList({ onSelectAuth }: Props) {
  const [authorizations, setAuthorizations] = useState<Authorization[]>([]);
  const [selected, setSelected] = useState<string|null>(null);
  const [filter, setFilter]     = useState('all');

  useEffect(() => {
    const fetch_auths = async () => {
      try {
        const res  = await fetch('/api/auth');
        if (!res.ok) return;
        const data = await res.json();
        const list: Authorization[] = (data.authorizations || []).reverse();
        setAuthorizations(list);
      } catch {}
    };
    fetch_auths();
    const t = setInterval(fetch_auths, 2000);
    return () => clearInterval(t);
  }, []);

  const filtered = authorizations.filter(a => {
    if (filter==='all') return true;
    const cs = clean(a.status);
    if (filter==='appeal') return cs.includes('appeal');
    return cs === filter;
  });

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">
          Authorizations
          {authorizations.length > 0 && (
            <span className="ml-2 text-sm font-normal text-slate-400">({authorizations.length})</span>
          )}
        </h2>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400"/>
          <select value={filter} onChange={e=>setFilter(e.target.value)}
            className="text-sm border-0 bg-transparent text-slate-600 focus:ring-0">
            <option value="all">All</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="denied">Denied</option>
            <option value="appeal">Appeal</option>
          </select>
        </div>
      </div>

      <div className="divide-y divide-slate-100 max-h-[400px] overflow-y-auto">
        <AnimatePresence>
          {filtered.length === 0 ? (
            <div className="p-8 text-center">
              <FileCheck className="w-12 h-12 text-slate-300 mx-auto mb-3"/>
              <p className="text-slate-500">No authorizations yet</p>
              <p className="text-sm text-slate-400">Select a demo scenario to get started</p>
            </div>
          ) : (
            filtered.map((auth, i) => {
              const displayStatus = clean(auth.status);
              return (
                <motion.button key={auth.id}
                  initial={{opacity:0, y:6}} animate={{opacity:1, y:0}}
                  transition={{delay:i*0.03}}
                  onClick={() => { setSelected(auth.id); onSelectAuth?.(auth.id); }}
                  className={cn(
                    "w-full px-6 py-3.5 flex items-center justify-between hover:bg-slate-50 transition-colors text-left",
                    selected===auth.id && "bg-blue-50"
                  )}>
                  <div className="flex items-center gap-3">
                    <div className="flex-shrink-0">{statusIcon(auth.status)}</div>
                    <div>
                      <p className="font-medium text-slate-900 text-sm">{ptName(auth)}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-xs font-mono bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                          {auth.cpt_code}
                        </span>
                        <span className="text-xs text-slate-400 capitalize">
                          {(auth.service_type||'').replace(/_/g,' ')}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className={cn("text-xs px-2 py-1 rounded-full font-medium capitalize",
                      getStatusColor(displayStatus))}>
                      {displayStatus.replace(/_/g,' ')}
                    </span>
                    <ChevronRight className="w-4 h-4 text-slate-300"/>
                  </div>
                </motion.button>
              );
            })
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}