# 🎤 Ravenvoice

> *The Ravens Still Speak*

A reusable voice agent library that makes building voice-enabled AI applications simple.
Drop-in support for LiveKit + Deepgram + ElevenLabs + LangGraph.

## Features

- **🎯 Simple API** — One class to rule them all
- **🔌 Pluggable Providers** — Swap STT/TTS/Brain easily
- **🎙️ LiveKit Integration** — WebRTC voice rooms
- **🧠 LangGraph Brain** — Connect to any LangGraph agent (including the Norns!)
- **📦 Reusable** — Import into any Python project

## Quick Start

### Installation

```bash
# From the ravenhelm monorepo
pip install -e libs/ravenvoice[all]

# Or just what you need
pip install -e libs/ravenvoice
pip install deepgram-sdk elevenlabs
```

### Basic Usage

```python
import asyncio
from ravenvoice import VoiceAgent, DeepgramSTT, ElevenLabsTTS, LangGraphBrain

async def main():
    # Create providers
    stt = DeepgramSTT(api_key="your-deepgram-key")
    tts = ElevenLabsTTS(api_key="your-elevenlabs-key", voice_id="rachel")
    brain = LangGraphBrain(api_url="http://langgraph:2024", assistant_id="norns")
    
    # Create agent
    agent = VoiceAgent(stt=stt, tts=tts, brain=brain)
    await agent.initialize()
    
    # Connect to LiveKit room
    await agent.connect(
        livekit_url="ws://localhost:7880",
        api_key="devkey",
        api_secret="secret",
        room_name="my-voice-room",
    )
    
    # Run (listens, thinks, speaks automatically)
    await agent.run()

asyncio.run(main())
```

### Factory Function

```python
from ravenvoice import create_voice_agent

agent = create_voice_agent(
    stt_provider="deepgram",
    tts_provider="elevenlabs",
    brain_provider="langgraph",
    deepgram_api_key="...",
    elevenlabs_api_key="...",
    elevenlabs_voice_id="rachel",
    langgraph_api_url="http://langgraph:2024",
    livekit_url="ws://localhost:7880",
    room_name="my-room",
)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         VoiceAgent                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ LiveKit  │───▶│   STT    │───▶│  Brain   │───▶│   TTS    │  │
│  │ (Audio)  │    │(Deepgram)│    │(LangGraph│    │(ElevenLabs│  │
│  │          │◀───│          │◀───│  Norns)  │◀───│          │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                                                  │
│  Audio In ─────────────────────────────────────────▶ Audio Out  │
└─────────────────────────────────────────────────────────────────┘
```

## Providers

### Speech-to-Text (STT)

| Provider | Class | Features |
|----------|-------|----------|
| **Deepgram** | `DeepgramSTT` | Streaming, word timestamps, diarization |
| **OpenAI Whisper** | `OpenAISTT` | High quality, multilingual |

### Text-to-Speech (TTS)

| Provider | Class | Features |
|----------|-------|----------|
| **ElevenLabs** | `ElevenLabsTTS` | Neural voices, streaming, voice cloning |
| **OpenAI** | `OpenAITTS` | HD quality, multiple voices |

### Brain (AI)

| Provider | Class | Features |
|----------|-------|----------|
| **LangGraph** | `LangGraphBrain` | Tool use, memory, Norns integration |

## Configuration

### VoiceAgentConfig

```python
from ravenvoice import VoiceAgentConfig

config = VoiceAgentConfig(
    # LiveKit
    livekit_url="ws://localhost:7880",
    livekit_api_key="devkey",
    livekit_api_secret="secret",
    
    # Room
    room_name="my-room",
    participant_name="VoiceAgent",
    
    # Behavior
    auto_speak=True,              # Speak brain responses
    interrupt_on_speech=True,     # Stop if user talks
    silence_threshold_ms=1000,    # Silence before processing
    
    # Language
    language="en",
    
    # Callbacks
    on_state_change=lambda state: print(f"State: {state}"),
    on_transcript=lambda t: print(f"User: {t.text}"),
    on_response=lambda r: print(f"Agent: {r.text}"),
)
```

