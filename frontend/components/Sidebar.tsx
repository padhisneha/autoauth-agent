'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  LayoutDashboard, 
  Users, 
  FileCheck, 
  Activity,
  Settings,
  Brain,
  Shield,
  Bell,
  HelpCircle,
  ChevronRight
} from 'lucide-react';
import { cn } from '@/lib/utils';

const navItems = [
  {
    title: 'Dashboard',
    href: '/',
    icon: LayoutDashboard,
  },
  {
    title: 'Patients',
    href: '/patients',
    icon: Users,
  },
  {
    title: 'Authorizations',
    href: '/authorizations',
    icon: FileCheck,
  },
  {
    title: 'Analytics',
    href: '/analytics',
    icon: Activity,
  },
];

const secondaryItems = [
  {
    title: 'Settings',
    href: '/settings',
    icon: Settings,
  },
  {
    title: 'Help',
    href: '/help',
    icon: HelpCircle,
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-lg">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-white text-lg">AutoAuth</h1>
            <p className="text-xs text-slate-400">AI Agent Platform</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-2">
        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-3">
          Main Menu
        </div>
        
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 group",
                isActive 
                  ? "bg-blue-600 text-white" 
                  : "text-slate-400 hover:bg-slate-800 hover:text-white"
              )}
            >
              <item.icon className={cn(
                "w-5 h-5",
                isActive ? "text-white" : "text-slate-500 group-hover:text-white"
              )} />
              <span className="font-medium">{item.title}</span>
              {isActive && (
                <ChevronRight className="w-4 h-4 ml-auto" />
              )}
            </Link>
          );
        })}

        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mt-8 mb-3 px-3">
          System
        </div>

        {secondaryItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200",
                isActive 
                  ? "bg-slate-800 text-white" 
                  : "text-slate-400 hover:bg-slate-800 hover:text-white"
              )}
            >
              <item.icon className="w-5 h-5 text-slate-500" />
              <span className="font-medium">{item.title}</span>
            </Link>
          );
        })}
      </nav>

      {/* Agent Status */}
      <div className="p-4 border-t border-slate-800">
        <div className="bg-slate-800/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-sm font-medium text-white">System Status</span>
          </div>
          <div className="space-y-2">
            <AgentStatus name="Clinical Reader" status="active" color="purple" />
            <AgentStatus name="Policy Agent" status="active" color="cyan" />
            <AgentStatus name="Submission Agent" status="active" color="green" />
            <AgentStatus name="Appeal Agent" status="ready" color="amber" />
          </div>
        </div>
      </div>
    </div>
  );
}

function AgentStatus({ name, status, color }: { name: string; status: string; color: string }) {
  const colorMap: Record<string, string> = {
    purple: 'bg-purple-500',
    cyan: 'bg-cyan-500',
    green: 'bg-green-500',
    amber: 'bg-amber-500',
  };

  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-slate-400">{name}</span>
      <span className={cn("text-xs font-medium capitalize", 
        status === 'active' ? 'text-green-400' : 'text-slate-400'
      )}>
        {status}
      </span>
    </div>
  );
}
