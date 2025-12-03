"use client";

import { useState, useEffect, useCallback } from "react";
import { Settings, Zap, Wrench, Users, Check, Loader2, X, RefreshCw } from "lucide-react";

interface LLMModelConfig {
  provider: string;
  model: string;
  temperature: number;
}

interface LLMConfiguration {
  reasoning: LLMModelConfig;
  tools: LLMModelConfig;
  subagents: LLMModelConfig;
}

interface Provider {
  id: string;
  name: string;
  available: boolean;
  models: string[];
  default_model: string;
}

interface LLMConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessionId: string;
  onConfigChange?: (config: LLMConfiguration) => void;
}

const DEFAULT_CONFIG: LLMConfiguration = {
  reasoning: { provider: "ollama", model: "mistral-nemo:latest", temperature: 0.7 },
  tools: { provider: "ollama", model: "mistral-nemo:latest", temperature: 0.1 },
  subagents: { provider: "ollama", model: "mistral-nemo:latest", temperature: 0.5 },
};

const PURPOSE_INFO = {
  reasoning: {
    icon: Zap,
    title: "Reasoning Model",
    description: "Main agent for thinking, planning, and decision making. Use a capable model.",
    defaultTemp: 0.7,
  },
  tools: {
    icon: Wrench,
    title: "Tools Model",
    description: "Executes tool calls and parses results. Use a fast, precise model.",
    defaultTemp: 0.1,
  },
  subagents: {
    icon: Users,
    title: "Subagents Model",
    description: "Specialized tasks and subagent work. Balance cost and capability.",
    defaultTemp: 0.5,
  },
};

export function LLMConfigModal({
  isOpen,
  onClose,
  sessionId,
  onConfigChange,
}: LLMConfigModalProps) {
  const [config, setConfig] = useState<LLMConfiguration>(DEFAULT_CONFIG);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Fetch providers and current config
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // Fetch providers
      const providersResp = await fetch("/api/llm/config");
      if (providersResp.ok) {
        const data = await providersResp.json();
        setProviders(data.providers || []);
      }

      // Fetch current config for session
      if (sessionId) {
        const configResp = await fetch(`/api/llm/config?sessionId=${sessionId}`);
        if (configResp.ok) {
          const data = await configResp.json();
          if (data.reasoning) {
            setConfig({
              reasoning: data.reasoning,
              tools: data.tools,
              subagents: data.subagents,
            });
          }
        }
      }
    } catch (err) {
      console.error("Failed to fetch LLM config:", err);
      setError("Failed to load configuration");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    if (isOpen) {
      fetchData();
      setSuccess(false);
    }
  }, [isOpen, fetchData]);

  // Save configuration
  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);

    try {
      const resp = await fetch("/api/llm/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId, config }),
      });

      if (!resp.ok) {
        throw new Error("Failed to save configuration");
      }

      setSuccess(true);
      onConfigChange?.(config);

      // Auto-close after success
      setTimeout(() => {
        onClose();
      }, 1000);
    } catch (err) {
      console.error("Failed to save config:", err);
      setError("Failed to save configuration");
    } finally {
      setSaving(false);
    }
  };

  // Update a specific purpose's config
  const updatePurpose = (
    purpose: keyof LLMConfiguration,
    field: keyof LLMModelConfig,
    value: string | number
  ) => {
    setConfig((prev) => ({
      ...prev,
      [purpose]: {
        ...prev[purpose],
        [field]: value,
      },
    }));
    setSuccess(false);
  };

  // Get models for a provider
  const getModelsForProvider = (providerId: string): string[] => {
    const provider = providers.find((p) => p.id === providerId);
    return provider?.models || ["mistral-nemo:latest"];
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-700">
          <div className="flex items-center gap-3">
            <Settings className="w-5 h-5 text-amber-400" />
            <h2 className="text-lg font-semibold text-zinc-100">
              LLM Configuration
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchData}
              disabled={loading}
              className="p-2 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-lg transition-colors"
              title="Refresh"
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

        {/* Content */}
        <div className="p-6 space-y-6 overflow-y-auto max-h-[calc(90vh-140px)]">
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-amber-400 animate-spin" />
            </div>
          ) : (
            <>
              {/* Purpose sections */}
              {(Object.keys(PURPOSE_INFO) as Array<keyof typeof PURPOSE_INFO>).map(
                (purpose) => {
                  const info = PURPOSE_INFO[purpose];
                  const Icon = info.icon;
                  const purposeConfig = config[purpose];

                  return (
                    <div
                      key={purpose}
                      className="bg-zinc-800/50 border border-zinc-700/50 rounded-lg p-4 space-y-4"
                    >
                      {/* Section header */}
                      <div className="flex items-start gap-3">
                        <div className="p-2 bg-amber-400/10 rounded-lg">
                          <Icon className="w-5 h-5 text-amber-400" />
                        </div>
                        <div>
                          <h3 className="font-medium text-zinc-100">
                            {info.title}
                          </h3>
                          <p className="text-sm text-zinc-400">
                            {info.description}
                          </p>
                        </div>
                      </div>

                      {/* Config fields */}
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
                        {/* Provider */}
                        <div>
                          <label className="block text-xs font-medium text-zinc-400 mb-1">
                            Provider
                          </label>
                          <select
                            value={purposeConfig.provider}
                            onChange={(e) =>
                              updatePurpose(purpose, "provider", e.target.value)
                            }
                            className="w-full px-3 py-2 bg-zinc-900 border border-zinc-600 rounded-lg text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-amber-400/50"
                          >
                            {providers.map((p) => (
                              <option
                                key={p.id}
                                value={p.id}
                                disabled={!p.available}
                              >
                                {p.name} {!p.available && "(unavailable)"}
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
                            value={purposeConfig.model}
                            onChange={(e) =>
                              updatePurpose(purpose, "model", e.target.value)
                            }
                            className="w-full px-3 py-2 bg-zinc-900 border border-zinc-600 rounded-lg text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-amber-400/50"
                          >
                            {getModelsForProvider(purposeConfig.provider).map(
                              (model) => (
                                <option key={model} value={model}>
                                  {model}
                                </option>
                              )
                            )}
                          </select>
                        </div>

                        {/* Temperature */}
                        <div>
                          <label className="block text-xs font-medium text-zinc-400 mb-1">
                            Temperature: {purposeConfig.temperature.toFixed(1)}
                          </label>
                          <input
                            type="range"
                            min="0"
                            max="2"
                            step="0.1"
                            value={purposeConfig.temperature}
                            onChange={(e) =>
                              updatePurpose(
                                purpose,
                                "temperature",
                                parseFloat(e.target.value)
                              )
                            }
                            className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-amber-400"
                          />
                          <div className="flex justify-between text-xs text-zinc-500 mt-1">
                            <span>Precise</span>
                            <span>Creative</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                }
              )}

              {/* Session info */}
              <div className="text-xs text-zinc-500 pt-2">
                Configuration is session-scoped. Session: <code className="text-zinc-400">{sessionId || "default"}</code>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-zinc-700 bg-zinc-800/30">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-zinc-300 hover:text-zinc-100 hover:bg-zinc-700 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || loading}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-zinc-900 bg-amber-400 hover:bg-amber-300 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : success ? (
              <Check className="w-4 h-4" />
            ) : null}
            {success ? "Saved!" : saving ? "Saving..." : "Apply Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

