'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CheckCircle2,
  XCircle,
  ArrowRight,
  Sparkles,
  Brain,
  Shield,
  Send,
  Activity,
  FileText,
  Search,
  AlertTriangle
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface Agent {
  name: string;
  status: 'idle' | 'running' | 'completed' | 'failed' | 'waiting';
  start_time?: string;
  end_time?: string;
  output_data?: Record<string, any>;
  reasoning_steps?: string[];
  tokens_used?: number;
}

interface WorkflowState {
  auth_id: string;
  current_state: string;
  agents: Record<string, Agent>;
  processing_log: Array<{ timestamp: string; event_type: string; state: string; data: Record<string, any> }>;
  clinical_evidence?: any;
  policy_match?: any;
  submission_result?: any;
  appeal_letter?: string;
}

interface WorkflowVisualizationProps {
  authId: string | null;
}

const WORKFLOW_STAGES = [
  { id: 'triage', name: 'Triage', icon: Activity, color: 'pink' },
  { id: 'evidence_extraction', name: 'Clinical Reading', icon: Brain, color: 'purple' },
  { id: 'policy_lookup', name: 'Policy Match', icon: Shield, color: 'cyan' },
  { id: 'validation', name: 'Validation', icon: Search, color: 'blue' },
  { id: 'submission', name: 'Submission', icon: Send, color: 'green' },
  { id: 'monitoring', name: 'Decision', icon: Activity, color: 'yellow' },
  { id: 'appeal_generation', name: 'Appeal', icon: FileText, color: 'amber' },
];

const colorMap: Record<string, { border: string; text: string; bg: string }> = {
  pink: { border: 'border-pink-500', text: 'text-pink-600', bg: 'bg-pink-100' },
  purple: { border: 'border-purple-500', text: 'text-purple-600', bg: 'bg-purple-100' },
  cyan: { border: 'border-cyan-500', text: 'text-cyan-600', bg: 'bg-cyan-100' },
  blue: { border: 'border-blue-500', text: 'text-blue-600', bg: 'bg-blue-100' },
  green: { border: 'border-green-500', text: 'text-green-600', bg: 'bg-green-100' },
  yellow: { border: 'border-yellow-500', text: 'text-yellow-600', bg: 'bg-yellow-100' },
  amber: { border: 'border-amber-500', text: 'text-amber-600', bg: 'bg-amber-100' },
  gray: { border: 'border-slate-200', text: 'text-slate-400', bg: 'bg-slate-100' },
};

// Ordered list of states so we can determine which stages are done
const STATE_ORDER = [
  'pending', 'triage', 'evidence_extraction', 'policy_lookup',
  'validation', 'submission', 'monitoring', 'approved', 'denied',
  'appeal_analysis', 'appeal_generation', 'appeal_submission'
];

