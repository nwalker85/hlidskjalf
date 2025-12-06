"use client";

import React, {
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ArrowRight } from "lucide-react";
import { PasswordInput } from "@/components/ui/password-input";
import { LangGraphLogoSVG } from "@/components/icons/langgraph";
import { getApiKey } from "@/lib/api-key";

export interface NornsSessionConfig {
  apiUrl: string;
  assistantId: string;
  threadId?: string | null;
}

interface NornsSessionContextValue {
  config: NornsSessionConfig;
  token: string | null;
  apiKey: string | null;
  setApiKey: (key: string) => void;
  updateThreadId: (threadId: string | null) => Promise<void>;
  refreshSession: () => Promise<void>;
  shareLink: () => Promise<string | null>;
}

const NornsSessionContext = createContext<
  NornsSessionContextValue | undefined
>(undefined);

export function useNornsSession() {
  const ctx = useContext(NornsSessionContext);
  if (!ctx) {
    throw new Error(
      "useNornsSession must be used within a NornsSessionProvider",
    );
  }
  return ctx;
}

const DEFAULT_API_URL =
  process.env.NEXT_PUBLIC_LANGGRAPH_API_URL || "https://norns.ravenhelm.test";
const DEFAULT_ASSISTANT_ID =
  process.env.NEXT_PUBLIC_LANGGRAPH_ASSISTANT_ID || "norns";

interface SessionResponse {
  token: string;
  config: NornsSessionConfig;
}

async function fetchSessionConfig(
  token?: string | null,
): Promise<SessionResponse | null> {
  const url = token ? `/api/norns/session?token=${token}` : "/api/norns/session";
  const resp = await fetch(url, { cache: "no-store" });
  if (resp.status === 404) {
    return null;
  }
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.error || "Failed to load session");
  }
  return resp.json();
}

async function persistSessionConfig(
  payload: NornsSessionConfig,
): Promise<SessionResponse> {
  const resp = await fetch("/api/norns/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.error || "Failed to save session");
  }
  return resp.json();
}

