"""
Base Provider Classes — Abstract interfaces for STT, TTS, and Brain.

Implement these interfaces to add new providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Optional, Any

from pydantic import BaseModel


class AudioFormat(str, Enum):
    """Supported audio formats."""
    PCM_16KHZ = "pcm_16khz"
    PCM_24KHZ = "pcm_24khz"
    PCM_48KHZ = "pcm_48khz"
    MP3 = "mp3"
    OPUS = "opus"
    WAV = "wav"


@dataclass
class STTResult:
    """Result from speech-to-text transcription."""
    
    text: str
    is_final: bool = True
    confidence: float = 1.0
    
    # Timing information
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    # Word-level details (if available)
    words: list[dict] = field(default_factory=list)
    
    # Provider metadata
    provider: str = "unknown"
    raw_response: Optional[dict] = None


@dataclass
class TTSResult:
    """Result from text-to-speech synthesis."""
    
    audio: bytes
    format: AudioFormat = AudioFormat.PCM_16KHZ
    sample_rate: int = 16000
    duration_seconds: Optional[float] = None
    
    # Provider metadata
    provider: str = "unknown"
    voice_id: Optional[str] = None


class BrainResponse(BaseModel):
    """Response from the AI brain."""
    
    text: str
    thread_id: Optional[str] = None
    
    # For multi-persona systems (like Norns)
    persona: str = "assistant"
    
    # Tool calls made during response
    tool_calls: Optional[list[dict]] = None
    
    # Should this response be spoken?
    should_speak: bool = True
    
    # Provider metadata
    provider: str = "unknown"
    model: Optional[str] = None
    tokens_used: Optional[int] = None


class BaseSTT(ABC):
    """
    Abstract base class for Speech-to-Text providers.
    
    Implement this to add support for new STT services.
    
    Example:
        class MySTT(BaseSTT):
            @property
            def name(self) -> str:
                return "my_stt"
            
            async def transcribe(self, audio: bytes, format: AudioFormat) -> STTResult:
                # Call your STT API
                text = await my_api.transcribe(audio)
                return STTResult(text=text, provider=self.name)
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this provider."""
        pass
    
    @abstractmethod
    async def transcribe(
        self,
        audio: bytes,
        format: AudioFormat = AudioFormat.PCM_16KHZ,
        language: str = "en",
    ) -> STTResult:
        """
        Transcribe audio to text.
        
        Args:
            audio: Raw audio bytes
            format: Audio format
            language: Language code (e.g., "en", "es")
            
        Returns:
            STTResult with transcribed text
        """
        pass
    
    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        format: AudioFormat = AudioFormat.PCM_16KHZ,
        language: str = "en",
    ) -> AsyncIterator[STTResult]:
        """
        Stream transcription of audio.
        
        Override for providers that support streaming STT.
        Default implementation buffers audio and calls transcribe().
        
        Args:
            audio_stream: Async iterator of audio chunks
            format: Audio format
            language: Language code
            
        Yields:
            STTResult objects (may include partial results)
        """
        # Default: buffer and transcribe
        buffer = bytearray()
        async for chunk in audio_stream:
            buffer.extend(chunk)
        
        if buffer:
            result = await self.transcribe(bytes(buffer), format, language)
            yield result
    
    async def initialize(self) -> None:
        """Initialize the provider (optional setup)."""
        pass
    
    async def shutdown(self) -> None:
        """Cleanup resources."""
        pass


class BaseTTS(ABC):
    """
    Abstract base class for Text-to-Speech providers.
    
    Implement this to add support for new TTS services.
    
    Example:
        class MyTTS(BaseTTS):
            @property
            def name(self) -> str:
                return "my_tts"
            
            async def synthesize(self, text: str) -> TTSResult:
                audio = await my_api.synthesize(text)
                return TTSResult(audio=audio, provider=self.name)
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this provider."""
        pass
    
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
    ) -> TTSResult:
        """
        Synthesize text to speech.
        
        Args:
            text: Text to speak
            voice_id: Optional voice identifier
            
        Returns:
            TTSResult with audio bytes
        """
        pass
    
    async def synthesize_stream(
        self,
        text: str,
        voice_id: Optional[str] = None,
    ) -> AsyncIterator[bytes]:
        """
        Stream synthesized audio.
        
        Override for providers that support streaming TTS.
        Default implementation calls synthesize() and yields the result.
        
        Args:
            text: Text to speak
            voice_id: Optional voice identifier
            
        Yields:
            Audio chunks
        """
        result = await self.synthesize(text, voice_id)
        yield result.audio
    
    async def initialize(self) -> None:
        """Initialize the provider (optional setup)."""
        pass
    
    async def shutdown(self) -> None:
        """Cleanup resources."""
        pass


class BaseBrain(ABC):
    """
    Abstract base class for AI Brain providers.
    
    The brain handles the conversational AI logic, generating
    responses to user speech.
    
    Example:
        class MyBrain(BaseBrain):
            @property
            def name(self) -> str:
                return "my_brain"
            
            async def think(self, text: str, thread_id: str) -> BrainResponse:
                response = await my_llm.chat(text)
                return BrainResponse(text=response, thread_id=thread_id)
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this provider."""
        pass
    
    @abstractmethod
    async def think(
        self,
        text: str,
        thread_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> BrainResponse:
        """
        Generate a response to user input.
        
        Args:
            text: User's transcribed speech
            thread_id: Conversation thread ID for continuity
            context: Additional context (user info, room info, etc.)
            
        Returns:
            BrainResponse with text to speak
        """
        pass
    
    async def think_stream(
        self,
        text: str,
        thread_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> AsyncIterator[str]:
        """
        Stream a response token by token.
        
        Override for providers that support streaming.
        Default implementation calls think() and yields the full response.
        
        Args:
            text: User's transcribed speech
            thread_id: Conversation thread ID
            context: Additional context
            
        Yields:
            Response tokens
        """
        response = await self.think(text, thread_id, context)
        yield response.text
    
    async def initialize(self) -> None:
        """Initialize the provider (optional setup)."""
        pass
    
    async def shutdown(self) -> None:
        """Cleanup resources."""
        pass

