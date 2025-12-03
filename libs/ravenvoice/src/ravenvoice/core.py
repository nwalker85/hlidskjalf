"""
Voice Agent Core — The main VoiceAgent class that orchestrates everything.

This is the primary interface for creating voice agents.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Any

import structlog

from ravenvoice.providers.base import (
    BaseSTT,
    BaseTTS,
    BaseBrain,
    STTResult,
    BrainResponse,
    AudioFormat,
)

logger = structlog.get_logger(__name__)

# Optional LiveKit import
try:
    from livekit import rtc
    from livekit.agents import (
        JobContext,
        WorkerOptions,
        cli,
        llm as lk_llm,
    )
    HAS_LIVEKIT = True
except ImportError:
    HAS_LIVEKIT = False
    logger.debug("livekit_not_installed", hint="pip install livekit livekit-agents")


class VoiceAgentState(str, Enum):
    """Voice agent states."""
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"


@dataclass
class VoiceAgentConfig:
    """Configuration for VoiceAgent."""
    
    # LiveKit connection
    livekit_url: str = "ws://localhost:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "secret"
    
    # Room settings
    room_name: Optional[str] = None
    participant_name: str = "VoiceAgent"
    
    # Audio settings
    sample_rate: int = 16000
    channels: int = 1
    
    # Behavior
    auto_speak: bool = True  # Automatically speak brain responses
    interrupt_on_speech: bool = True  # Stop speaking if user starts talking
    silence_threshold_ms: int = 1000  # Silence before processing
    
    # Language
    language: str = "en"
    
    # Callbacks
    on_state_change: Optional[Callable[[VoiceAgentState], None]] = None
    on_transcript: Optional[Callable[[STTResult], None]] = None
    on_response: Optional[Callable[[BrainResponse], None]] = None


class VoicePipeline:
    """
    Voice processing pipeline.
    
    Handles the flow: Audio → STT → Brain → TTS → Audio
    """
    
    def __init__(
        self,
        stt: BaseSTT,
        tts: BaseTTS,
        brain: BaseBrain,
        config: VoiceAgentConfig,
    ):
        self.stt = stt
        self.tts = tts
        self.brain = brain
        self.config = config
        self._thread_id: Optional[str] = None
    
    async def initialize(self) -> None:
        """Initialize all providers."""
        await self.stt.initialize()
        await self.tts.initialize()
        await self.brain.initialize()
        logger.info(
            "voice_pipeline_initialized",
            stt=self.stt.name,
            tts=self.tts.name,
            brain=self.brain.name,
        )
    
    async def shutdown(self) -> None:
        """Shutdown all providers."""
        await self.stt.shutdown()
        await self.tts.shutdown()
        await self.brain.shutdown()
    
    async def process_audio(self, audio: bytes) -> tuple[STTResult, BrainResponse, bytes]:
        """
        Full pipeline: Audio → STT → Brain → TTS
        
        Args:
            audio: Raw audio bytes
            
        Returns:
            Tuple of (transcript, brain_response, audio_response)
        """
        # 1. Speech to Text
        transcript = await self.stt.transcribe(
            audio,
            format=AudioFormat.PCM_16KHZ,
            language=self.config.language,
        )
        
        if self.config.on_transcript:
            self.config.on_transcript(transcript)
        
        if not transcript.text.strip():
            return transcript, None, None
        
        # 2. Brain processing
        response = await self.brain.think(
            transcript.text,
            thread_id=self._thread_id,
            context={
                "source": "voice",
                "language": self.config.language,
            },
        )
        
        # Store thread for continuity
        if response.thread_id:
            self._thread_id = response.thread_id
        
        if self.config.on_response:
            self.config.on_response(response)
        
        if not response.should_speak or not response.text.strip():
            return transcript, response, None
        
        # 3. Text to Speech
        tts_result = await self.tts.synthesize(response.text)
        
        return transcript, response, tts_result.audio
    
    async def transcribe_only(self, audio: bytes) -> STTResult:
        """Just transcribe audio without processing."""
        return await self.stt.transcribe(audio, format=AudioFormat.PCM_16KHZ)
    
    async def speak_only(self, text: str) -> bytes:
        """Just synthesize speech without brain."""
        result = await self.tts.synthesize(text)
        return result.audio


class VoiceAgent:
    """
    Complete voice agent with LiveKit integration.
    
    This is the main class you'll use to create voice agents.
    
    Example:
        from ravenvoice import VoiceAgent, DeepgramSTT, ElevenLabsTTS, LangGraphBrain
        
        agent = VoiceAgent(
            stt=DeepgramSTT(api_key="..."),
            tts=ElevenLabsTTS(api_key="...", voice_id="rachel"),
            brain=LangGraphBrain(api_url="http://langgraph:2024"),
        )
        
        # Connect to LiveKit room
        await agent.connect(
            livekit_url="ws://localhost:7880",
            api_key="devkey",
            api_secret="secret",
            room_name="my-room",
        )
        
        # Agent will now listen, think, and speak automatically
        await agent.run()
    """
    
    def __init__(
        self,
        stt: BaseSTT,
        tts: BaseTTS,
        brain: BaseBrain,
        config: Optional[VoiceAgentConfig] = None,
    ):
        """
        Initialize VoiceAgent.
        
        Args:
            stt: Speech-to-Text provider
            tts: Text-to-Speech provider
            brain: AI brain provider
            config: Agent configuration (optional)
        """
        self.config = config or VoiceAgentConfig()
        self.pipeline = VoicePipeline(stt, tts, brain, self.config)
        
        self._state = VoiceAgentState.IDLE
        self._room: Optional[Any] = None
        self._audio_track: Optional[Any] = None
        self._running = False
        self._audio_buffer = bytearray()
    
    @property
    def state(self) -> VoiceAgentState:
        """Current agent state."""
        return self._state
    
    def _set_state(self, state: VoiceAgentState) -> None:
        """Update state and trigger callback."""
        self._state = state
        if self.config.on_state_change:
            self.config.on_state_change(state)
        logger.debug("voice_agent_state", state=state.value)
    
    async def initialize(self) -> None:
        """Initialize the agent and providers."""
        await self.pipeline.initialize()
        logger.info("voice_agent_initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the agent."""
        self._running = False
        if self._room:
            await self._room.disconnect()
        await self.pipeline.shutdown()
        logger.info("voice_agent_shutdown")
    
    async def connect(
        self,
        livekit_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        room_name: Optional[str] = None,
        token: Optional[str] = None,
    ) -> None:
        """
        Connect to a LiveKit room.
        
        Args:
            livekit_url: LiveKit server URL
            api_key: API key for token generation
            api_secret: API secret for token generation
            room_name: Room to join
            token: Pre-generated access token (alternative to key/secret)
        """
        if not HAS_LIVEKIT:
            raise ImportError("livekit not installed. Run: pip install livekit livekit-agents")
        
        url = livekit_url or self.config.livekit_url
        room = room_name or self.config.room_name
        
        if not room:
            raise ValueError("room_name is required")
        
        # Generate token if not provided
        if not token:
            from livekit import api
            
            key = api_key or self.config.livekit_api_key
            secret = api_secret or self.config.livekit_api_secret
            
            token = (
                api.AccessToken(key, secret)
                .with_identity(self.config.participant_name)
                .with_name(self.config.participant_name)
                .with_grants(api.VideoGrants(
                    room_join=True,
                    room=room,
                ))
                .to_jwt()
            )
        
        # Connect to room
        self._room = rtc.Room()
        
        # Set up event handlers
        @self._room.on("track_subscribed")
        def on_track_subscribed(track, publication, participant):
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info("audio_track_subscribed", participant=participant.identity)
                asyncio.create_task(self._process_audio_track(track))
        
        @self._room.on("participant_connected")
        def on_participant_connected(participant):
            logger.info("participant_connected", identity=participant.identity)
        
        @self._room.on("disconnected")
        def on_disconnected():
            logger.info("disconnected_from_room")
            self._running = False
        
        await self._room.connect(url, token)
        logger.info("connected_to_room", room=room, url=url)
    
    async def _process_audio_track(self, track) -> None:
        """Process incoming audio from a track."""
        audio_stream = rtc.AudioStream(track)
        
        self._set_state(VoiceAgentState.LISTENING)
        silence_frames = 0
        
        async for frame_event in audio_stream:
            if not self._running:
                break
            
            frame = frame_event.frame
            audio_data = frame.data.tobytes()
            
            # Detect silence
            is_silent = self._is_silent(audio_data)
            
            if is_silent:
                silence_frames += 1
                if silence_frames * 20 >= self.config.silence_threshold_ms:  # ~20ms per frame
                    if self._audio_buffer:
                        # Process accumulated audio
                        await self._handle_speech_end()
                        silence_frames = 0
            else:
                silence_frames = 0
                self._audio_buffer.extend(audio_data)
    
    def _is_silent(self, audio: bytes) -> bool:
        """Check if audio chunk is silent."""
        import struct
        
        # Simple RMS-based silence detection
        samples = struct.unpack(f"{len(audio)//2}h", audio)
        rms = (sum(s**2 for s in samples) / len(samples)) ** 0.5
        return rms < 500  # Threshold
    
    async def _handle_speech_end(self) -> None:
        """Handle end of user speech."""
        if not self._audio_buffer:
            return
        
        audio = bytes(self._audio_buffer)
        self._audio_buffer.clear()
        
        self._set_state(VoiceAgentState.THINKING)
        
        try:
            transcript, response, audio_response = await self.pipeline.process_audio(audio)
            
            if audio_response and self.config.auto_speak:
                self._set_state(VoiceAgentState.SPEAKING)
                await self._play_audio(audio_response)
            
            self._set_state(VoiceAgentState.LISTENING)
            
        except Exception as e:
            logger.error("voice_processing_error", error=str(e))
            self._set_state(VoiceAgentState.ERROR)
    
    async def _play_audio(self, audio: bytes) -> None:
        """Play audio to the room."""
        if not self._room:
            return
        
        # Create audio source and track
        source = rtc.AudioSource(
            sample_rate=self.config.sample_rate,
            num_channels=self.config.channels,
        )
        
        track = rtc.LocalAudioTrack.create_audio_track("agent-voice", source)
        
        options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        publication = await self._room.local_participant.publish_track(track, options)
        
        # Push audio frames
        import struct
        
        frame_size = self.config.sample_rate // 50  # 20ms frames
        for i in range(0, len(audio), frame_size * 2):
            chunk = audio[i:i + frame_size * 2]
            if len(chunk) < frame_size * 2:
                chunk += b'\x00' * (frame_size * 2 - len(chunk))
            
            samples = struct.unpack(f"{frame_size}h", chunk)
            frame = rtc.AudioFrame(
                data=bytes(chunk),
                sample_rate=self.config.sample_rate,
                num_channels=self.config.channels,
                samples_per_channel=frame_size,
            )
            await source.capture_frame(frame)
        
        # Cleanup
        await self._room.local_participant.unpublish_track(publication.sid)
    
    async def run(self) -> None:
        """Run the agent (blocking)."""
        if not self._room:
            raise RuntimeError("Not connected to a room. Call connect() first.")
        
        self._running = True
        logger.info("voice_agent_running")
        
        try:
            while self._running:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.shutdown()
    
    async def say(self, text: str) -> None:
        """
        Speak text immediately.
        
        Args:
            text: Text to speak
        """
        self._set_state(VoiceAgentState.SPEAKING)
        audio = await self.pipeline.speak_only(text)
        await self._play_audio(audio)
        self._set_state(VoiceAgentState.LISTENING if self._running else VoiceAgentState.IDLE)
    
    async def ask(self, question: str) -> BrainResponse:
        """
        Ask the brain a question directly (without voice input).
        
        Args:
            question: Question text
            
        Returns:
            Brain response
        """
        self._set_state(VoiceAgentState.THINKING)
        response = await self.pipeline.brain.think(question)
        
        if response.should_speak and self.config.auto_speak:
            self._set_state(VoiceAgentState.SPEAKING)
            audio = await self.pipeline.speak_only(response.text)
            await self._play_audio(audio)
        
        self._set_state(VoiceAgentState.LISTENING if self._running else VoiceAgentState.IDLE)
        return response


