"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Check, ChevronDown, RefreshCw, Server, Cloud, Cpu, AlertCircle, Copy, CheckCircle } from "lucide-react";

interface ProviderStatus {
  name: string;
  online: boolean;
  url: string;
  models: string[];
  current_model: string | null;
  error: string | null;
}

interface LLMConfig {
  current_provider: string;
  current_model: string;
  providers: ProviderStatus[];
}

const PROVIDER_ICONS: Record<string, React.ReactNode> = {
  ollama: <Cpu className="w-4 h-4" />,
  lmstudio: <Server className="w-4 h-4" />,
  openai: <Cloud className="w-4 h-4" />,
};

const PROVIDER_LABELS: Record<string, string> = {
  ollama: "Ollama",
  lmstudio: "LM Studio",
  openai: "OpenAI",
};

export function LLMSelector() {
  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [showInstructions, setShowInstructions] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch("/api/llm/config");
      if (!resp.ok) throw new Error("Failed to fetch");
      const data: LLMConfig = await resp.json();
      setConfig(data);
      setSelectedProvider(data.current_provider);
      setSelectedModel(data.current_model);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleProviderChange = (provider: string) => {
    setSelectedProvider(provider);
    setShowInstructions(false);
    const providerStatus = config?.providers.find((p) => p.name === provider);
    if (providerStatus && providerStatus.models.length > 0) {
      setSelectedModel(providerStatus.current_model || providerStatus.models[0]);
    }
  };

  // Generate the env commands for the selected configuration
  const getEnvCommands = () => {
    const lines = [`LLM_PROVIDER=${selectedProvider}`];
    if (selectedProvider === "ollama") {
      lines.push(`OLLAMA_CHAT_MODEL=${selectedModel}`);
    } else if (selectedProvider === "lmstudio") {
      lines.push(`LMSTUDIO_MODEL=${selectedModel}`);
    } else if (selectedProvider === "openai") {
      lines.push(`NORNS_MODEL=${selectedModel}`);
    }
    return lines.join("\n");
  };

  const handleApply = () => {
    // Show instructions instead of trying to apply (requires env change + restart)
    setShowInstructions(true);
  };

  const handleCopyEnv = async () => {
    await navigator.clipboard.writeText(getEnvCommands());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const currentProviderStatus = config?.providers.find(
    (p) => p.name === config.current_provider
  );

  const hasChanges = selectedProvider !== config?.current_provider || 
                     selectedModel !== config?.current_model;

  if (loading && !config) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 text-sm text-zinc-400">
        <RefreshCw className="w-4 h-4 animate-spin" />
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Trigger Button */}
      <button
        onClick={() => {
          setIsOpen(!isOpen);
          setShowInstructions(false);
        }}
        className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-zinc-800/60 border border-zinc-700/50 hover:bg-zinc-700/60 hover:border-zinc-600/50 transition-all"
      >
        <span className={`w-2 h-2 rounded-full ${
          currentProviderStatus?.online ? "bg-emerald-500" : "bg-amber-500"
        }`} />
        <span className="text-zinc-400">
          {PROVIDER_ICONS[config?.current_provider || "ollama"]}
        </span>
        <span className="text-xs font-medium text-zinc-200">
          {PROVIDER_LABELS[config?.current_provider || "ollama"]}
        </span>
        <span className="text-[10px] text-zinc-500 hidden sm:inline">
          {config?.current_model?.split(':')[0] || ''}
        </span>
        <ChevronDown className={`w-3 h-3 text-zinc-500 transition-transform ${isOpen ? "rotate-180" : ""}`} />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute top-full mt-2 right-0 w-80 bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl z-[9999]">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
            <span className="text-sm font-semibold text-zinc-200">LLM Provider</span>
            <button
              onClick={fetchConfig}
              className="p-1 hover:bg-zinc-800 rounded"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 text-zinc-500 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>

          {error && (
            <div className="px-4 py-2 bg-red-900/20 border-b border-red-800/30 flex items-center gap-2 text-red-400 text-xs">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Providers */}
          <div className="p-2 space-y-1">
            {config?.providers.map((provider) => {
              const isSelected = selectedProvider === provider.name;
              const isCurrent = config.current_provider === provider.name;
              
              return (
                <button
                  key={provider.name}
                  onClick={() => handleProviderChange(provider.name)}
                  className={`w-full flex items-center gap-3 px-3 py-3 rounded-md transition-all text-left ${
                    isSelected
                      ? "bg-blue-600/20 ring-1 ring-blue-500/50"
                      : "hover:bg-zinc-800"
                  }`}
                >
                  {/* Status dot */}
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    provider.online ? "bg-emerald-500" : "bg-zinc-600"
                  }`} />
                  
                  {/* Icon */}
                  <span className="text-zinc-400 flex-shrink-0">
                    {PROVIDER_ICONS[provider.name]}
                  </span>
                  
                  {/* Text content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-zinc-100">
                        {PROVIDER_LABELS[provider.name]}
                      </span>
                      {isCurrent && (
                        <span className="px-1.5 py-0.5 text-[9px] font-bold bg-emerald-600/30 text-emerald-400 rounded">
                          ACTIVE
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-zinc-500 mt-0.5">
                      {provider.online
                        ? `${provider.models.length} models`
                        : provider.error || "Offline"}
                    </div>
                  </div>
                  
                  {/* Check */}
                  {isSelected && (
                    <Check className="w-4 h-4 text-blue-400 flex-shrink-0" />
                  )}
                </button>
              );
            })}
          </div>

          {/* Model selector */}
          {selectedProvider && config?.providers.find(p => p.name === selectedProvider)?.models.length ? (
            <div className="px-4 py-3 border-t border-zinc-800">
              <label className="block text-xs font-medium text-zinc-500 mb-2">
                Model
              </label>
              <select
                value={selectedModel}
                onChange={(e) => {
                  setSelectedModel(e.target.value);
                  setShowInstructions(false);
                }}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded text-sm text-zinc-200 focus:outline-none focus:border-blue-500"
              >
                {config?.providers
                  .find((p) => p.name === selectedProvider)
                  ?.models.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
              </select>
            </div>
          ) : null}

          {/* Instructions panel (shown after Apply) */}
          {showInstructions && hasChanges && (
            <div className="px-4 py-3 border-t border-zinc-800 bg-blue-900/10">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-blue-400">
                  Add to .env file:
                </span>
                <button
                  onClick={handleCopyEnv}
                  className="flex items-center gap-1 px-2 py-1 text-[10px] bg-zinc-800 hover:bg-zinc-700 rounded text-zinc-300"
                >
                  {copied ? (
                    <>
                      <CheckCircle className="w-3 h-3 text-emerald-400" />
                      Copied!
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      Copy
                    </>
                  )}
                </button>
              </div>
              <pre className="p-2 bg-zinc-950 rounded text-[11px] text-zinc-300 font-mono overflow-x-auto">
                {getEnvCommands()}
              </pre>
              <p className="mt-2 text-[10px] text-zinc-500">
                Then restart: <code className="text-zinc-400">docker compose up -d langgraph</code>
              </p>
            </div>
          )}

          {/* Actions */}
          <div className="px-4 py-3 border-t border-zinc-800 flex gap-2">
            <button
              onClick={() => {
                setIsOpen(false);
                setShowInstructions(false);
                // Reset to current config
                if (config) {
                  setSelectedProvider(config.current_provider);
                  setSelectedModel(config.current_model);
                }
              }}
              className="flex-1 px-3 py-2 text-sm text-zinc-400 hover:text-zinc-200"
            >
              Cancel
            </button>
            <button
              onClick={handleApply}
              disabled={!hasChanges}
              className="flex-1 px-3 py-2 text-sm bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white rounded transition-colors"
            >
              {showInstructions ? "Instructions ↑" : "Apply"}
            </button>
          </div>

          {/* Footer note */}
          {!showInstructions && (
            <div className="px-4 py-2 bg-zinc-800/50 border-t border-zinc-800 text-[10px] text-zinc-500">
              Runtime changes require .env update + restart
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default LLMSelector;
