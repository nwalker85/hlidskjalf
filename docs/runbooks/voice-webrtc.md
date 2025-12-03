# Ravenhelm Voice Stack – Twilio WebRTC Integration

We use [Twilio WebRTC](https://www.twilio.com/en-us/webrtc) to let platform agents place and receive PSTN-quality calls directly inside the browser-based control plane. Twilio supplies the signaling, TURN media relay, and SDKs for JavaScript/iOS/Android so our agents can operate from anywhere with minimal infrastructure overhead while still leveraging Twilio’s global Super Network for SIP/PSTN breakout.[^twilio-webrtc]

## Current Objectives

1. **Embed calling UI** inside the `hlidskjalf` dashboard so on-call operators can answer routed calls or initiate outbound campaigns without leaving the app.
2. **Support multi-device clients** (web + future mobile) using the Twilio Voice SDK, sharing identity/session context with the Ravenhelm agent layer.
3. **Route contextual data** (customer profile, ticket info) alongside the call session so agents can view relevant insights mid-call.

## Required Components

| Component | Purpose | Notes |
|-----------|---------|-------|
| Twilio Voice SDK / WebRTC | Client-side voice/video plumbing | Provides browser-native audio with TURN fallback. |
| Twilio Programmable Voice (Server) | Voice session control + PSTN bridge | Configured via Twilio Console + webhooks served by Ravenhelm. |
| Agent UI (`hlidskjalf/ui`) | Embeds the Voice SDK | Hooks into Norns assistant + CRM context. |
| Signaling/Token service (`hlidskjalf` backend) | Issues Access Tokens per agent | Uses Twilio API keys & capabilities. |

## Implementation Notes

1. **Access Tokens** – Extend the `hlidskjalf` FastAPI backend with an endpoint that returns Twilio Voice access tokens scoped to the agent’s identity/permissions. Tokens will include the necessary grants for:
   - Outbound calls (PSTN + SIP)
   - Incoming call routing to a `client:{agent_id}` identity
2. **UI Integration** – In `hlidskjalf/ui/src/components/NornsChat.tsx` (or a dedicated voice panel), initialize the Twilio Voice SDK once the agent session loads. Provide status indicators, mute/hold, keypad, and call logging triggers.
3. **Call Routing** – Map Twilio webhooks (Voice URL + status callbacks) back into Ravenhelm:
   - `/voice/incoming` – When Twilio receives an inbound PSTN call, bridge it to the relevant agent identity (e.g., via queue/skills).
   - `/voice/events` – Record lifecycle events (ringing, answered, completed) for analytics.
4. **Observability** – Feed Twilio call events into Redpanda + LangFuse so Norns can reference call history, and optionally push metrics into Prometheus/Grafana.

### Credentials & Secrets

Twilio credentials live in our local `.env` / infrastructure secrets:

| Variable | Description | Location |
|----------|-------------|----------|
| `TWILIO_SID` | Account SID (ACxxxx) | `.env` (root) and `sendTwilio.py` smoke test |
| `TWILIO_AUTH_TOKEN` | Auth token / secret | `.env` |
| `TWILIO_NUMBER` | Provisioned Twilio phone number used for outbound calls/SMS | `.env` |

- The `sendTwilio.py` helper (see repo root) is the canonical smoke test to confirm SID/secret/number are valid; it sends a simple SMS when the env vars are present.
- For production, these secrets should be injected via OpenBao or the deployment environment; never commit `.env` or the raw credentials.

## Next Steps

1. Set up Twilio Voice project credentials (Account SID, Auth Token, API Key/Secret).
2. Create a `voice-token` endpoint in `hlidskjalf` backend and unit test it with the Twilio SDK.
3. Embed the WebRTC dialer in the agent UI and test call flows (browser ↔ PSTN, PSTN ↔ browser).
4. Document operational runbooks (token rotation, webhook retries, call quality troubleshooting).

[^twilio-webrtc]: Twilio, “WebRTC – Embed voice and video calls in your application,” accessed 2025-12-02, https://www.twilio.com/en-us/webrtc.***