# =============================================================================
# Factory function for quick setup
# =============================================================================

def create_voice_agent(
    stt_provider: str = "deepgram",
    tts_provider: str = "elevenlabs",
    brain_provider: str = "langgraph",
    **kwargs,
) -> VoiceAgent:
    """
    Factory function to create a voice agent with common providers.
    
    Args:
        stt_provider: STT provider name (deepgram, openai)
        tts_provider: TTS provider name (elevenlabs, openai)
        brain_provider: Brain provider name (langgraph)
        **kwargs: Provider-specific configuration
        
    Returns:
        Configured VoiceAgent
        
    Example:
        agent = create_voice_agent(
            stt_provider="deepgram",
            tts_provider="elevenlabs",
            brain_provider="langgraph",
            deepgram_api_key="...",
            elevenlabs_api_key="...",
            elevenlabs_voice_id="rachel",
            langgraph_api_url="http://langgraph:2024",
        )
    """
    # Create STT
    if stt_provider == "deepgram":
        from ravenvoice.providers.deepgram import DeepgramSTT
        stt = DeepgramSTT(
            api_key=kwargs.get("deepgram_api_key"),
            model=kwargs.get("deepgram_model", "nova-2"),
        )
    elif stt_provider == "openai":
        from ravenvoice.providers.openai_provider import OpenAISTT
        stt = OpenAISTT(api_key=kwargs.get("openai_api_key"))
    else:
        raise ValueError(f"Unknown STT provider: {stt_provider}")
    
    # Create TTS
    if tts_provider == "elevenlabs":
        from ravenvoice.providers.elevenlabs import ElevenLabsTTS
        tts = ElevenLabsTTS(
            api_key=kwargs.get("elevenlabs_api_key"),
            voice_id=kwargs.get("elevenlabs_voice_id", "rachel"),
        )
    elif tts_provider == "openai":
        from ravenvoice.providers.openai_provider import OpenAITTS
        tts = OpenAITTS(
            api_key=kwargs.get("openai_api_key"),
            voice=kwargs.get("openai_voice", "nova"),
        )
    else:
        raise ValueError(f"Unknown TTS provider: {tts_provider}")
    
    # Create Brain
    if brain_provider == "langgraph":
        from ravenvoice.providers.langgraph import LangGraphBrain
        brain = LangGraphBrain(
            api_url=kwargs.get("langgraph_api_url", "http://localhost:2024"),
            assistant_id=kwargs.get("langgraph_assistant_id", "norns"),
        )
    else:
        raise ValueError(f"Unknown brain provider: {brain_provider}")
    
    # Create config
    config = VoiceAgentConfig(
        livekit_url=kwargs.get("livekit_url", "ws://localhost:7880"),
        livekit_api_key=kwargs.get("livekit_api_key", "devkey"),
        livekit_api_secret=kwargs.get("livekit_api_secret", "secret"),
        room_name=kwargs.get("room_name"),
        participant_name=kwargs.get("participant_name", "VoiceAgent"),
    )
    
    return VoiceAgent(stt=stt, tts=tts, brain=brain, config=config)

