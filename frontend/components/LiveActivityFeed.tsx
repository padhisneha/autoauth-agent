'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Activity, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  Send,
  Brain,
  Shield,
  FileText
} from 'lucide-react';
import { cn, formatTime } from '@/lib/utils';

interface Activity {
  auth_id: string;
  patient: string;
  service: string;
  status: string;
  timestamp: string;
}

interface LiveActivityFeedProps {
  activities: Activity[];
}

const statusConfig: Record<string, { icon: React.ElementType; color: string; bg: string }> = {
  pending: { icon: Clock, color: 'text-yellow-600', bg: 'bg-yellow-100' },
  processing: { icon: Activity, color: 'text-blue-600', bg: 'bg-blue-100' },
  submitted: { icon: Send, color: 'text-cyan-600', bg: 'bg-cyan-100' },
  approved: { icon: CheckCircle2, color: 'text-green-600', bg: 'bg-green-100' },
  denied: { icon: XCircle, color: 'text-red-600', bg: 'bg-red-100' },
  triage: { icon: Activity, color: 'text-pink-600', bg: 'bg-pink-100' },
  evidence_extraction: { icon: Brain, color: 'text-purple-600', bg: 'bg-purple-100' },
  policy_lookup: { icon: Shield, color: 'text-cyan-600', bg: 'bg-cyan-100' },
  appeal_generation: { icon: FileText, color: 'text-amber-600', bg: 'bg-amber-100' },
};

export function LiveActivityFeed({ activities }: LiveActivityFeedProps) {
  const [liveActivities, setLiveActivities] = useState<Activity[]>(activities);
  
  // Update when prop changes
  useEffect(() => {
    setLiveActivities(activities);
  }, [activities]);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <h3 className="font-semibold text-slate-900">Live Activity</h3>
          </div>
          <span className="text-xs text-slate-500">
            {liveActivities.length} events
          </span>
        </div>
      </div>

      {/* Activity Feed */}
      <div className="max-h-[400px] overflow-y-auto">
        <AnimatePresence>
          {liveActivities.length === 0 ? (
            <div className="p-8 text-center">
              <Activity className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <p className="text-sm text-slate-500">No recent activity</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {liveActivities.map((activity, index) => {
                const config = statusConfig[activity.status.toLowerCase()] || statusConfig.pending;
                const Icon = config.icon;
                
                return (
                  <motion.div
                    key={`${activity.auth_id}-${index}`}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="px-4 py-3 hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex items-start gap-3">
                      <div className={cn("p-1.5 rounded-lg", config.bg)}>
                        <Icon className={cn("w-3.5 h-3.5", config.color)} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <p className="text-sm font-medium text-slate-900 truncate">
                            {activity.patient}
                          </p>
                          <span className="text-xs text-slate-400">
                            {formatTime(activity.timestamp)}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs text-slate-500">
                            {activity.service}
                          </span>
                          <span className="text-slate-300">•</span>
                          <span className={cn("text-xs font-medium capitalize", config.color)}>
                            {activity.status.replace(/_/g, ' ')}
                          </span>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          )}
        </AnimatePresence>
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-slate-200 bg-slate-50">
        <p className="text-xs text-slate-500 text-center">
          Real-time updates enabled
        </p>
      </div>
    </div>
  );
}
