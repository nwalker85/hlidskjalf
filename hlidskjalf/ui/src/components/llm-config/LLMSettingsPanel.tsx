"use client";

import React, { useState, useEffect } from "react";
import { X, Settings, Check, AlertCircle, Loader2 } from "lucide-react";

interface LLMProvider {
  id: string;
  name: string;
  provider_type: string;
  enabled: boolean;
  validated_at: string | null;
  models: string[];
}

interface ModelConfig {
  provider_id: string;
  provider_name: string;
  model_name: string;
  temperature: number;
}

interface GlobalConfig {
  [key: string]: ModelConfig;
}

interface LLMSettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function LLMSettingsPanel({ isOpen, onClose }: LLMSettingsPanelProps) {
  const [activeTab, setActiveTab] = useState<"config" | "providers">("config");
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [config, setConfig] = useState<GlobalConfig>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch providers and config on mount
  useEffect(() => {
    if (isOpen) {
      fetchData();
    }
  }, [isOpen]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Fetch providers
      const providersResp = await fetch("/api/llm/providers");
      if (!providersResp.ok) throw new Error("Failed to fetch providers");
      const providersData = await providersResp.json();
      setProviders(Array.isArray(providersData) ? providersData : providersData.providers || []);

      // Fetch config
      const configResp = await fetch("/api/llm/config");
      if (!configResp.ok) throw new Error("Failed to fetch config");
      const configData = await configResp.json();
      setConfig(configData || {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  const updateInteractionConfig = async (
    interactionType: string,
    providerId: string,
    modelName: string,
    temperature: number
  ) => {
    setSaving(interactionType);
    setError(null);

    try {
      const resp = await fetch(`/api/llm/config/${interactionType}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider_id: providerId,
          model_name: modelName,
          temperature,
        }),
      });

      if (!resp.ok) {
        const errorData = await resp.json();
        throw new Error(errorData.error || "Failed to update config");
      }

      // Refresh config
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update config");
    } finally {
      setSaving(null);
    }
  };

  const handleModelChange = async (
    interactionType: string,
    providerId: string,
    modelName: string
  ) => {
    const currentConfig = config[interactionType];
    await updateInteractionConfig(
      interactionType,
      providerId,
      modelName,
      currentConfig?.temperature || 0.7
    );
  };

  const handleTemperatureChange = async (
    interactionType: string,
    temperature: number
  ) => {
    const currentConfig = config[interactionType];
    if (!currentConfig) return;

    await updateInteractionConfig(
      interactionType,
      currentConfig.provider_id,
      currentConfig.model_name,
      temperature
    );
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-gray-900 rounded-lg shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col border border-gray-700">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <Settings className="w-6 h-6 text-blue-400" />
            <h2 className="text-2xl font-bold text-white">LLM Configuration</h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-700 px-6">
          <button
            onClick={() => setActiveTab("config")}
            className={`px-4 py-3 font-medium transition-colors ${
              activeTab === "config"
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-white"
            }`}
          >
            Model Configuration
          </button>
          <button
            onClick={() => setActiveTab("providers")}
            className={`px-4 py-3 font-medium transition-colors ${
              activeTab === "providers"
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-white"
            }`}
          >
            Providers
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 p-4 bg-red-900/20 border border-red-500 rounded-lg flex items-center gap-2 text-red-400">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
            </div>
          ) : activeTab === "config" ? (
            <ConfigTab
              config={config}
              providers={providers}
              saving={saving}
              onModelChange={handleModelChange}
              onTemperatureChange={handleTemperatureChange}
            />
          ) : (
            <ProvidersTab providers={providers} onRefresh={fetchData} />
          )}
        </div>
      </div>
    </div>
  );
}

// Config Tab Component
function ConfigTab({
  config,
  providers,
  saving,
  onModelChange,
  onTemperatureChange,
}: {
  config: GlobalConfig;
  providers: LLMProvider[];
  saving: string | null;
  onModelChange: (type: string, providerId: string, model: string) => void;
  onTemperatureChange: (type: string, temp: number) => void;
}) {
  const interactionTypes = [
    {
      key: "reasoning",
      label: "Reasoning",
      description: "Main supervisor thinking and decision making",
    },
    {
      key: "tools",
      label: "Tools",
      description: "Tool calling and result parsing",
    },
    {
      key: "subagents",
      label: "Subagents",
      description: "Specialized agent tasks",
    },
    {
      key: "planning",
      label: "Planning",
      description: "TODO generation and planning",
    },
    {
      key: "embeddings",
      label: "Embeddings",
      description: "Vector embeddings for RAG",
    },
  ];

  return (
    <div className="space-y-6">
      {interactionTypes.map((type) => {
        const currentConfig = config[type.key];
        const currentProvider = providers.find(
          (p) => p.id === currentConfig?.provider_id
        );

        return (
          <div
            key={type.key}
            className="bg-gray-800 rounded-lg p-5 border border-gray-700"
          >
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                  {type.label}
                  {saving === type.key && (
                    <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                  )}
                </h3>
                <p className="text-sm text-gray-400 mt-1">{type.description}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Provider Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Provider
                </label>
                <select
                  value={currentProvider?.id || ""}
                  onChange={(e) => {
                    const provider = providers.find((p) => p.id === e.target.value);
                    if (provider && provider.models.length > 0) {
                      onModelChange(type.key, provider.id, provider.models[0]);
                    }
                  }}
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={saving === type.key}
                >
                  {providers.map((provider) => (
                    <option key={provider.id} value={provider.id}>
                      {provider.name} ({provider.provider_type})
                    </option>
                  ))}
                </select>
              </div>

              {/* Model Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Model
                </label>
                <select
                  value={currentConfig?.model_name || ""}
                  onChange={(e) =>
                    onModelChange(
                      type.key,
                      currentConfig.provider_id,
                      e.target.value
                    )
                  }
                  className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={saving === type.key || !currentProvider}
                >
                  {currentProvider?.models.sort((a, b) => {
                    // Sort models: GPT-5.1 > GPT-5 > GPT-4.1 > GPT-4o > GPT-4 > GPT-3.5 > embeddings
                    const getModelPriority = (model: string) => {
                      if (model.startsWith("gpt-5.1")) return 10;
                      if (model.startsWith("gpt-5")) return 9;
                      if (model.startsWith("gpt-4.1")) return 8;
                      if (model.startsWith("gpt-4o")) return 7;
                      if (model.startsWith("gpt-4")) return 6;
                      if (model.startsWith("gpt-3")) return 5;
                      if (model.includes("embedding")) return 1;
                      return 3;
                    };
                    
                    const priorityA = getModelPriority(a);
                    const priorityB = getModelPriority(b);
                    
                    if (priorityA !== priorityB) {
                      return priorityB - priorityA; // Higher priority first
                    }
                    
                    // Within same priority, sort alphabetically
                    return a.localeCompare(b);
                  }).map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              </div>

              {/* Temperature Slider */}
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Temperature: {currentConfig?.temperature?.toFixed(2) || "0.70"}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={currentConfig?.temperature || 0.7}
                  onChange={(e) =>
                    onTemperatureChange(type.key, parseFloat(e.target.value))
                  }
                  className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                  disabled={saving === type.key}
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>Deterministic</span>
                  <span>Creative</span>
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Providers Tab Component
function ProvidersTab({
  providers,
  onRefresh,
}: {
  providers: LLMProvider[];
  onRefresh: () => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <p className="text-gray-400">
          Manage LLM providers. Add new providers via API.
        </p>
        <button
          onClick={onRefresh}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
        >
          Refresh
        </button>
      </div>

      {providers.map((provider) => (
        <div
          key={provider.id}
          className="bg-gray-800 rounded-lg p-5 border border-gray-700"
        >
          <div className="flex items-start justify-between mb-3">
            <div>
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                {provider.name}
                {provider.enabled ? (
                  <Check className="w-5 h-5 text-green-400" />
                ) : (
                  <AlertCircle className="w-5 h-5 text-yellow-400" />
                )}
              </h3>
              <p className="text-sm text-gray-400 mt-1">
                Type: {provider.provider_type}
              </p>
              {provider.validated_at && (
                <p className="text-xs text-gray-500 mt-1">
                  Last validated: {new Date(provider.validated_at).toLocaleString()}
                </p>
              )}
            </div>
          </div>

          <div>
            <p className="text-sm font-medium text-gray-300 mb-2">
              Available Models ({provider.models.length})
            </p>
            <div className="flex flex-wrap gap-2">
              {provider.models.slice(0, 10).map((model) => (
                <span
                  key={model}
                  className="px-2 py-1 bg-gray-700 text-gray-300 text-xs rounded"
                >
                  {model}
                </span>
              ))}
              {provider.models.length > 10 && (
                <span className="px-2 py-1 text-gray-500 text-xs">
                  +{provider.models.length - 10} more
                </span>
              )}
            </div>
          </div>
        </div>
      ))}

      {providers.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          No providers configured. Add one via API.
        </div>
      )}
    </div>
  );
}