export function WorkflowVisualization({ authId }: WorkflowVisualizationProps) {
  const [workflowState, setWorkflowState] = useState<WorkflowState | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  useEffect(() => {
    if (!authId) return;

    const pollWorkflow = async () => {
      try {
        const res = await fetch(`/api/auth/${authId}/trace`);
        if (!res.ok) return;
        const data = await res.json();
        setWorkflowState(data);

        const state = (data.current_state || '').toLowerCase();
        const terminal = ['approved', 'denied', 'appeal_approved', 'appeal_denied', 'completed', 'requires_human_review'];
        if (terminal.includes(state)) {
          setIsPolling(false);
          clearInterval(interval);
        }
      } catch (error) {
        console.error('Failed to fetch workflow:', error);
      }
    };

    pollWorkflow();
    const interval = setInterval(pollWorkflow, 1500);
    setIsPolling(true);

    return () => {
      clearInterval(interval);
      setIsPolling(false);
    };
  }, [authId]);

  const currentStateNorm = (workflowState?.current_state || '').toLowerCase();

  const getStageStatus = (stageId: string): 'pending' | 'active' | 'completed' | 'failed' => {
    if (!workflowState) return 'pending';

    const currentIndex = STATE_ORDER.indexOf(currentStateNorm);
    const stageIndex = STATE_ORDER.indexOf(stageId);

    if (currentStateNorm === 'approved' || currentStateNorm === 'denied') {
      // All stages up to monitoring are done
      const monitoringIdx = STATE_ORDER.indexOf('monitoring');
      if (stageIndex <= monitoringIdx) return 'completed';
    }

    if (stageIndex < currentIndex) return 'completed';
    if (stageIndex === currentIndex) return 'active';
    return 'pending';
  };

  const getAgentForStage = (stageId: string): Agent | undefined => {
    if (!workflowState) return undefined;

    const agentMap: Record<string, string> = {
      'triage': 'TriageAgent',
      'evidence_extraction': 'ClinicalReaderAgent',
      'policy_lookup': 'PolicyAgent',
      'validation': 'ValidationAgent',
      'submission': 'SubmissionAgent',
      'monitoring': 'MonitoringAgent',
      'appeal_generation': 'AppealAgent',
    };

    const agentName = agentMap[stageId];
    return agentName ? workflowState.agents?.[agentName] : undefined;
  };

  const isApproved = currentStateNorm === 'approved';
  const isDenied = ['denied', 'appeal_generation', 'appeal_submission'].includes(currentStateNorm);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white/10 rounded-lg">
              <Sparkles className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <h2 className="text-white font-semibold">Live Agent Workflow</h2>
              <p className="text-slate-400 text-sm">Real-time processing visualization</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className={cn(
              "w-3 h-3 rounded-full",
              isPolling ? "bg-green-500 animate-pulse" : "bg-gray-400"
            )}></div>
            <span className="text-sm text-slate-400">
              {isPolling ? 'Processing...' : isApproved ? 'Approved' : isDenied ? 'Denied' : 'Idle'}
            </span>
          </div>
        </div>
      </div>

      {/* Workflow Stages */}
      <div className="p-6">
        <div className="flex items-center justify-between overflow-x-auto pb-4">
          {WORKFLOW_STAGES.map((stage, index) => {
            const status = getStageStatus(stage.id);
            const colors = colorMap[status === 'active' ? stage.color : 'gray'];
            const agent = getAgentForStage(stage.id);

            return (
              <div key={stage.id} className="flex items-center">
                <div className="flex flex-col items-center min-w-[100px]">
                  <motion.div
                    className={cn(
                      "relative w-14 h-14 rounded-xl border-2 flex items-center justify-center transition-all duration-500",
                      status === 'completed' && "bg-green-50 border-green-500",
                      status === 'active' && `bg-white shadow-lg ${colors.border}`,
                      status === 'failed' && "bg-red-50 border-red-500",
                      status === 'pending' && "border-slate-200 bg-slate-50"
                    )}
                    animate={status === 'active' ? { scale: [1, 1.05, 1] } : {}}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    {status === 'completed' && <CheckCircle2 className="w-6 h-6 text-green-500" />}
                    {status === 'failed' && <XCircle className="w-6 h-6 text-red-500" />}
                    {status === 'active' && (
                      <>
                        <stage.icon className={cn("w-6 h-6 relative z-10", colors.text)} />
                        <motion.div
                          className={cn("absolute inset-0 rounded-xl", colors.bg)}
                          animate={{ opacity: [0.3, 0.6, 0.3] }}
                          transition={{ duration: 1.5, repeat: Infinity }}
                        />
                      </>
                    )}
                    {status === 'pending' && <stage.icon className="w-6 h-6 text-slate-300" />}
                  </motion.div>
                  <p className={cn(
                    "text-xs font-medium mt-2 text-center",
                    status === 'active' ? 'text-slate-900' : 'text-slate-500'
                  )}>
                    {stage.name}
                  </p>

                  {/* Agent status badge */}
                  {agent && status === 'active' && (
                    <motion.div
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mt-2 px-2 py-1 bg-purple-50 rounded-full"
                    >
                      <span className="text-xs text-purple-600 font-medium">
                        {agent.status}
                      </span>
                    </motion.div>
                  )}
                </div>

                {index < WORKFLOW_STAGES.length - 1 && (
                  <ArrowRight className={cn(
                    "w-5 h-5 mx-2 flex-shrink-0",
                    getStageStatus(stage.id) === 'completed' ? 'text-green-500' : 'text-slate-300'
                  )} />
                )}
              </div>
            );
          })}
        </div>

        {/* Agent Details Panel */}
        <AnimatePresence mode="wait">
          {workflowState && workflowState.agents && Object.keys(workflowState.agents).length > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-6 pt-6 border-t border-slate-200"
            >
              <h3 className="text-sm font-semibold text-slate-900 mb-4">Agent Execution Details</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.values(workflowState.agents).map((agent) => (
                  <AgentCard key={agent.name} agent={agent} />
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Results Summary */}
        <AnimatePresence>
          {isApproved && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="mt-6 p-4 bg-green-50 border border-green-200 rounded-xl"
            >
              <div className="flex items-center gap-3">
                <CheckCircle2 className="w-6 h-6 text-green-500" />
                <div>
                  <p className="font-semibold text-green-900">Authorization Approved!</p>
                  <p className="text-sm text-green-700">
                    ID: {workflowState?.submission_result?.external_auth_id}
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {isDenied && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="mt-6 p-4 bg-amber-50 border border-amber-200 rounded-xl"
            >
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-6 h-6 text-amber-500" />
                <div>
                  <p className="font-semibold text-amber-900">Authorization Denied</p>
                  <p className="text-sm text-amber-700">
                    Appeal letter automatically generated
                  </p>
                </div>
              </div>
              {workflowState?.appeal_letter && (
                <div className="mt-3 p-3 bg-white rounded-lg border border-amber-200 max-h-40 overflow-y-auto">
                  <pre className="text-xs text-slate-600 whitespace-pre-wrap font-mono">
                    {workflowState.appeal_letter.substring(0, 600)}...
                  </pre>
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
  const statusColors: Record<string, string> = {
    idle: 'bg-gray-100 text-gray-600',
    running: 'bg-blue-100 text-blue-600',
    completed: 'bg-green-100 text-green-600',
    failed: 'bg-red-100 text-red-600',
    waiting: 'bg-yellow-100 text-yellow-600',
  };

  return (
    <div className="p-4 bg-slate-50 rounded-xl border border-slate-200">
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-medium text-slate-900">{agent.name}</h4>
        <span className={cn(
          "text-xs px-2 py-1 rounded-full font-medium capitalize",
          statusColors[agent.status] || statusColors.idle
        )}>
          {agent.status}
        </span>
      </div>
      {agent.output_data && Object.keys(agent.output_data).length > 0 && (
        <div className="space-y-1">
          {Object.entries(agent.output_data).slice(0, 3).map(([key, val]) => (
            <div key={key} className="flex justify-between text-xs">
              <span className="text-slate-500 capitalize">{key.replace(/_/g, ' ')}</span>
              <span className="text-slate-700 font-medium truncate ml-2 max-w-[120px]">
                {typeof val === 'boolean' ? (val ? 'Yes' : 'No') : String(val)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}