import { useEffect, useRef } from "react";

export type ProviderInfo = {
  id: string;
  name: string;
  available: boolean;
  models: string[];
  default_model: string;
};

export type LlmConfigEvent = {
  type: string;
  session_id?: string;
  config?: {
    reasoning: { provider: string; model: string; temperature: number };
    tools: { provider: string; model: string; temperature: number };
    subagents: { provider: string; model: string; temperature: number };
  };
  timestamp?: string;
  providers?: ProviderInfo[];
};

type Callback = (event: LlmConfigEvent) => void;

export function useLlmConfigEvents(
  enabled: boolean,
  onEvent?: Callback,
): void {
  const callbackRef = useRef(onEvent);
  callbackRef.current = onEvent;

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const eventSource = new EventSource("/api/llm/events");

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as LlmConfigEvent;
        if (callbackRef.current) {
          callbackRef.current(data);
        }
      } catch (err) {
        console.error("Failed to parse LLM config event", err);
      }
    };

    eventSource.onerror = (err) => {
      console.error("LLM config event stream error", err);
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [enabled]);
}