### Environment Variables

```bash
# Deepgram
DEEPGRAM_API_KEY=your-key

# ElevenLabs
ELEVEN_API_KEY=your-key

# OpenAI (for Whisper/TTS)
OPENAI_API_KEY=your-key

# LiveKit
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
```

## Custom Providers

### Custom STT

```python
from ravenvoice import BaseSTT, STTResult, AudioFormat

class MySTT(BaseSTT):
    @property
    def name(self) -> str:
        return "my_stt"
    
    async def transcribe(
        self,
        audio: bytes,
        format: AudioFormat = AudioFormat.PCM_16KHZ,
        language: str = "en",
    ) -> STTResult:
        # Your implementation
        text = await my_api.transcribe(audio)
        return STTResult(text=text, provider=self.name)
```

### Custom Brain

```python
from ravenvoice import BaseBrain, BrainResponse

class MyBrain(BaseBrain):
    @property
    def name(self) -> str:
        return "my_brain"
    
    async def think(
        self,
        text: str,
        thread_id: str = None,
        context: dict = None,
    ) -> BrainResponse:
        # Your implementation
        response = await my_llm.chat(text)
        return BrainResponse(text=response, thread_id=thread_id)
```

## Examples

### Voice-Enabled Norns

```python
from ravenvoice import create_voice_agent

# Create agent connected to Norns
agent = create_voice_agent(
    brain_provider="langgraph",
    langgraph_api_url="http://gitlab-sre-langgraph:2024",
    langgraph_assistant_id="norns",
    room_name="norns-voice",
)

await agent.initialize()
await agent.connect()
await agent.run()
```

### Text-Only Mode (No LiveKit)

```python
from ravenvoice import DeepgramSTT, ElevenLabsTTS, LangGraphBrain, VoicePipeline

stt = DeepgramSTT()
tts = ElevenLabsTTS()
brain = LangGraphBrain()

pipeline = VoicePipeline(stt, tts, brain, config)
await pipeline.initialize()

# Process audio directly
transcript, response, audio = await pipeline.process_audio(audio_bytes)

# Or just transcribe
transcript = await pipeline.transcribe_only(audio_bytes)

# Or just speak
audio = await pipeline.speak_only("Hello, world!")
```

### Callbacks

```python
def on_transcript(result):
    print(f"[USER] {result.text}")
    # Save to database, emit event, etc.

def on_response(response):
    print(f"[{response.persona.upper()}] {response.text}")
    # Log, metrics, etc.

config = VoiceAgentConfig(
    on_transcript=on_transcript,
    on_response=on_response,
)
```

## Integration with Bifrost

Ravenvoice can be used with Bifrost to add voice to chat platforms:

```python
# In Bifrost adapter
from ravenvoice import VoicePipeline, DeepgramSTT, ElevenLabsTTS, LangGraphBrain

pipeline = VoicePipeline(
    DeepgramSTT(),
    ElevenLabsTTS(),
    LangGraphBrain(api_url="http://langgraph:2024"),
    config,
)

# When voice message received from Telegram
async def handle_voice_message(voice_file: bytes):
    transcript, response, audio = await pipeline.process_audio(voice_file)
    # Send audio response back to Telegram
    return audio
```

## Requirements

- Python 3.11+
- LiveKit server (for WebRTC rooms)
- API keys for providers (Deepgram, ElevenLabs, etc.)

## Related

- [Bifrost Gateway](../../bifrost-gateway/) — External chat integrations
- [Norns](../../hlidskjalf/) — The AI agent system
- [RUNBOOK-022](../../docs/runbooks/RUNBOOK-022-configure-voice-agent.md) — Setup guide

---

*"The ravens still fly. They still return with what is seen and what is known."*

