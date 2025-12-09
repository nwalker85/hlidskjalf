"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { 
  Wrench, 
  Cpu, 
  History, 
  Sparkles, 
  Brain, 
  Target, 
  Folder, 
  Globe, 
  GitBranch, 
  Bot,
  Plus,
  RefreshCw,
  Search,
  ChevronRight,
  Check,
  X,
  ExternalLink
} from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";

interface ToolParameter {
  name: string;
  type: string;
  description?: string;
  required?: boolean;
  default?: unknown;
}

interface Tool {
  name: string;
  description: string;
  category: string;
  source: string;
  enabled: boolean;
  parameters: ToolParameter[];
  norn?: string;
  tags: string[];
}

interface ToolsResponse {
  tools: Tool[];
  total: number;
  categories: Record<string, number>;
}

const CATEGORY_CONFIG: Record<string, { label: string; icon: React.ElementType; color: string }> = {
  platform: { label: "Platform", icon: Cpu, color: "text-odin-400" },
  history: { label: "History", icon: History, color: "text-amber-400" },
  planning: { label: "Planning", icon: Sparkles, color: "text-purple-400" },
  memory: { label: "Memory", icon: Brain, color: "text-huginn-400" },
  skills: { label: "Skills", icon: Target, color: "text-emerald-400" },
  workspace: { label: "Workspace", icon: Folder, color: "text-blue-400" },
  web: { label: "Web", icon: Globe, color: "text-cyan-400" },
  graph: { label: "Graph", icon: GitBranch, color: "text-pink-400" },
  llm: { label: "LLM", icon: Bot, color: "text-violet-400" },
  subagents: { label: "Subagents", icon: Bot, color: "text-orange-400" },
  mcp: { label: "MCP", icon: ExternalLink, color: "text-teal-400" },
  custom: { label: "Custom", icon: Wrench, color: "text-raven-400" },
};

const NORN_COLORS: Record<string, string> = {
  verdandi: "bg-odin-500/20 text-odin-300 border-odin-500/30",
  urd: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  skuld: "bg-purple-500/20 text-purple-300 border-purple-500/30",
};

