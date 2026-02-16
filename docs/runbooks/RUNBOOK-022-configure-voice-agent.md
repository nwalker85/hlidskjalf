# RUNBOOK-022: Configure Voice Agent (Ravenvoice)

> **Purpose**: Set up a voice-enabled AI agent using the Ravenvoice library  
> **Scope**: LiveKit + Deepgram + ElevenLabs + LangGraph integration  
> **Audience**: Developers integrating voice capabilities

---

## Prerequisites

- [ ] LiveKit server running (`docker compose up livekit`)
- [ ] Deepgram API key (https://console.deepgram.com)
- [ ] ElevenLabs API key (https://elevenlabs.io)
- [ ] LangGraph server running with target agent (e.g., Norns)
- [ ] Python 3.11+

---

## 1. Install Ravenvoice

### From Monorepo (Recommended)

```bash
cd ~/Development/hlidskjalf
pip install -e libs/ravenvoice[all]
```

### Minimal Installation

```bash
pip install -e libs/ravenvoice
pip install deepgram-sdk elevenlabs livekit livekit-agents
```

---

## 2. Configure API Keys

### Option A: Environment Variables

```bash
# Add to ~/.zshrc or .env
export DEEPGRAM_API_KEY=your-deepgram-key
export ELEVEN_API_KEY=your-elevenlabs-key
export LIVEKIT_API_KEY=devkey
export LIVEKIT_API_SECRET=secret
```

### Option B: Direct Configuration

```python
stt = DeepgramSTT(api_key="your-key")
tts = ElevenLabsTTS(api_key="your-key")
```

### Option C: OpenBao/Vault (Production)

```python
import hvac

client = hvac.Client(url="https://vault.ravenhelm.test:8443")
secrets = client.secrets.kv.v2.read_secret_version(path="ravenvoice")

stt = DeepgramSTT(api_key=secrets["data"]["data"]["deepgram_key"])
```

---

## 3. Verify LiveKit

### Check LiveKit is Running

```bash
curl http://localhost:7880/healthz
# Expected: {"status":"ok"}
```

### Test Token Generation

```python
from livekit import api

token = (
    api.AccessToken("devkey", "secret")
    .with_identity("test-user")
    .with_grants(api.VideoGrants(room_join=True, room="test-room"))
    .to_jwt()
)
print(token)  # Should print JWT
```

---

## 4. Create Voice Agent

### Minimal Example

```python
import asyncio
from ravenvoice import VoiceAgent, DeepgramSTT, ElevenLabsTTS, LangGraphBrain

async def main():
    # Initialize providers
    stt = DeepgramSTT()  # Uses DEEPGRAM_API_KEY env var
    tts = ElevenLabsTTS(voice_id="rachel")  # Uses ELEVEN_API_KEY env var
    brain = LangGraphBrain(
        api_url="http://localhost:2024",  # Or http://langgraph:2024 in Docker
        assistant_id="norns",
    )
    
    # Create and initialize agent
    agent = VoiceAgent(stt=stt, tts=tts, brain=brain)
    await agent.initialize()
    
    # Connect to LiveKit room
    await agent.connect(
        livekit_url="ws://localhost:7880",
        room_name="voice-test",
    )
    
    print("Agent ready! Join room 'voice-test' to interact.")
    await agent.run()

asyncio.run(main())
```

### Production Example with Callbacks

```python
import asyncio
import structlog
from ravenvoice import (
    VoiceAgent,
    VoiceAgentConfig,
    DeepgramSTT,
    ElevenLabsTTS,
    LangGraphBrain,
    VoiceAgentState,
)

logger = structlog.get_logger()

def on_state_change(state: VoiceAgentState):
    logger.info("voice_agent_state_changed", state=state.value)

def on_transcript(result):
    logger.info("user_speech", text=result.text, confidence=result.confidence)

def on_response(response):
    logger.info("agent_response", 
                text=response.text, 
                persona=response.persona,
                tool_calls=len(response.tool_calls or []))

async def main():
    config = VoiceAgentConfig(
        livekit_url="ws://localhost:7880",
        room_name="norns-voice",
        participant_name="Norns-Voice-Agent",
        silence_threshold_ms=1500,
        on_state_change=on_state_change,
        on_transcript=on_transcript,
        on_response=on_response,
    )
    
    agent = VoiceAgent(
        stt=DeepgramSTT(model="nova-2"),
        tts=ElevenLabsTTS(voice_id="rachel", model_id="eleven_turbo_v2_5"),
        brain=LangGraphBrain(
            api_url="http://langgraph:2024",
            assistant_id="norns",
        ),
        config=config,
    )
    
    await agent.initialize()
    await agent.connect()
    
    logger.info("voice_agent_started", room="norns-voice")
    await agent.run()

asyncio.run(main())
```

---

## 5. Test the Agent

### Using LiveKit Playground

1. Go to https://livekit.io/playground
2. Enter your server URL: `ws://localhost:7880`
3. Enter room name: `voice-test`
4. Generate token (or paste one)
5. Join and speak!

### Using CLI

```bash
# Install livekit-cli
brew install livekit-cli

# Join room
livekit-cli join --url ws://localhost:7880 \
  --api-key devkey \
  --api-secret secret \
  --room voice-test \
  --identity tester
```

### Programmatic Test

```python
async def test_voice_agent():
    agent = create_voice_agent(...)
    await agent.initialize()
    await agent.connect(room_name="test-room")
    
    # Test direct speech
    await agent.say("Hello! I'm ready to help.")
    
    # Test brain interaction
    response = await agent.ask("What is the status of the platform?")
    print(f"Response: {response.text}")
```

---

## 6. Deploy in Docker

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install audio dependencies
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install ravenvoice
COPY libs/ravenvoice /app/libs/ravenvoice
RUN pip install -e /app/libs/ravenvoice[all]

# Copy agent code
COPY voice_agent.py /app/

CMD ["python", "voice_agent.py"]
```

### Docker Compose Service

```yaml
voice-agent:
  build:
    context: .
    dockerfile: Dockerfile.voice-agent
  container_name: gitlab-sre-voice-agent
  environment:
    - DEEPGRAM_API_KEY=${DEEPGRAM_API_KEY}
    - ELEVEN_API_KEY=${ELEVEN_API_KEY}
    - LIVEKIT_URL=ws://livekit:7880
    - LANGGRAPH_URL=http://langgraph:2024
  depends_on:
    - livekit
    - langgraph
  networks:
    - platform_net
```

---

## 7. Voice Selection

### ElevenLabs Voices

| Name | Voice ID | Style |
|------|----------|-------|
| Rachel | `21m00Tcm4TlvDq8ikWAM` | Female, professional |
| Adam | `pNInz6obpgDQGcFmaJgB` | Male, friendly |
| Bella | `EXAVITQu4vr4xnSDxMaL` | Female, warm |
| Josh | `TxGEqnHWrfWFTfGW9XjX` | Male, deep |

```python
# Use voice name (convenience)
tts = ElevenLabsTTS(voice_id="rachel")

# Or voice ID directly
tts = ElevenLabsTTS(voice_id="21m00Tcm4TlvDq8ikWAM")
```

### OpenAI Voices

| Voice | Style |
|-------|-------|
| alloy | Neutral |
| echo | Male |
| fable | British |
| onyx | Deep male |
| nova | Female |
| shimmer | Female, warm |

```python
tts = OpenAITTS(voice="nova")
```

---

## 8. Troubleshooting

### No Audio Received

```bash
# Check LiveKit logs
docker logs gitlab-sre-livekit

# Verify room exists
curl http://localhost:7880/rooms
```

### STT Not Working

```python
# Test Deepgram directly
from deepgram import DeepgramClient

client = DeepgramClient("your-key")
# Should not raise exception
```

### TTS Errors

```python
# Test ElevenLabs directly
from elevenlabs import AsyncElevenLabs

client = AsyncElevenLabs(api_key="your-key")
audio = await client.text_to_speech.convert(
    voice_id="21m00Tcm4TlvDq8ikWAM",
    text="Test",
)
```

### Brain Not Responding

```bash
# Check LangGraph health
curl http://localhost:2024/info

# Check assistant exists
curl http://localhost:2024/assistants
```

---

## 9. Performance Tuning

### Reduce Latency

```python
config = VoiceAgentConfig(
    silence_threshold_ms=500,  # Faster response (but may cut off)
)

# Use streaming TTS
tts = ElevenLabsTTS(model_id="eleven_turbo_v2_5")  # Faster model
```

### Improve Quality

```python
# Higher quality STT
stt = DeepgramSTT(model="nova-2", smart_format=True, diarize=True)

# Higher quality TTS
tts = ElevenLabsTTS(
    model_id="eleven_multilingual_v2",  # Better quality
    stability=0.7,  # More consistent
)
```

---

## 10. Related Runbooks

- [RUNBOOK-001](./RUNBOOK-001-deploy-docker-service.md) — Deploy Docker services
- [RUNBOOK-020](./RUNBOOK-020-add-bifrost-adapter.md) — Bifrost chat adapters
- [RUNBOOK-021](./RUNBOOK-021-add-bifrost-ai-backend.md) — Bifrost AI backends

---

## Checklist

- [ ] API keys configured
- [ ] LiveKit server running
- [ ] LangGraph server running with target assistant
- [ ] Voice agent code written
- [ ] Tested with LiveKit Playground or CLI
- [ ] Deployed in Docker (if production)

---

*"Give voice to thought, give speech to knowledge."*

