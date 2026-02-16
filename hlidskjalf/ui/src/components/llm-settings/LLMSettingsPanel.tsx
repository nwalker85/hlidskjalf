"use client";

import { useState, useEffect } from "react";
import { 
  Settings, 
  Plus, 
  Trash2, 
  Check, 
  X, 
  Loader2, 
  RefreshCw,
  AlertCircle,
  Server,
  Zap,
  Wrench,
  Users,
  Calendar,
  Database,
  ExternalLink,
  TestTube
} from "lucide-react";

interface Provider {
  id: string;
  name: string;
  provider_type: string;
  api_base_url?: string;
  enabled: boolean;
  validated_at?: string;
  models?: string[];
}

interface ModelConfig {
  interaction_type: string;
  provider_id: string;
  model_name: string;
  temperature: number;
  max_tokens?: number;
}

interface GlobalConfig {
  reasoning: ModelConfig;
  tools: ModelConfig;
  subagents: ModelConfig;
  planning: ModelConfig;
  embeddings: ModelConfig;
}

interface NewProviderForm {
  name: string;
  provider_type: "openai" | "anthropic" | "ollama" | "custom";
  api_base_url: string;
  api_key: string;
}

const INTERACTION_ICONS = {
  reasoning: { Icon: Zap, label: "Reasoning", desc: "Main supervisor thinking" },
  tools: { Icon: Wrench, label: "Tools", desc: "Tool calling and parsing" },
  subagents: { Icon: Users, label: "Subagents", desc: "Specialized tasks" },
  planning: { Icon: Calendar, label: "Planning", desc: "TODO generation" },
  embeddings: { Icon: Database, label: "Embeddings", desc: "Vector search" },
};

const PROVIDER_DEFAULTS: Record<string, Partial<NewProviderForm>> = {
  openai: { api_base_url: "https://api.openai.com/v1" },
  anthropic: { api_base_url: "https://api.anthropic.com/v1" },
  ollama: { api_base_url: "http://localhost:11434" },
  custom: { api_base_url: "" },
};

