'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileCheck, Clock, TrendingUp, CheckCircle2, XCircle,
  Brain, Shield, Heart
} from 'lucide-react';
import { StatsCard } from '@/components/StatsCard';
import { WorkflowVisualization } from '@/components/WorkflowVisualization';
import { ScenarioSelector } from '@/components/ScenarioSelector';
import { AuthorizationList } from '@/components/AuthorizationList';
import { LiveActivityFeed } from '@/components/LiveActivityFeed';

interface DashboardStats {
  total_requests: number; approved: number; denied: number; pending: number;
  approval_rate: number; avg_processing_time_seconds: number;
  total_cost_saved: number; appeals_success_rate: number;
}

interface Activity {
  auth_id: string; patient: string; service: string; status: string; timestamp: string;
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats>({
    total_requests:0, approved:0, denied:0, pending:0,
    approval_rate:0, avg_processing_time_seconds:0, total_cost_saved:0, appeals_success_rate:0
  });
  const [activities, setActivities] = useState<Activity[]>([]);
  const [currentAuthId, setCurrentAuthId] = useState<string|null>(null);
  const [isProcessing, setIsProcessing]   = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [sr, ar] = await Promise.all([
        fetch('/api/dashboard/stats'),
        fetch('/api/dashboard/recent-activity'),
      ]);
      if (sr.ok) setStats(await sr.json());
      if (ar.ok) { const d = await ar.json(); setActivities(d.activities || []); }
    } catch {}
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, [refresh]);

  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-8 text-white">
        <div className="absolute inset-0 opacity-10"
          style={{backgroundImage:'radial-gradient(circle at 20% 50%, #3b82f6 0%, transparent 50%), radial-gradient(circle at 80% 20%, #06b6d4 0%, transparent 50%)'}}/>
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-3 bg-blue-500/20 rounded-xl">
              <Brain className="w-8 h-8 text-blue-400"/>
            </div>
            <div>
              <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                AutoAuth Agent
              </h1>
              <p className="text-slate-400">Autonomous Prior Authorization Platform with Predictive Intelligence</p>
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { icon:Clock,     label:'Avg Processing', value:`${stats.avg_processing_time_seconds.toFixed(0)}s`, sub:'vs. 12–15 days manual' },
              { icon:TrendingUp,label:'Approval Rate',  value:`${stats.approval_rate.toFixed(1)}%`,              sub:'+15% vs manual' },
              { icon:Shield,    label:'Cost Saved',     value:`$${stats.total_cost_saved.toFixed(0)}`,            sub:'$70 saved per request' },
              { icon:Heart,     label:'Appeal Success', value:`${stats.appeals_success_rate}%`,                  sub:'Auto-generated letters' },
            ].map(s=>(
              <div key={s.label} className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
                <div className="flex items-center gap-2 text-slate-400 text-sm mb-1">
                  <s.icon className="w-4 h-4"/> {s.label}
                </div>
                <div className="text-2xl font-bold text-white">{s.value}</div>
                <div className="text-xs text-green-400 mt-0.5">{s.sub}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatsCard title="Total Requests" value={stats.total_requests} icon={FileCheck}    color="blue"/>
        <StatsCard title="Approved"        value={stats.approved}      icon={CheckCircle2} color="green"/>
        <StatsCard title="Pending"         value={stats.pending}       icon={Clock}        color="yellow"/>
        <StatsCard title="Denied"          value={stats.denied}        icon={XCircle}      color="red"/>
      </div>

      {/* Main */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <ScenarioSelector onProcessingStarted={(id) => { setCurrentAuthId(id); setIsProcessing(true); }}/>

          <AnimatePresence>
            {isProcessing && currentAuthId && (
              <motion.div initial={{opacity:0,y:20}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-10}}>
                <WorkflowVisualization authId={currentAuthId}/>
              </motion.div>
            )}
          </AnimatePresence>

          <AuthorizationList onSelectAuth={(id) => { setCurrentAuthId(id); setIsProcessing(true); }}/>
        </div>
        <div>
          <LiveActivityFeed activities={activities}/>
        </div>
      </div>
    </div>
  );
}