function ToolCard({ tool, onToggle }: { tool: Tool; onToggle: (name: string, enabled: boolean) => void }) {
  const categoryConfig = CATEGORY_CONFIG[tool.category] || CATEGORY_CONFIG.custom;
  const Icon = categoryConfig.icon;

  return (
    <Card className="card-hover group">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg bg-raven-800/50 ${categoryConfig.color}`}>
              <Icon className="w-4 h-4" />
            </div>
            <div>
              <CardTitle className="text-sm font-mono text-raven-100 group-hover:text-odin-300 transition-colors">
                {tool.name}
              </CardTitle>
              <CardDescription className="text-xs text-raven-400">
                {tool.source}
              </CardDescription>
            </div>
          </div>
          <Switch
            checked={tool.enabled}
            onCheckedChange={(checked) => onToggle(tool.name, checked)}
          />
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-raven-300 mb-3 line-clamp-2">
          {tool.description}
        </p>
        <div className="flex flex-wrap gap-2">
          {tool.norn && (
            <span className={`px-2 py-0.5 text-xs rounded-full border ${NORN_COLORS[tool.norn] || "bg-raven-800 text-raven-300"}`}>
              {tool.norn.charAt(0).toUpperCase() + tool.norn.slice(1)}
            </span>
          )}
          {tool.parameters.length > 0 && (
            <span className="px-2 py-0.5 text-xs rounded-full bg-raven-800 text-raven-300">
              {tool.parameters.length} params
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function CategorySidebar({ 
  categories, 
  selected, 
  onSelect 
}: { 
  categories: Record<string, number>; 
  selected: string | null;
  onSelect: (cat: string | null) => void;
}) {
  return (
    <div className="w-64 shrink-0">
      <div className="sticky top-4">
        <h3 className="text-sm font-semibold text-raven-300 mb-3 uppercase tracking-wider">Categories</h3>
        <div className="space-y-1">
          <button
            onClick={() => onSelect(null)}
            className={`w-full flex items-center justify-between px-3 py-2 rounded-lg transition-colors ${
              selected === null
                ? "bg-odin-500/20 text-odin-300"
                : "text-raven-300 hover:bg-raven-800/50"
            }`}
          >
            <span className="flex items-center gap-2">
              <Wrench className="w-4 h-4" />
              All Tools
            </span>
            <span className="text-xs text-raven-500">
              {Object.values(categories).reduce((a, b) => a + b, 0)}
            </span>
          </button>
          {Object.entries(categories).map(([cat, count]) => {
            const config = CATEGORY_CONFIG[cat] || CATEGORY_CONFIG.custom;
            const Icon = config.icon;
            return (
              <button
                key={cat}
                onClick={() => onSelect(cat)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg transition-colors ${
                  selected === cat
                    ? "bg-odin-500/20 text-odin-300"
                    : "text-raven-300 hover:bg-raven-800/50"
                }`}
              >
                <span className={`flex items-center gap-2 ${config.color}`}>
                  <Icon className="w-4 h-4" />
                  {config.label}
                </span>
                <span className="text-xs text-raven-500">{count}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <Card key={i} className="card">
          <CardHeader className="pb-2">
            <div className="flex items-center gap-3">
              <Skeleton className="w-10 h-10 rounded-lg" />
              <div className="space-y-2">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-3 w-16" />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <Skeleton className="h-10 w-full mb-3" />
            <div className="flex gap-2">
              <Skeleton className="h-5 w-16 rounded-full" />
              <Skeleton className="h-5 w-20 rounded-full" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function ToolsPage() {
  const [tools, setTools] = useState<Tool[]>([]);
  const [categories, setCategories] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const fetchTools = async () => {
    try {
      const params = new URLSearchParams();
      if (selectedCategory) params.append("category", selectedCategory);
      
      const response = await fetch(`/api/tools?${params}`);
      const data: ToolsResponse = await response.json();
      
      setTools(data.tools);
      setCategories(data.categories);
    } catch (error) {
      console.error("Failed to fetch tools:", error);
      toast.error("Failed to load tools");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTools();
  }, [selectedCategory]);

  const handleToggle = async (name: string, enabled: boolean) => {
    try {
      const response = await fetch(`/api/tools/${name}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });

      if (response.ok) {
        setTools((prev) =>
          prev.map((t) => (t.name === name ? { ...t, enabled } : t))
        );
        toast.success(`Tool ${enabled ? "enabled" : "disabled"}`);
      } else {
        throw new Error("Failed to update tool");
      }
    } catch {
      toast.error("Failed to update tool");
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchTools();
    setRefreshing(false);
    toast.success("Tools refreshed");
  };

  const filteredTools = tools.filter((tool) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      tool.name.toLowerCase().includes(query) ||
      tool.description.toLowerCase().includes(query)
    );
  });

  return (
    <div className="min-h-screen bg-raven-950">
      {/* Header */}
      <header className="border-b border-raven-800 bg-raven-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link 
                href="/norns" 
                className="text-raven-400 hover:text-odin-300 transition-colors"
              >
                <ChevronRight className="w-5 h-5 rotate-180" />
              </Link>
              <div>
                <h1 className="text-xl font-semibold text-raven-100">Tool Registry</h1>
                <p className="text-sm text-raven-400">
                  Manage Norns tools and capabilities
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={refreshing}
                className="border-raven-700 hover:border-odin-500/50"
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? "animate-spin" : ""}`} />
                Refresh
              </Button>
              <Button size="sm" className="bg-odin-500 hover:bg-odin-400 text-raven-950">
                <Plus className="w-4 h-4 mr-2" />
                Add Tool
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-6">
        <div className="flex gap-8">
          {/* Sidebar */}
          <CategorySidebar
            categories={categories}
            selected={selectedCategory}
            onSelect={setSelectedCategory}
          />

          {/* Tools Grid */}
          <div className="flex-1">
            {/* Search */}
            <div className="mb-6">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-raven-500" />
                <Input
                  placeholder="Search tools..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 bg-raven-900 border-raven-700 focus:border-odin-500/50"
                />
              </div>
            </div>

            {/* Stats Row */}
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="stat-card">
                <div className="text-2xl font-bold text-odin-300">
                  {tools.length}
                </div>
                <div className="text-sm text-raven-400">Total Tools</div>
              </div>
              <div className="stat-card">
                <div className="text-2xl font-bold text-emerald-400">
                  {tools.filter((t) => t.enabled).length}
                </div>
                <div className="text-sm text-raven-400">Enabled</div>
              </div>
              <div className="stat-card">
                <div className="text-2xl font-bold text-raven-400">
                  {Object.keys(categories).length}
                </div>
                <div className="text-sm text-raven-400">Categories</div>
              </div>
            </div>

            {/* Tools */}
            {loading ? (
              <LoadingSkeleton />
            ) : filteredTools.length === 0 ? (
              <div className="text-center py-12 text-raven-400">
                <Wrench className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No tools found</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredTools.map((tool) => (
                  <ToolCard
                    key={tool.name}
                    tool={tool}
                    onToggle={handleToggle}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

