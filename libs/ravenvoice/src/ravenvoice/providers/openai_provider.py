"""
OpenAI Providers — STT and TTS via OpenAI API.

Provides Whisper (STT) and TTS capabilities.
"""

from typing import AsyncIterator, Optional

import structlog

from ravenvoice.providers.base import (
    BaseSTT,
    BaseTTS,
    STTResult,
    TTSResult,
    AudioFormat,
)

logger = structlog.get_logger(__name__)

# Optional import
try:
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class OpenAISTT(BaseSTT):
    """
    OpenAI Whisper Speech-to-Text provider.
    
    Features:
    - High-quality transcription
    - Multiple languages
    - Translation to English
    
    Configuration:
        stt = OpenAISTT(
            api_key="sk-...",
            model="whisper-1",
        )
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "whisper-1",
        language: str = "en",
    ):
        """
        Initialize OpenAI Whisper STT.
        
        Args:
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            model: Model to use (whisper-1)
            language: Language hint
        """
        if not HAS_OPENAI:
            raise ImportError("openai not installed. Run: pip install openai")
        
        import os
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError("OpenAI API key required")
        
        self._model = model
        self._language = language
        self._client: Optional[AsyncOpenAI] = None
    
    @property
    def name(self) -> str:
        return "openai_whisper"
    
    async def initialize(self) -> None:
        """Initialize OpenAI client."""
        self._client = AsyncOpenAI(api_key=self._api_key)
        logger.info("openai_whisper_initialized", model=self._model)
    
    async def shutdown(self) -> None:
        """Cleanup."""
        if self._client:
            await self._client.close()
            self._client = None
    
    async def transcribe(
        self,
        audio: bytes,
        format: AudioFormat = AudioFormat.PCM_16KHZ,
        language: str = None,
    ) -> STTResult:
        """Transcribe audio using Whisper."""
        if self._client is None:
            await self.initialize()
        
        try:
            # Whisper expects a file-like object
            import io
            
            # Determine file extension
            ext = "wav"
            if format == AudioFormat.MP3:
                ext = "mp3"
            elif format == AudioFormat.OPUS:
                ext = "opus"
            
            # Create file tuple for upload
            audio_file = (f"audio.{ext}", io.BytesIO(audio), f"audio/{ext}")
            
            response = await self._client.audio.transcriptions.create(
                model=self._model,
                file=audio_file,
                language=language or self._language,
                response_format="verbose_json",
            )
            
            return STTResult(
                text=response.text,
                is_final=True,
                provider=self.name,
                raw_response=response.model_dump() if hasattr(response, 'model_dump') else None,
            )
            
        except Exception as e:
            logger.error("openai_whisper_failed", error=str(e))
            raise


class OpenAITTS(BaseTTS):
    """
    OpenAI Text-to-Speech provider.
    
    Features:
    - Multiple voices
    - HD quality option
    - Fast response
    
    Configuration:
        tts = OpenAITTS(
            api_key="sk-...",
            voice="nova",
            model="tts-1-hd",
        )
    """
    
    # Available voices
    VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        voice: str = "nova",
        model: str = "tts-1",
        speed: float = 1.0,
    ):
        """
        Initialize OpenAI TTS.
        
        Args:
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
            model: Model to use (tts-1, tts-1-hd)
            speed: Speech speed (0.25 to 4.0)
        """
        if not HAS_OPENAI:
            raise ImportError("openai not installed. Run: pip install openai")
        
        import os
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError("OpenAI API key required")
        
        self._voice = voice
        self._model = model
        self._speed = speed
        self._client: Optional[AsyncOpenAI] = None
    
    @property
    def name(self) -> str:
        return "openai_tts"
    
    async def initialize(self) -> None:
        """Initialize OpenAI client."""
        self._client = AsyncOpenAI(api_key=self._api_key)
        logger.info("openai_tts_initialized", voice=self._voice, model=self._model)
    
    async def shutdown(self) -> None:
        """Cleanup."""
        if self._client:
            await self._client.close()
            self._client = None
    
    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
    ) -> TTSResult:
        """Synthesize text to speech."""
        if self._client is None:
            await self.initialize()
        
        voice = voice_id or self._voice
        
        try:
            response = await self._client.audio.speech.create(
                model=self._model,
                voice=voice,
                input=text,
                speed=self._speed,
                response_format="pcm",  # 24kHz PCM
            )
            
            audio = await response.read()
            
            return TTSResult(
                audio=audio,
                format=AudioFormat.PCM_24KHZ,
                sample_rate=24000,
                provider=self.name,
                voice_id=voice,
            )
            
        except Exception as e:
            logger.error("openai_tts_failed", error=str(e))
            raise
    
    async def synthesize_stream(
        self,
        text: str,
        voice_id: Optional[str] = None,
    ) -> AsyncIterator[bytes]:
        """Stream synthesized audio."""
        if self._client is None:
            await self.initialize()
        
        voice = voice_id or self._voice
        
        try:
            response = await self._client.audio.speech.create(
                model=self._model,
                voice=voice,
                input=text,
                speed=self._speed,
                response_format="pcm",
            )
            
            async for chunk in response.iter_bytes(chunk_size=4096):
                yield chunk
                
        except Exception as e:
            logger.error("openai_tts_stream_failed", error=str(e))
            raise

