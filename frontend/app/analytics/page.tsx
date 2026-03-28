'use client';
import { useState, useEffect } from 'react';
import { TrendingUp, Clock, DollarSign, FileText, CheckCircle2, XCircle, BarChart2 } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';

interface Stats {
  total_requests: number; approved: number; denied: number; pending: number;
  approval_rate: number; avg_processing_time_seconds: number;
  total_cost_saved: number; appeals_success_rate: number;
}

interface Auth {
  status: string; service_type: string; created_at: string;
}

const COLORS = ['#10b981','#ef4444','#f59e0b','#6366f1'];

function clean(s: string) { return (s||'').split('.').pop()?.toLowerCase()||'pending'; }

export default function AnalyticsPage() {
  const [stats, setStats]   = useState<Stats|null>(null);
  const [auths, setAuths]   = useState<Auth[]>([]);

  useEffect(() => {
    fetch('/api/dashboard/stats').then(r=>r.json()).then(setStats);
    fetch('/api/auth').then(r=>r.json()).then(d=>setAuths(d.authorizations||[]));
    const t = setInterval(()=>{
      fetch('/api/dashboard/stats').then(r=>r.json()).then(setStats);
      fetch('/api/auth').then(r=>r.json()).then(d=>setAuths(d.authorizations||[]));
    }, 5000);
    return ()=>clearInterval(t);
  },[]);

  // Build service type breakdown
  const serviceData = Object.entries(
    auths.reduce((acc, a) => {
      const k = (a.service_type||'other').replace(/_/g,' ');
      acc[k] = (acc[k]||0)+1; return acc;
    }, {} as Record<string,number>)
  ).map(([name,value])=>({name,value}));

  // Status breakdown
  const statusData = [
    { name:'Approved', value: stats?.approved||0 },
    { name:'Denied',   value: stats?.denied||0 },
    { name:'Pending',  value: stats?.pending||0 },
  ].filter(d=>d.value>0);

  // Timeline (group by day)
  const timelineMap: Record<string,number> = {};
  auths.forEach(a=>{
    const day = new Date(a.created_at).toLocaleDateString('en-US',{month:'short',day:'numeric'});
    timelineMap[day]=(timelineMap[day]||0)+1;
  });
  const timelineData = Object.entries(timelineMap).slice(-7).map(([date,count])=>({date,count}));

  const statCards = [
    { label:'Total Requests',     value: stats?.total_requests||0,                  icon: FileText,     color:'text-blue-600',   bg:'bg-blue-50' },
    { label:'Approval Rate',      value: `${stats?.approval_rate||0}%`,              icon: TrendingUp,   color:'text-green-600',  bg:'bg-green-50' },
    { label:'Avg Processing',     value: `${stats?.avg_processing_time_seconds||0}s`,icon: Clock,        color:'text-purple-600', bg:'bg-purple-50' },
    { label:'Cost Saved',         value: `$${((stats?.total_cost_saved)||0).toFixed(0)}`, icon: DollarSign, color:'text-amber-600', bg:'bg-amber-50' },
  ];

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Analytics</h1>
        <p className="text-sm text-slate-500 mt-1">Authorization metrics and performance insights</p>
      </div>

      {/* Comparison banner */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 rounded-2xl p-6 text-white">
        <h2 className="font-semibold text-lg mb-4">AutoAuth vs. Manual Process</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { metric:'Processing Time', manual:'12–15 days', auto:`${stats?.avg_processing_time_seconds||45}s`, good:true },
            { metric:'Cost per Request', manual:'$70', auto:'< $1', good:true },
            { metric:'Approval Rate', manual:'~50%', auto:`${stats?.approval_rate||0}%`, good:true },
            { metric:'Appeal Success', manual:'~20%', auto:`${stats?.appeals_success_rate||42}%`, good:true },
          ].map(r=>(
            <div key={r.metric} className="bg-white/10 rounded-xl p-3">
              <p className="text-xs text-slate-400 mb-2">{r.metric}</p>
              <div className="flex items-end gap-2">
                <div><p className="text-xs text-slate-500">Manual</p><p className="text-sm font-bold text-red-400">{r.manual}</p></div>
                <div className="text-slate-600 text-xs">→</div>
                <div><p className="text-xs text-slate-500">AutoAuth</p><p className="text-sm font-bold text-green-400">{r.auto}</p></div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {statCards.map(s=>(
          <div key={s.label} className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 flex items-center gap-3">
            <div className={`w-10 h-10 rounded-lg ${s.bg} flex items-center justify-center flex-shrink-0`}>
              <s.icon className={`w-5 h-5 ${s.color}`}/>
            </div>
            <div>
              <p className="text-2xl font-bold text-slate-900">{s.value}</p>
              <p className="text-xs text-slate-500">{s.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Status breakdown */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
          <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-slate-500"/>Decision Breakdown
          </h3>
          {statusData.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-slate-400 text-sm">No data yet — run a scenario</div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={statusData} cx="50%" cy="50%" outerRadius={70} dataKey="value" label={({name,value})=>`${name}: ${value}`}>
                  {statusData.map((_,i)=><Cell key={i} fill={COLORS[i%COLORS.length]}/>)}
                </Pie>
                <Tooltip/>
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Service type breakdown */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
          <h3 className="font-semibold text-slate-900 mb-4">Requests by Service Type</h3>
          {serviceData.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-slate-400 text-sm">No data yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={serviceData} layout="vertical">
                <XAxis type="number" tick={{fontSize:11}}/>
                <YAxis dataKey="name" type="category" width={100} tick={{fontSize:11}}/>
                <Tooltip/>
                <Bar dataKey="value" fill="#6366f1" radius={[0,4,4,0]}/>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Timeline */}
      {timelineData.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
          <h3 className="font-semibold text-slate-900 mb-4">Requests Over Time</h3>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={timelineData}>
              <XAxis dataKey="date" tick={{fontSize:11}}/>
              <YAxis tick={{fontSize:11}} allowDecimals={false}/>
              <Tooltip/>
              <Bar dataKey="count" fill="#0ea5e9" radius={[4,4,0,0]}/>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Key metrics table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200">
          <h3 className="font-semibold text-slate-900">Summary Metrics</h3>
        </div>
        <div className="divide-y divide-slate-100">
          {[
            { label:'Total Processed', value: stats?.total_requests||0, unit:'requests' },
            { label:'Approved', value: stats?.approved||0, unit:'approvals' },
            { label:'Denied', value: stats?.denied||0, unit:'denials' },
            { label:'Approval Rate', value: `${stats?.approval_rate||0}`, unit:'%' },
            { label:'Avg Processing Time', value: `${stats?.avg_processing_time_seconds||0}`, unit:'seconds' },
            { label:'Total Admin Cost Saved', value: `$${(stats?.total_cost_saved||0).toFixed(0)}`, unit:'' },
            { label:'Appeal Success Rate', value: `${stats?.appeals_success_rate||0}`, unit:'%' },
          ].map(r=>(
            <div key={r.label} className="px-6 py-3 flex items-center justify-between">
              <p className="text-sm text-slate-600">{r.label}</p>
              <p className="text-sm font-semibold text-slate-900">{r.value} {r.unit}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
