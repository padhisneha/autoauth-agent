'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  FileCheck, 
  Clock, 
  CheckCircle2, 
  XCircle, 
  ChevronRight,
  Search,
  Filter
} from 'lucide-react';
import { cn, getStatusColor } from '@/lib/utils';

interface Authorization {
  id: string;
  patient_id: string;
  patient: {
    first_name: string;
    last_name: string;
  };
  service_type: string;
  cpt_code: string;
  status: string;
  created_at: string;
}

interface AuthorizationListProps {
  onSelectAuth?: (authId: string) => void;
}

export function AuthorizationList({ onSelectAuth }: AuthorizationListProps) {
  const [authorizations, setAuthorizations] = useState<Authorization[]>([]);
  const [selectedAuth, setSelectedAuth] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    fetchAuthorizations();
    const interval = setInterval(fetchAuthorizations, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchAuthorizations = async () => {
    try {
      const res = await fetch('/api/auth');
      const data = await res.json();
      setAuthorizations(data.authorizations || []);
    } catch (error) {
      console.error('Failed to fetch authorizations:', error);
    }
  };

  const filteredAuths = authorizations.filter(auth => 
    filter === 'all' || auth.status.toLowerCase() === filter
  );

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'approved':
        return <CheckCircle2 className="w-4 h-4 text-green-500" />;
      case 'denied':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'pending':
      case 'processing':
        return <Clock className="w-4 h-4 text-yellow-500" />;
      default:
        return <FileCheck className="w-4 h-4 text-slate-400" />;
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-200">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Authorizations</h2>
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <select 
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="text-sm border-0 bg-transparent text-slate-600 focus:ring-0"
            >
              <option value="all">All</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="denied">Denied</option>
            </select>
          </div>
        </div>
      </div>

      {/* List */}
      <div className="divide-y divide-slate-100">
        <AnimatePresence>
          {filteredAuths.length === 0 ? (
            <div className="p-8 text-center">
              <FileCheck className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500">No authorizations yet</p>
              <p className="text-sm text-slate-400">Select a demo scenario to get started</p>
            </div>
          ) : (
            filteredAuths.map((auth, index) => (
              <motion.button
                key={auth.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
                onClick={() => {
                  setSelectedAuth(auth.id);
                  onSelectAuth?.(auth.id);
                }}
                className={cn(
                  "w-full px-6 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors text-left",
                  selectedAuth === auth.id && "bg-blue-50"
                )}
              >
                <div className="flex items-center gap-4">
                  {getStatusIcon(auth.status)}
                  <div>
                    <p className="font-medium text-slate-900">
                      {auth.patient.first_name} {auth.patient.last_name}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs px-2 py-0.5 bg-slate-100 rounded text-slate-600">
                        {auth.cpt_code}
                      </span>
                      <span className="text-xs text-slate-400 capitalize">
                        {auth.service_type.replace('_', ' ')}
                      </span>
                    </div>
                  </div>
                </div>
                
                <div className="flex items-center gap-3">
                  <span className={cn(
                    "text-xs px-2 py-1 rounded-full font-medium capitalize",
                    getStatusColor(auth.status)
                  )}>
                    {auth.status}
                  </span>
                  <ChevronRight className="w-4 h-4 text-slate-400" />
                </div>
              </motion.button>
            ))
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
