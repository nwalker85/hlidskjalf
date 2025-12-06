"use client";

import Link from "next/link";
import { useState } from "react";
import { motion } from "framer-motion";
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
  RefreshCw
} from "lucide-react";
import { NornsChat } from "@/components/NornsChat";
import { ObservabilityWidget } from "@/components/observability";

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

// Mock data for demonstration
const MOCK_PROJECTS = [
  { id: "saaa", name: "SAAA", realm: "midgard", services: 4, health: "healthy" },
  { id: "ravenmaskos", name: "Ravenmaskos", realm: "midgard", services: 2, health: "healthy" },
  { id: "gitlab-sre", name: "GitLab SRE", realm: "vanaheim", services: 12, health: "healthy" },
];

const MOCK_STATS = {
  totalProjects: 3,
  totalServices: 18,
  portsAllocated: 24,
  healthyDeployments: 18,
  unhealthyDeployments: 0,
};

export default function HlidskjalfDashboard() {
  const [selectedRealm, setSelectedRealm] = useState<string | null>(null);

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
              
              <button className="btn-primary flex items-center gap-2">
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
          <StatCard 
            label="Projects" 
            value={MOCK_STATS.totalProjects} 
            icon={Server}
            color="text-odin-400"
          />
          <StatCard 
            label="Services" 
            value={MOCK_STATS.totalServices} 
            icon={Network}
            color="text-huginn-400"
          />
          <StatCard 
            label="Ports Allocated" 
            value={MOCK_STATS.portsAllocated} 
            icon={Activity}
            color="text-muninn-400"
          />
          <StatCard 
            label="Healthy" 
            value={MOCK_STATS.healthyDeployments} 
            icon={Shield}
            color="text-healthy"
          />
          <StatCard 
            label="Unhealthy" 
            value={MOCK_STATS.unhealthyDeployments} 
            icon={Activity}
            color="text-unhealthy"
          />
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
                {MOCK_PROJECTS.map((project) => {
                  const realm = REALMS.find(r => r.id === project.realm);
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
                      <td className="px-4 py-3 text-raven-300">{project.services}</td>
                      <td className="px-4 py-3">
                        <span className={`badge-${project.health}`}>
                          {project.health}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <button className="text-sm text-raven-400 hover:text-odin-400">
                          Manage →
                        </button>
                      </td>
                    </tr>
                  );
                })}
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

