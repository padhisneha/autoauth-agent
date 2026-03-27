'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Activity, 
  Users, 
  FileCheck, 
  Clock, 
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Play,
  Brain,
  Shield,
  Send,
  FileText,
  Heart
} from 'lucide-react';
import { StatsCard } from '@/components/StatsCard';
import { WorkflowVisualization } from '@/components/WorkflowVisualization';
import { ScenarioSelector } from '@/components/ScenarioSelector';
import { AuthorizationList } from '@/components/AuthorizationList';
import { LiveActivityFeed } from '@/components/LiveActivityFeed';

interface DashboardStats {
  total_requests: number;
  approved: number;
  denied: number;
  pending: number;
  approval_rate: number;
  avg_processing_time_seconds: number;
  total_cost_saved: number;
  appeals_success_rate: number;
}

interface Activity {
  auth_id: string;
  patient: string;
  service: string;
  status: string;
  timestamp: string;
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats>({
    total_requests: 0,
    approved: 0,
    denied: 0,
    pending: 0,
    approval_rate: 0,
    avg_processing_time_seconds: 0,
    total_cost_saved: 0,
    appeals_success_rate: 0,
  });
  const [activities, setActivities] = useState<Activity[]>([]);
  const [selectedAuth, setSelectedAuth] = useState<string | null>(null);
  const [currentAuthId, setCurrentAuthId] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    fetchStats();
    fetchActivities();
    const interval = setInterval(() => {
      fetchStats();
      fetchActivities();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchStats = async () => {
    try {
      const res = await fetch('/api/dashboard/stats');
      const data = await res.json();
      setStats(data);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  };

  const fetchActivities = async () => {
    try {
      const res = await fetch('/api/dashboard/recent-activity');
      const data = await res.json();
      setActivities(data.activities || []);
    } catch (error) {
      console.error('Failed to fetch activities:', error);
    }
  };

  // Called by ScenarioSelector when it gets an auth_id back from the backend
  const handleProcessingStarted = (authId: string) => {
    setCurrentAuthId(authId);
    setIsProcessing(true);
  };

  return (
    <div className="space-y-6">
      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-8 text-white">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iMC4wNSI+PHBhdGggZD0iTTM2IDM0djItSDI0di0yaDEyek0zNiAzMHYySDI0di0yaDEyeiIvPjwvZz48L2c+PC9zdmc+')] opacity-50"></div>
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-3 bg-blue-500/20 rounded-xl">
              <Brain className="w-8 h-8 text-blue-400" />
            </div>
            <div>
              <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                AutoAuth Agent
              </h1>
              <p className="text-slate-400">Autonomous Prior Authorization Platform</p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-8">
            <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
              <div className="flex items-center gap-2 text-slate-400 text-sm">
                <Clock className="w-4 h-4" />
                Processing Time
              </div>
              <div className="text-2xl font-bold text-white mt-1">
                {stats.avg_processing_time_seconds.toFixed(1)}s
              </div>
              <div className="text-xs text-green-400 mt-1">vs. 12 days manual</div>
            </div>
            
            <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
              <div className="flex items-center gap-2 text-slate-400 text-sm">
                <TrendingUp className="w-4 h-4" />
                Approval Rate
              </div>
              <div className="text-2xl font-bold text-white mt-1">
                {stats.approval_rate.toFixed(1)}%
              </div>
              <div className="text-xs text-green-400 mt-1">+15% vs manual</div>
            </div>
            
            <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
              <div className="flex items-center gap-2 text-slate-400 text-sm">
                <Shield className="w-4 h-4" />
                Cost Saved
              </div>
              <div className="text-2xl font-bold text-white mt-1">
                ${stats.total_cost_saved.toFixed(0)}
              </div>
              <div className="text-xs text-green-400 mt-1">$70/request</div>
            </div>
            
            <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
              <div className="flex items-center gap-2 text-slate-400 text-sm">
                <Heart className="w-4 h-4" />
                Appeal Success
              </div>
              <div className="text-2xl font-bold text-white mt-1">
                {stats.appeals_success_rate}%
              </div>
              <div className="text-xs text-green-400 mt-1">Auto-generated</div>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatsCard 
          title="Total Requests"
          value={stats.total_requests}
          icon={FileCheck}
          color="blue"
        />
        <StatsCard 
          title="Approved"
          value={stats.approved}
          icon={CheckCircle2}
          color="green"
        />
        <StatsCard 
          title="Pending"
          value={stats.pending}
          icon={Clock}
          color="yellow"
        />
        <StatsCard 
          title="Denied"
          value={stats.denied}
          icon={XCircle}
          color="red"
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Scenario Selector & Workflow */}
        <div className="lg:col-span-2 space-y-6">
          <ScenarioSelector onProcessingStarted={handleProcessingStarted} />
          
          {isProcessing && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <WorkflowVisualization authId={currentAuthId} />
            </motion.div>
          )}
          
          <AuthorizationList onSelectAuth={setSelectedAuth} />
        </div>

        {/* Right: Live Activity */}
        <div className="space-y-6">
          <LiveActivityFeed activities={activities} />
        </div>
      </div>
    </div>
  );
}