"use client";

import Link from "next/link";
import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { 
  Eye, 
  Bird, 
  Server, 
  Network, 
  Shield, 
  Activity,
  Database,
  Globe,
  Flame,
  Snowflake,
  Mountain,
  Trees,
  Moon,
  Sun,
  Skull,
  ChevronRight,
  Plus,
  RefreshCw,
  Settings,
  Loader2
} from "lucide-react";
import { NornsChat } from "@/components/NornsChat";
import { ObservabilityWidget } from "@/components/observability";
import { LLMSettingsPanel } from "@/components/llm-settings";
import { NewProjectWizard } from "@/components/new-project";
import { api } from "@/lib/api";

// The Nine Realms with their characteristics
const REALMS = [
  { id: "midgard", name: "Midgard", icon: Globe, color: "text-emerald-400", desc: "Development", status: "active" },
  { id: "alfheim", name: "Alfheim", icon: Sun, color: "text-amber-300", desc: "Staging", status: "active" },
  { id: "asgard", name: "Asgard", icon: Shield, color: "text-odin-400", desc: "Production", status: "active" },
  { id: "vanaheim", name: "Vanaheim", icon: Trees, color: "text-green-500", desc: "Shared Services", status: "active" },
  { id: "svartalfheim", name: "Svartalfheim", icon: Database, color: "text-purple-400", desc: "Data", status: "active" },
  { id: "jotunheim", name: "Jötunheim", icon: Mountain, color: "text-slate-400", desc: "Sandbox", status: "idle" },
  { id: "muspelheim", name: "Muspelheim", icon: Flame, color: "text-orange-500", desc: "Load Testing", status: "idle" },
  { id: "niflheim", name: "Niflheim", icon: Snowflake, color: "text-cyan-300", desc: "DR", status: "standby" },
  { id: "helheim", name: "Helheim", icon: Skull, color: "text-raven-500", desc: "Archive", status: "cold" },
];

