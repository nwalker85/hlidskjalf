# ADR: Dynamic LLM Configuration Flow

## Context

Operators can switch LLM providers/models for the Norns during an active
session. The existing flow is:

1. **UI (`LLMConfigModal`)** calls `POST /api/llm/config` with the session ID.
2. **Next.js route** proxies to `hlidskjalf` (`/api/v1/llm/config/{session}`).
3. **FastAPI controller** stores the config in Huginn via
   `HuginnStateAgent.update_llm_config`, which persists to Redis.
4. **LangGraph runtime** reads `_huginn.perceive(session_id)` at run start and
   selects models via `_get_session_llm_config`.

Gaps:

- LangGraph only sees updates when `_huginn.perceive` refreshes, so mid-thread
  changes can be missed.
- There is no event/stream confirming when a new config is applied.
- UI dropdown models were previously static and could list models not loaded in
  the host Ollama instance.

## Decision

Implement an end-to-end evented flow so the *next* graph execution uses the
newly selected model:

- Emit an `llm_config.changed` event (Kafka topic + SSE proxy) whenever the
  FastAPI controller updates Huginn.
- Expose a lightweight diagnostics endpoint so operators can verify the active
  config stored in Redis.
- Update the UI to subscribe to the SSE stream and refresh provider/model lists
  plus the current session config when a change event arrives.
- In the LangGraph service, add a subscriber that listens for the change
  events, updates an in-process cache, and injects the config into each
  `NornState` so `norns_node`, planner, tools, etc., read the settings from the
  run state instead of static defaults.

## Consequences

- Model dropdowns always reflect the models currently loaded in Ollama/LM
  Studio/OpenAI.
- Huginn remains the source of truth, but LangGraph the runtime never uses
  stale data because it receives the same event stream as the UI.
- Every run logs the provider/model applied, providing traceability for future
  incidents.


