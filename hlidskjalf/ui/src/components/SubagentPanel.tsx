"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  FileText,
  Package,
  Network,
  Shield,
  TestTube2,
  Eye,
  Users,
  Database,
  DollarSign,
  AlertTriangle,
  Scale,
  Briefcase,
  FileCode,
  Server,
  HardDrive,
  Activity,
} from "lucide-react";

interface Subagent {
  name: string;
  description: string;
  status: "ready" | "working" | "idle";
  tasksCompleted: number;
}

const SUBAGENT_ICONS: Record<string, any> = {
  file_manager: FileText,
  app_installer: Package,
  network_specialist: Network,
  security_specialist: Shield,
  qa_engineer: TestTube2,
  observability_monitor: Eye,
  sso_identity_expert: Users,
  schema_architect: Database,
  cost_analyst: DollarSign,
  risk_assessor: AlertTriangle,
  governance_officer: Scale,
  project_coordinator: Briefcase,
  technical_writer: FileCode,
  devops_engineer: Server,
  data_engineer: HardDrive,
};

export function SubagentPanel() {
  const [subagents, setSubagents] = useState<Subagent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeSubagents, setActiveSubagents] = useState<Set<string>>(new Set());

  useEffect(() => {
    // Fetch subagent list
    fetchSubagents();
    
    // Subscribe to observability stream
    const eventSource = new EventSource('/api/norns/observability/stream');
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'subagent_start') {
        setActiveSubagents(prev => new Set(prev).add(data.agent));
      } else if (data.type === 'subagent_end') {
        setActiveSubagents(prev => {
          const newSet = new Set(prev);
          newSet.delete(data.agent);
          return newSet;
        });
      }
    };
    
    return () => eventSource.close();
  }, []);

  const fetchSubagents = async () => {
    try {
      const response = await fetch('/api/norns/subagents');
      const data = await response.json();
      setSubagents(data.subagents);
      setIsLoading(false);
    } catch (error) {
      console.error('Failed to fetch subagents:', error);
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-sm text-raven-500">Loading subagents...</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-raven-300">
          Specialist Subagents ({subagents.length})
        </h3>
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-healthy animate-pulse" />
          <span className="text-xs text-raven-500">
            {activeSubagents.size} active
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {subagents.map((subagent) => {
          const Icon = SUBAGENT_ICONS[subagent.name] || FileCode;
          const isActive = activeSubagents.has(subagent.name);

          return (
            <motion.div
              key={subagent.name}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className={`
                relative overflow-hidden rounded-lg border p-3
                ${isActive 
                  ? 'bg-odin-500/10 border-odin-500/50' 
                  : 'bg-raven-800/30 border-raven-700/50'
                }
                hover:bg-raven-800/50 transition-all duration-200
              `}
            >
              {isActive && (
                <motion.div
                  className="absolute inset-0 bg-gradient-to-r from-odin-500/20 to-transparent"
                  animate={{
                    x: ['-100%', '100%'],
                  }}
                  transition={{
                    duration: 1.5,
                    repeat: Infinity,
                    ease: "linear",
                  }}
                />
              )}
              
              <div className="relative flex items-start gap-3">
                <div className={`
                  flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center
                  ${isActive ? 'bg-odin-500/20' : 'bg-raven-700/50'}
                `}>
                  <Icon className={`w-4 h-4 ${isActive ? 'text-odin-400' : 'text-raven-400'}`} />
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs font-medium text-raven-200 truncate">
                      {subagent.name.replace(/_/g, ' ')}
                    </h4>
                    {isActive && (
                      <span className="flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-odin-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-odin-500"></span>
                      </span>
                    )}
                  </div>
                  <p className="text-[10px] text-raven-500 mt-0.5 line-clamp-2">
                    {subagent.description}
                  </p>
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