export default function HlidskjalfDashboard() {
  const [selectedRealm, setSelectedRealm] = useState<string | null>(null);
  const [showLLMSettings, setShowLLMSettings] = useState(false);
  const [showNewProject, setShowNewProject] = useState(false);

  // Fetch platform overview stats
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['platform-overview'],
    queryFn: () => api.getOverview(),
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  // Fetch projects with optional realm filtering
  const { data: projects, isLoading: projectsLoading } = useQuery({
    queryKey: ['projects', selectedRealm],
    queryFn: () => api.listProjects(selectedRealm || undefined),
    refetchInterval: 15000, // Refresh every 15 seconds
  });

  // Calculate realm statistics from projects
  const realmStats = useMemo(() => {
    if (!projects) return {};
    
    const stats: Record<string, { services: number; health: Record<string, number> }> = {};
    
    projects.forEach(project => {
      // Count services per project (from ports)
      const serviceCount = project.ports.length;
      
      // This would ideally come from deployments, but we'll use a simplified approach
      // In a real implementation, you'd join with deployment data
      const realm = "midgard"; // Default for now
      
      if (!stats[realm]) {
        stats[realm] = { services: 0, health: {} };
      }
      stats[realm].services += serviceCount;
    });
    
    return stats;
  }, [projects]);

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-raven-800/50 bg-raven-950/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <motion.div 
                className="relative"
                animate={{ rotate: [0, 5, -5, 0] }}
                transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
              >
                <Eye className="w-10 h-10 text-odin-400" />
                <div className="absolute inset-0 bg-odin-400/20 blur-xl rounded-full" />
              </motion.div>
              <div>
                <h1 className="text-2xl font-display font-bold text-raven-100">
                  Hliðskjálf
                </h1>
                <p className="text-sm text-raven-500 font-sans">
                  Odin's High Seat • Observe All Realms
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-6">
              {/* Ravens Status */}
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2 text-huginn-400">
                  <Bird className="w-5 h-5" />
                  <span className="text-sm font-medium">Huginn</span>
                  <span className="w-2 h-2 bg-huginn-400 rounded-full status-breathe" />
                </div>
                <div className="flex items-center gap-2 text-muninn-400">
                  <Bird className="w-5 h-5 transform scale-x-[-1]" />
                  <span className="text-sm font-medium">Muninn</span>
                  <span className="w-2 h-2 bg-muninn-400 rounded-full status-breathe" />
                </div>
              </div>
              
              <button
                onClick={() => setShowLLMSettings(true)}
                className="btn-secondary flex items-center gap-2 whitespace-nowrap"
                title="Configure LLM providers and models"
              >
                <Settings className="w-4 h-4" />
                LLM Settings
              </button>
              <button 
                onClick={() => setShowNewProject(true)}
                className="btn-primary flex items-center gap-2"
              >
                <Plus className="w-4 h-4" />
                New Project
              </button>
              <Link
                href="/norns"
                className="btn-secondary flex items-center gap-2 whitespace-nowrap"
              >
                Meet the Norns
                <ChevronRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Stats Overview */}
        <div className="grid grid-cols-5 gap-4 mb-8">
          {statsLoading ? (
            <>
              {[...Array(5)].map((_, i) => (
                <div key={i} className="stat-card animate-pulse">
                  <div className="h-4 bg-raven-800 rounded mb-2" />
                  <div className="h-8 bg-raven-800 rounded" />
                </div>
              ))}
            </>
          ) : stats ? (
            <>
          <StatCard 
            label="Projects" 
                value={stats.total_projects} 
            icon={Server}
            color="text-odin-400"
          />
          <StatCard 
                label="Deployments" 
                value={stats.total_deployments} 
            icon={Network}
            color="text-huginn-400"
          />
          <StatCard 
            label="Ports Allocated" 
                value={stats.ports_allocated} 
            icon={Activity}
            color="text-muninn-400"
          />
          <StatCard 
            label="Healthy" 
                value={stats.healthy_deployments} 
            icon={Shield}
            color="text-healthy"
          />
          <StatCard 
            label="Unhealthy" 
                value={stats.unhealthy_deployments} 
            icon={Activity}
            color="text-unhealthy"
          />
            </>
          ) : (
            <div className="col-span-5 text-center text-raven-500 py-8">
              Failed to load stats
            </div>
          )}
        </div>

        {/* Observability Stream */}
        <div className="mb-8">
          <ObservabilityWidget />
        </div>

        {/* Nine Realms Grid */}
        <section className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-display font-semibold text-raven-100">
              The Nine Realms
            </h2>
            <button className="text-sm text-raven-400 hover:text-raven-200 flex items-center gap-1">
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
          </div>
          
          <div className="grid grid-cols-3 gap-4">
            {REALMS.map((realm, index) => (
              <motion.button
                key={realm.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
                onClick={() => setSelectedRealm(realm.id === selectedRealm ? null : realm.id)}
                className={`card-hover p-4 text-left transition-all ${
                  selectedRealm === realm.id ? "border-odin-500/50 bg-odin-500/5" : ""
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg bg-raven-800/50 ${realm.color}`}>
                      <realm.icon className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-medium text-raven-100">{realm.name}</h3>
                      <p className="text-sm text-raven-500">{realm.desc}</p>
                    </div>
                  </div>
                  <RealmStatus status={realm.status} />
                </div>
              </motion.button>
            ))}
          </div>
        </section>

        {/* Projects Table */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-display font-semibold text-raven-100">
              Projects Registry
            </h2>
            <button className="text-sm text-odin-400 hover:text-odin-300 flex items-center gap-1">
              View All
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
          
          <div className="card overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-raven-800 text-left">
                  <th className="px-4 py-3 text-sm font-medium text-raven-400">Project</th>
                  <th className="px-4 py-3 text-sm font-medium text-raven-400">Realm</th>
                  <th className="px-4 py-3 text-sm font-medium text-raven-400">Services</th>
                  <th className="px-4 py-3 text-sm font-medium text-raven-400">Health</th>
                  <th className="px-4 py-3 text-sm font-medium text-raven-400">Actions</th>
                </tr>
              </thead>
              <tbody>
                {projectsLoading ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center">
                      <Loader2 className="w-6 h-6 animate-spin mx-auto text-odin-400" />
                    </td>
                  </tr>
                ) : projects && projects.length > 0 ? (
                  projects.map((project) => {
                    // Determine realm from project data (simplified)
                    const realm = REALMS[0]; // Default to Midgard for now
                    const serviceCount = project.ports.length;
                    
                  return (
                    <tr key={project.id} className="table-row">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-raven-800 flex items-center justify-center text-odin-400 font-bold">
                            {project.name[0]}
                          </div>
                          <div>
                            <div className="font-medium text-raven-100">{project.name}</div>
                            <div className="text-sm text-raven-500">{project.id}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className={`flex items-center gap-2 ${realm?.color}`}>
                          {realm && <realm.icon className="w-4 h-4" />}
                          <span className="text-sm">{realm?.name}</span>
                        </div>
                      </td>
                        <td className="px-4 py-3 text-raven-300">{serviceCount}</td>
                      <td className="px-4 py-3">
                          <span className="badge-healthy">
                            healthy
                        </span>
                      </td>
                      <td className="px-4 py-3">
                          <Link 
                            href={`/projects/${project.id}`}
                            className="text-sm text-raven-400 hover:text-odin-400"
                          >
                          Manage →
                          </Link>
                      </td>
                    </tr>
                  );
                  })
                ) : (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-raven-500">
                      No projects found. Create your first project to get started.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-raven-800/50 mt-12">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between text-sm text-raven-600">
            <p>
              "From Hliðskjálf he could look out over all the worlds and see all things." — Prose Edda
            </p>
            <p>SPIFFE Trust Domain: ravenhelm.local</p>
          </div>
        </div>
      </footer>

      {/* The Norns - AI Chat Assistant */}
      <NornsChat />
      
      {/* LLM Settings Panel */}
      <LLMSettingsPanel
        isOpen={showLLMSettings}
        onClose={() => setShowLLMSettings(false)}
      />
      
      {/* New Project Wizard */}
      <NewProjectWizard
        isOpen={showNewProject}
        onClose={() => setShowNewProject(false)}
        onSuccess={() => {
          // Refetch projects after successful creation
          window.location.reload();
        }}
      />
    </div>
  );
}

function StatCard({ 
  label, 
  value, 
  icon: Icon,
  color 
}: { 
  label: string; 
  value: number; 
  icon: any;
  color: string;
}) {
  return (
    <motion.div 
      className="stat-card"
      whileHover={{ scale: 1.02 }}
      transition={{ type: "spring", stiffness: 400 }}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-raven-500">{label}</span>
        <Icon className={`w-5 h-5 ${color}`} />
      </div>
      <div className="text-3xl font-bold text-raven-100">{value}</div>
    </motion.div>
  );
}

function RealmStatus({ status }: { status: string }) {
  const styles = {
    active: "bg-healthy/20 text-healthy",
    idle: "bg-raven-600/20 text-raven-400",
    standby: "bg-degraded/20 text-degraded",
    cold: "bg-raven-700/20 text-raven-500",
  };
  
  return (
    <span className={`badge ${styles[status as keyof typeof styles] || styles.idle}`}>
      {status}
    </span>
  );
}