export function LLMSettingsPanel({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [activeTab, setActiveTab] = useState<"providers" | "config">("config");
  const [providers, setProviders] = useState<Provider[]>([]);
  const [config, setConfig] = useState<GlobalConfig | null>(null);
  const [models, setModels] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showAddProvider, setShowAddProvider] = useState(false);
  const [newProvider, setNewProvider] = useState<NewProviderForm>({
    name: "",
    provider_type: "ollama",
    api_base_url: "http://localhost:11434",
    api_key: "",
  });
  
  // Load data
  useEffect(() => {
    if (isOpen) {
      loadData();
    }
  }, [isOpen]);

  // Clear messages after delay
  useEffect(() => {
    if (success) {
      const timer = setTimeout(() => setSuccess(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [success]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Load providers
      const providersRes = await fetch("/api/llm/providers");
      if (providersRes.ok) {
        const providersData = await providersRes.json();
        setProviders(Array.isArray(providersData) ? providersData : []);
        
        // Load models for each provider
        const modelsMap: Record<string, string[]> = {};
        const providerArray = Array.isArray(providersData) ? providersData : [];
        for (const provider of providerArray) {
          try {
            const modelsRes = await fetch(`/api/llm/providers/${provider.id}/models`);
            if (modelsRes.ok) {
              const modelsData = await modelsRes.json();
              modelsMap[provider.id] = Array.isArray(modelsData) 
                ? modelsData.map((m: any) => m.model_name || m.name || m)
                : [];
            }
          } catch (e) {
            console.error(`Failed to load models for ${provider.name}:`, e);
          }
        }
        setModels(modelsMap);
      } else {
        // Fallback: create default providers if API returns error
        setProviders([]);
        setModels({});
      }
      
      // Load config
      const configRes = await fetch("/api/llm/config");
      if (configRes.ok) {
        const configData = await configRes.json();
        setConfig(configData);
      } else {
        // Set empty config state if API returns error
        setConfig(null);
      }
    } catch (e) {
      console.error("Failed to load LLM settings:", e);
      setError("Failed to load settings. Backend may be unavailable.");
    } finally {
      setLoading(false);
    }
  };
  
  const addProvider = async () => {
    if (!newProvider.name || !newProvider.api_base_url) {
      setError("Provider name and API URL are required");
      return;
    }
    
    setSaving(true);
    setError(null);
    
    try {
      const res = await fetch("/api/llm/providers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newProvider.name,
          provider_type: newProvider.provider_type,
          api_base_url: newProvider.api_base_url,
          api_key: newProvider.api_key || undefined,
        }),
      });
      
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || "Failed to add provider");
      }
      
      setSuccess(`Provider "${newProvider.name}" added successfully`);
      setShowAddProvider(false);
      setNewProvider({
        name: "",
        provider_type: "ollama",
        api_base_url: "http://localhost:11434",
        api_key: "",
      });
      
      // Reload providers
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add provider");
    } finally {
      setSaving(false);
    }
  };

  const updateInteractionConfig = async (
    interactionType: keyof GlobalConfig,
    updates: Partial<ModelConfig>
  ) => {
    if (!config) return;
    
    const currentConfig = config[interactionType];
    
    // If provider is changing, we must also update the model
    // Don't merge old model with new provider - require explicit model selection
    const isProviderChange = updates.provider_id && updates.provider_id !== currentConfig?.provider_id;
    
    // For partial updates (just temperature), send only what's changing
    // For provider changes without model, the backend will return an error
    const payload = isProviderChange && !updates.model_name
      ? updates  // Send only provider_id, backend will require model selection
      : updates; // Send only the fields being updated
    
    setSaving(true);
    try {
      const res = await fetch(`/api/llm/config/${interactionType}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        const errorMessage = errorData.detail || errorData.error || "Failed to update configuration";
        throw new Error(errorMessage);
      }
      
      const updatedConfig = await res.json();
      setConfig({
        ...config,
        [interactionType]: updatedConfig,
      });
    } catch (e) {
      console.error("Failed to update config:", e);
      setError(e instanceof Error ? e.message : "Failed to save configuration");
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="relative bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-700">
          <div className="flex items-center gap-3">
            <Settings className="w-5 h-5 text-odin-400" />
            <h2 className="text-lg font-semibold text-zinc-100">
              LLM Configuration
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={loadData}
              disabled={loading}
              className="p-2 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-lg transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
            <button
              onClick={onClose}
              className="p-2 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-lg transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-zinc-700 px-6">
          <button
            onClick={() => setActiveTab("config")}
            className={`px-4 py-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === "config"
                ? "border-odin-400 text-odin-400"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Model Configuration
          </button>
          <button
            onClick={() => setActiveTab("providers")}
            className={`px-4 py-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === "providers"
                ? "border-odin-400 text-odin-400"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Providers
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              {error}
              <button 
                onClick={() => setError(null)}
                className="ml-auto text-red-400 hover:text-red-300"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
          
          {success && (
            <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 text-sm flex items-center gap-2">
              <Check className="w-4 h-4" />
              {success}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-odin-400 animate-spin" />
            </div>
          ) : activeTab === "config" && config ? (
            <div className="space-y-4">
              {Object.entries(INTERACTION_ICONS).map(([key, { Icon, label, desc }]) => {
                const interactionType = key as keyof GlobalConfig;
                const interactionConfig = config[interactionType];
                const provider = providers.find(p => p.id === interactionConfig.provider_id);
                const availableModels = models[interactionConfig.provider_id] || [];

                return (
                  <div
                    key={key}
                    className="bg-zinc-800/50 border border-zinc-700/50 rounded-lg p-4"
                  >
                    <div className="flex items-start gap-3 mb-4">
                      <div className="p-2 bg-odin-400/10 rounded-lg">
                        <Icon className="w-5 h-5 text-odin-400" />
                      </div>
                      <div>
                        <h3 className="font-medium text-zinc-100">{label}</h3>
                        <p className="text-sm text-zinc-400">{desc}</p>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {/* Provider */}
                      <div>
                        <label className="block text-xs font-medium text-zinc-400 mb-1">
                          Provider
                        </label>
                        <select
                          value={interactionConfig.provider_id}
                          onChange={(e) => {
                            const newProviderId = e.target.value;
                            const newProviderModels = models[newProviderId] || [];
                            // When provider changes, auto-select first model from new provider
                            if (newProviderId !== interactionConfig.provider_id && newProviderModels.length > 0) {
                              updateInteractionConfig(interactionType, {
                                provider_id: newProviderId,
                                model_name: newProviderModels[0],
                              });
                            } else if (newProviderModels.length === 0) {
                              setError(`No models available for selected provider. Load models first.`);
                            }
                          }}
                          className="w-full px-3 py-2 bg-zinc-900 border border-zinc-600 rounded-lg text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-odin-400/50"
                        >
                          {providers.map((p) => (
                            <option key={p.id} value={p.id} disabled={!p.enabled}>
                              {p.name} {!p.enabled && "(disabled)"}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* Model */}
                      <div>
                        <label className="block text-xs font-medium text-zinc-400 mb-1">
                          Model
                        </label>
                        <select
                          value={interactionConfig.model_name}
                          onChange={(e) =>
                            updateInteractionConfig(interactionType, {
                              model_name: e.target.value,
                            })
                          }
                          className="w-full px-3 py-2 bg-zinc-900 border border-zinc-600 rounded-lg text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-odin-400/50"
                        >
                          {availableModels.map((model) => (
                            <option key={model} value={model}>
                              {model}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* Temperature */}
                      <div>
                        <label className="block text-xs font-medium text-zinc-400 mb-1">
                          Temperature: {interactionConfig.temperature.toFixed(1)}
                        </label>
                        <input
                          type="range"
                          min="0"
                          max="2"
                          step="0.1"
                          value={interactionConfig.temperature}
                          onChange={(e) =>
                            updateInteractionConfig(interactionType, {
                              temperature: parseFloat(e.target.value),
                            })
                          }
                          className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-odin-400"
                        />
                        <div className="flex justify-between text-xs text-zinc-500 mt-1">
                          <span>Precise</span>
                          <span>Creative</span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : activeTab === "config" && !config ? (
            <div className="flex flex-col items-center justify-center py-12 text-zinc-400">
              <AlertCircle className="w-12 h-12 mb-4 text-zinc-600" />
              <p className="text-lg font-medium mb-2">No Configuration Found</p>
              <p className="text-sm text-zinc-500 text-center max-w-md">
                LLM configuration is not yet initialized. Add providers first, 
                then configure models for each interaction type.
              </p>
              <button
                onClick={() => setActiveTab("providers")}
                className="mt-4 px-4 py-2 bg-odin-500/20 text-odin-400 rounded-lg hover:bg-odin-500/30 transition-colors"
              >
                Add Providers
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Add Provider Button */}
              <div className="flex justify-end">
                <button
                  onClick={() => setShowAddProvider(true)}
                  className="flex items-center gap-2 px-3 py-2 bg-odin-500/20 text-odin-400 rounded-lg hover:bg-odin-500/30 transition-colors text-sm"
                >
                  <Plus className="w-4 h-4" />
                  Add Provider
                </button>
              </div>

              {/* Add Provider Form */}
              {showAddProvider && (
                <div className="bg-zinc-800/80 border border-odin-500/30 rounded-lg p-4 space-y-4">
                  <h4 className="font-medium text-zinc-100 flex items-center gap-2">
                    <Plus className="w-4 h-4 text-odin-400" />
                    Add New Provider
                  </h4>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-zinc-400 mb-1">
                        Provider Name
                      </label>
                      <input
                        type="text"
                        value={newProvider.name}
                        onChange={(e) => setNewProvider(p => ({ ...p, name: e.target.value }))}
                        placeholder="e.g., My Ollama Server"
                        className="w-full px-3 py-2 bg-zinc-900 border border-zinc-600 rounded-lg text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-odin-400/50"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-xs font-medium text-zinc-400 mb-1">
                        Provider Type
                      </label>
                      <select
                        value={newProvider.provider_type}
                        onChange={(e) => {
                          const type = e.target.value as NewProviderForm["provider_type"];
                          setNewProvider(p => ({
                            ...p,
                            provider_type: type,
                            api_base_url: PROVIDER_DEFAULTS[type]?.api_base_url || "",
                          }));
                        }}
                        className="w-full px-3 py-2 bg-zinc-900 border border-zinc-600 rounded-lg text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-odin-400/50"
                      >
                        <option value="ollama">Ollama</option>
                        <option value="openai">OpenAI</option>
                        <option value="anthropic">Anthropic</option>
                        <option value="custom">Custom (OpenAI-compatible)</option>
                      </select>
                    </div>
                    
                    <div>
                      <label className="block text-xs font-medium text-zinc-400 mb-1">
                        API Base URL
                      </label>
                      <input
                        type="text"
                        value={newProvider.api_base_url}
                        onChange={(e) => setNewProvider(p => ({ ...p, api_base_url: e.target.value }))}
                        placeholder="http://localhost:11434"
                        className="w-full px-3 py-2 bg-zinc-900 border border-zinc-600 rounded-lg text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-odin-400/50"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-xs font-medium text-zinc-400 mb-1">
                        API Key {newProvider.provider_type === "ollama" && <span className="text-zinc-500">(optional)</span>}
                      </label>
                      <input
                        type="password"
                        value={newProvider.api_key}
                        onChange={(e) => setNewProvider(p => ({ ...p, api_key: e.target.value }))}
                        placeholder={newProvider.provider_type === "ollama" ? "Optional" : "sk-..."}
                        className="w-full px-3 py-2 bg-zinc-900 border border-zinc-600 rounded-lg text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-odin-400/50"
                      />
                    </div>
                  </div>
                  
                  <div className="flex justify-end gap-2 pt-2">
                    <button
                      onClick={() => setShowAddProvider(false)}
                      className="px-3 py-1.5 text-sm text-zinc-400 hover:text-zinc-200 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={addProvider}
                      disabled={saving || !newProvider.name || !newProvider.api_base_url}
                      className="flex items-center gap-2 px-3 py-1.5 text-sm bg-odin-500 text-zinc-900 rounded-lg hover:bg-odin-400 transition-colors disabled:opacity-50"
                    >
                      {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                      Add Provider
                    </button>
                  </div>
                </div>
              )}

              {/* Provider List */}
              {providers.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-zinc-400">
                  <Server className="w-12 h-12 mb-4 text-zinc-600" />
                  <p className="text-lg font-medium mb-2">No Providers Configured</p>
                  <p className="text-sm text-zinc-500 text-center">
                    Add an LLM provider to get started with AI model configuration.
                  </p>
                </div>
              ) : (
                providers.map((provider) => {
                  const providerModels = models[provider.id] || provider.models || [];
                  return (
                    <div
                      key={provider.id}
                      className="bg-zinc-800/50 border border-zinc-700/50 rounded-lg p-4"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`p-2 rounded-lg ${provider.enabled ? "bg-green-500/10" : "bg-zinc-700/50"}`}>
                            <Server className={`w-5 h-5 ${provider.enabled ? "text-green-400" : "text-zinc-500"}`} />
                          </div>
                          <div>
                            <h3 className="font-medium text-zinc-100 flex items-center gap-2">
                              {provider.name}
                              {provider.enabled ? (
                                <span className="text-xs px-2 py-0.5 bg-green-500/20 text-green-400 rounded-full">
                                  Active
                                </span>
                              ) : (
                                <span className="text-xs px-2 py-0.5 bg-zinc-700 text-zinc-400 rounded-full">
                                  Disabled
                                </span>
                              )}
                            </h3>
                            <p className="text-sm text-zinc-400">{provider.provider_type}</p>
                            {provider.api_base_url && (
                              <p className="text-xs text-zinc-500 mt-1 font-mono truncate max-w-md">
                                {provider.api_base_url}
                              </p>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {provider.validated_at && (
                            <span className="text-xs text-zinc-500">
                              Validated {new Date(provider.validated_at).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      </div>
                      
                      {/* Models */}
                      {providerModels.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-zinc-700/50">
                          <p className="text-xs text-zinc-400 mb-2">Available Models ({providerModels.length})</p>
                          <div className="flex flex-wrap gap-2">
                            {providerModels.slice(0, 8).map((model) => (
                              <span
                                key={model}
                                className="text-xs px-2 py-1 bg-zinc-700/50 text-zinc-300 rounded"
                              >
                                {model}
                              </span>
                            ))}
                            {providerModels.length > 8 && (
                              <span className="text-xs px-2 py-1 text-zinc-500">
                                +{providerModels.length - 8} more
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-zinc-700 bg-zinc-800/30">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-zinc-300 hover:text-zinc-100 hover:bg-zinc-700 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

