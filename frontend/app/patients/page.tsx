'use client';
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { User, Phone, MapPin, Shield, FileText, Activity, Plus, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Patient {
  id: string; mrn: string; first_name: string; last_name: string;
  date_of_birth: string; gender: string; address: string; phone: string;
  insurance_id: string; payer_name: string;
  conditions: {code:string;name:string}[];
  medications: {name:string;frequency:string}[];
  allergies: string[];
}

interface Auth {
  id: string; status: string; service_type: string; cpt_code: string; created_at: string;
}

function age(dob: string) {
  return Math.floor((Date.now() - new Date(dob).getTime()) / (365.25*24*3600*1000));
}

function statusColor(s: string) {
  const m: Record<string,string> = {approved:'bg-green-100 text-green-800',denied:'bg-red-100 text-red-800',pending:'bg-yellow-100 text-yellow-800'};
  return m[s] || 'bg-slate-100 text-slate-600';
}

export default function PatientsPage() {
  const [patients, setPatients]   = useState<Patient[]>([]);
  const [selected, setSelected]   = useState<Patient|null>(null);
  const [auths, setAuths]         = useState<Auth[]>([]);
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    fetch('/api/patients').then(r=>r.json()).then(d=>{ setPatients(d.patients||[]); setLoading(false); });
  }, []);

  useEffect(() => {
    if (!selected) return;
    fetch('/api/auth').then(r=>r.json()).then(d=>{
      const all: Auth[] = d.authorizations || [];
      setAuths(all.filter(a => {
        const p = (a as any).patient;
        return p?.id === selected.id || a.patient_id === selected.id || (a as any).patient_id === selected.id;
      }));
    });
  }, [selected]);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Patients</h1>
          <p className="text-sm text-slate-500 mt-1">Manage patient records and authorization history</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors">
          <Plus className="w-4 h-4" /> Add Patient
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Patient list */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-200 bg-slate-50">
              <p className="font-semibold text-slate-900">{patients.length} Patients</p>
            </div>
            {loading ? (
              <div className="p-8 text-center text-slate-400 text-sm">Loading...</div>
            ) : (
              <div className="divide-y divide-slate-100">
                {patients.map((p, i) => (
                  <motion.button key={p.id} initial={{opacity:0}} animate={{opacity:1}} transition={{delay:i*0.05}}
                    onClick={() => setSelected(p)}
                    className={cn("w-full px-4 py-3 flex items-center gap-3 hover:bg-slate-50 transition-colors text-left",
                      selected?.id===p.id && "bg-blue-50")}>
                    <div className="w-10 h-10 bg-gradient-to-br from-blue-400 to-cyan-500 rounded-full flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
                      {p.first_name[0]}{p.last_name[0]}
                    </div>
                    <div className="min-w-0">
                      <p className="font-semibold text-slate-900 text-sm truncate">{p.first_name} {p.last_name}</p>
                      <p className="text-xs text-slate-500">{p.mrn} · {age(p.date_of_birth)}y · {p.gender}</p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-slate-300 flex-shrink-0" />
                  </motion.button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Patient detail */}
        <div className="lg:col-span-2">
          {!selected ? (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-12 text-center">
              <User className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500">Select a patient to view details</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Header card */}
              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
                <div className="flex items-start gap-4">
                  <div className="w-16 h-16 bg-gradient-to-br from-blue-400 to-cyan-500 rounded-2xl flex items-center justify-center text-white font-bold text-xl flex-shrink-0">
                    {selected.first_name[0]}{selected.last_name[0]}
                  </div>
                  <div className="flex-1">
                    <h2 className="text-xl font-bold text-slate-900">{selected.first_name} {selected.last_name}</h2>
                    <p className="text-slate-500 text-sm">{selected.mrn} · {age(selected.date_of_birth)} years old · {selected.gender}</p>
                    <div className="flex flex-wrap gap-3 mt-3">
                      {selected.phone && (
                        <span className="flex items-center gap-1.5 text-xs text-slate-600"><Phone className="w-3.5 h-3.5"/>{selected.phone}</span>
                      )}
                      {selected.address && (
                        <span className="flex items-center gap-1.5 text-xs text-slate-600"><MapPin className="w-3.5 h-3.5"/>{selected.address}</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Insurance */}
              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
                <div className="flex items-center gap-2 mb-3">
                  <Shield className="w-4 h-4 text-blue-500" />
                  <h3 className="font-semibold text-slate-800">Insurance</h3>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div><p className="text-xs text-slate-500">Payer</p><p className="font-medium text-slate-800">{selected.payer_name}</p></div>
                  <div><p className="text-xs text-slate-500">Member ID</p><p className="font-medium text-slate-800 font-mono">{selected.insurance_id}</p></div>
                </div>
              </div>

              {/* Conditions + Meds */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
                  <h3 className="font-semibold text-slate-800 mb-3 flex items-center gap-2">
                    <Activity className="w-4 h-4 text-purple-500"/>Conditions
                  </h3>
                  {selected.conditions.length === 0 ? <p className="text-xs text-slate-400">None on file</p> :
                    selected.conditions.map((c,i) => (
                      <div key={i} className="flex items-center gap-2 mb-1.5">
                        <span className="text-xs font-mono text-purple-600 bg-purple-50 px-1.5 py-0.5 rounded">{c.code}</span>
                        <span className="text-xs text-slate-700">{c.name}</span>
                      </div>
                    ))
                  }
                </div>
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
                  <h3 className="font-semibold text-slate-800 mb-3">Medications</h3>
                  {selected.medications.length === 0 ? <p className="text-xs text-slate-400">None on file</p> :
                    selected.medications.map((m,i) => (
                      <div key={i} className="mb-1.5">
                        <p className="text-xs font-medium text-slate-700">{m.name}</p>
                        <p className="text-xs text-slate-400">{m.frequency}</p>
                      </div>
                    ))
                  }
                </div>
              </div>

              {/* Allergies */}
              {selected.allergies.length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded-2xl p-4">
                  <p className="text-sm font-semibold text-red-800 mb-2">⚠ Allergies</p>
                  <div className="flex flex-wrap gap-2">
                    {selected.allergies.map((a,i) => (
                      <span key={i} className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded-full">{a}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Auth history */}
              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="px-5 py-3 border-b border-slate-200 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-slate-500"/>
                  <h3 className="font-semibold text-slate-800">Authorization History</h3>
                </div>
                {auths.length === 0 ? (
                  <div className="p-6 text-center text-sm text-slate-400">No authorizations yet</div>
                ) : (
                  <div className="divide-y divide-slate-100">
                    {auths.map(a => (
                      <div key={a.id} className="px-5 py-3 flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-slate-700">CPT {a.cpt_code} · {a.service_type.replace('_',' ')}</p>
                          <p className="text-xs text-slate-400">{new Date(a.created_at).toLocaleDateString()}</p>
                        </div>
                        <span className={cn("text-xs px-2 py-1 rounded-full font-medium capitalize", statusColor(a.status))}>
                          {a.status}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