export function NornsSessionProvider({
  children,
}: {
  children: ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const sharedToken = searchParams.get("token");

  const [config, setConfig] = useState<NornsSessionConfig | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [apiKey, setApiKeyState] = useState<string>(() => getApiKey() || "");

  const setApiKey = useCallback((key: string) => {
    setApiKeyState(key);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("lg:chat:apiKey", key);
    }
  }, []);

  const refreshSession = useCallback(
    async (tokenOverride?: string | null) => {
      try {
        const session = await fetchSessionConfig(tokenOverride);
        if (!session) {
          setConfig(null);
          setToken(null);
          setError(null);
          return;
        }
        setConfig(session.config);
        setToken(session.token);
        setError(null);
      } catch (err) {
        console.error(err);
        setError(err instanceof Error ? err.message : "Failed to load session");
        setConfig(null);
        setToken(null);
      }
    },
    [],
  );

  useEffect(() => {
    setLoading(true);
    refreshSession(sharedToken)
      .catch(() => {
        /* error handled in refresh */
      })
      .finally(() => {
        setLoading(false);
        if (sharedToken) {
          router.replace(pathname || "/norns");
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sharedToken, refreshSession]);

  const handleCreateSession = useCallback(
    async (payload: { apiUrl: string; assistantId: string }) => {
      setSaving(true);
      try {
        const session = await persistSessionConfig({
          apiUrl: payload.apiUrl,
          assistantId: payload.assistantId,
          threadId: null,
        });
        setConfig(session.config);
        setToken(session.token);
        setError(null);
        router.replace(pathname || "/norns");
      } catch (err) {
        console.error(err);
        setError(
          err instanceof Error ? err.message : "Failed to save configuration",
        );
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [pathname, router],
  );

  const shareLink = useCallback(async () => {
    if (typeof window === "undefined" || !config) {
      return null;
    }
    try {
      const session = await persistSessionConfig({
        ...config,
        threadId: config.threadId ?? null,
      });
      setConfig(session.config);
      setToken(session.token);
      return `${window.location.origin}/norns?token=${session.token}`;
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : "Failed to generate link");
      return null;
    }
  }, [config]);

  const updateThreadId = useCallback(
    async (threadId: string | null) => {
      if (!config) return;
      setConfig((prev) => (prev ? { ...prev, threadId } : prev));
      try {
        const session = await persistSessionConfig({
          apiUrl: config.apiUrl,
          assistantId: config.assistantId,
          threadId,
        });
        setConfig(session.config);
        setToken(session.token);
      } catch (err) {
        console.error(err);
        setError(
          err instanceof Error ? err.message : "Failed to update session",
        );
      }
    },
    [config],
  );

  const contextValue = useMemo(() => {
    if (!config) {
      return undefined;
    }
    return {
      config,
      token,
      apiKey: apiKey || null,
      setApiKey,
      updateThreadId,
      refreshSession: () => refreshSession(null),
      shareLink,
    };
  }, [apiKey, config, token, refreshSession, setApiKey, shareLink, updateThreadId]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#0A0F1C] text-raven-400">
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <div className="w-12 h-12 rounded-full border-2 border-raven-700 border-t-huginn-400 animate-spin" />
          </div>
          <span className="font-mono text-sm">
            Initializing Norns Intelligence Console...
          </span>
        </div>
      </div>
    );
  }

  if (!config || !contextValue) {
    return (
      <div className="flex min-h-screen w-full items-center justify-center p-4 bg-raven-950">
        <div className="animate-in fade-in-0 zoom-in-95 bg-raven-900 flex max-w-3xl flex-col rounded-lg border border-raven-800 shadow-lg">
          <div className="mt-14 flex flex-col gap-2 border-b border-raven-800 p-6">
            <div className="flex flex-col items-start gap-2">
              <LangGraphLogoSVG className="h-7" />
              <h1 className="text-xl font-semibold tracking-tight text-raven-100">
                Agent Chat
              </h1>
            </div>
            <p className="text-raven-400">
              Welcome to Agent Chat! Before you get started, enter the URL of
              your LangGraph deployment and the assistant / graph ID.
            </p>
          </div>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const form = e.currentTarget;
              const formData = new FormData(form);
              const apiUrl = (formData.get("apiUrl") as string).trim();
              const assistantId = (formData.get("assistantId") as string).trim();
              const apiKeyInput = (formData.get("apiKey") as string) ?? "";

              setApiKey(apiKeyInput);

              try {
                await handleCreateSession({ apiUrl, assistantId });
                form.reset();
              } catch {
                // error already surfaced via state/toast
              }
            }}
            className="bg-raven-900/50 flex flex-col gap-6 p-6"
          >
            <div className="flex flex-col gap-2">
              <Label htmlFor="apiUrl" className="text-raven-200">
                Deployment URL<span className="text-rose-500">*</span>
              </Label>
              <p className="text-raven-500 text-sm">
                This is the URL of your LangGraph deployment. It can be local or
                production.
              </p>
              <Input
                id="apiUrl"
                name="apiUrl"
                className="bg-raven-800 border-raven-700 text-raven-100 placeholder:text-raven-500"
                defaultValue={DEFAULT_API_URL}
                autoComplete="url"
                required
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="assistantId" className="text-raven-200">
                Assistant / Graph ID<span className="text-rose-500">*</span>
              </Label>
              <p className="text-raven-500 text-sm">
                Provide the ID of the graph (or assistant) used for this
                deployment.
              </p>
              <Input
                id="assistantId"
                name="assistantId"
                className="bg-raven-800 border-raven-700 text-raven-100 placeholder:text-raven-500"
                defaultValue={DEFAULT_ASSISTANT_ID}
                autoComplete="username"
                required
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="apiKey" className="text-raven-200">
                LangSmith API Key
              </Label>
              <p className="text-raven-500 text-sm">
                Not required for local LangGraph servers. Stored in your
                browser's local storage.
              </p>
              <PasswordInput
                id="apiKey"
                name="apiKey"
                defaultValue={apiKey ?? ""}
                className="bg-raven-800 border-raven-700 text-raven-100 placeholder:text-raven-500"
                placeholder="lsv2_pt_..."
                autoComplete="new-password"
              />
            </div>

            {error && (
              <div className="text-sm text-rose-400 border border-rose-500/40 rounded-lg px-3 py-2 bg-rose-500/5">
                {error}
              </div>
            )}

            <div className="mt-2 flex justify-end">
              <Button
                type="submit"
                size="lg"
                className="bg-huginn-600 hover:bg-huginn-500 text-white"
                disabled={saving}
              >
                {saving ? "Configuring..." : "Continue"}
                <ArrowRight className="size-5" />
              </Button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  return (
    <NornsSessionContext.Provider value={contextValue}>
      {children}
    </NornsSessionContext.Provider>
  );
}

