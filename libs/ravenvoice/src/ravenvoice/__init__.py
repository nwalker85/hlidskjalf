"""
Ravenvoice — Reusable Voice Agent Library

A drop-in voice agent solution combining:
- LiveKit (WebRTC)
- Deepgram (Speech-to-Text)
- ElevenLabs (Text-to-Speech)
- LangGraph (AI Agent Brain)

Quick Start:
    from ravenvoice import VoiceAgent, DeepgramSTT, ElevenLabsTTS, LangGraphBrain
    
    agent = VoiceAgent(
        stt=DeepgramSTT(api_key="..."),
        tts=ElevenLabsTTS(api_key="...", voice_id="..."),
        brain=LangGraphBrain(api_url="http://langgraph:2024"),
    )
    
    # Join a LiveKit room and start listening
    await agent.connect(
        livekit_url="ws://localhost:7880",
        api_key="devkey",
        api_secret="secret",
        room_name="my-room",
    )

The Ravens Still Speak.
"""

__version__ = "0.1.0"

# Core
from ravenvoice.core import (
    VoiceAgent,
    VoiceAgentConfig,
    VoicePipeline,
)

# Provider base classes
from ravenvoice.providers.base import (
    BaseSTT,
    BaseTTS,
    BaseBrain,
    STTResult,
    TTSResult,
    BrainResponse,
)

# Concrete providers
from ravenvoice.providers.deepgram import DeepgramSTT
from ravenvoice.providers.elevenlabs import ElevenLabsTTS
from ravenvoice.providers.langgraph import LangGraphBrain
from ravenvoice.providers.openai_provider import OpenAISTT, OpenAITTS

__all__ = [
    # Version
    "__version__",
    # Core
    "VoiceAgent",
    "VoiceAgentConfig",
    "VoicePipeline",
    # Base classes
    "BaseSTT",
    "BaseTTS",
    "BaseBrain",
    "STTResult",
    "TTSResult",
    "BrainResponse",
    # Providers
    "DeepgramSTT",
    "ElevenLabsTTS",
    "LangGraphBrain",
    "OpenAISTT",
    "OpenAITTS",
]

