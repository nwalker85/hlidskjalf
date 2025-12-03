"""
ElevenLabs TTS Provider — Text-to-Speech via ElevenLabs API.

https://elevenlabs.io/docs
"""

from typing import AsyncIterator, Optional

import structlog

from ravenvoice.providers.base import BaseTTS, TTSResult, AudioFormat

logger = structlog.get_logger(__name__)

# Optional import
try:
    from elevenlabs import AsyncElevenLabs
    from elevenlabs.types import VoiceSettings
    HAS_ELEVENLABS = True
except ImportError:
    HAS_ELEVENLABS = False


# Well-known voice IDs
VOICES = {
    "rachel": "21m00Tcm4TlvDq8ikWAM",  # Default female
    "adam": "pNInz6obpgDQGcFmaJgB",     # Default male
    "bella": "EXAVITQu4vr4xnSDxMaL",
    "sam": "yoZ06aMxZJJ28mfd3POQ",
    "josh": "TxGEqnHWrfWFTfGW9XjX",
    "elli": "MF3mGyEYCl7XYWbV9V6O",
}


class ElevenLabsTTS(BaseTTS):
    """
    ElevenLabs Text-to-Speech provider.
    
    Features:
    - High-quality neural voices
    - Voice cloning support
    - Streaming audio
    - Multiple output formats
    
    Configuration:
        tts = ElevenLabsTTS(
            api_key="your-api-key",
            voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel
            model_id="eleven_turbo_v2",
        )
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",  # Rachel
        model_id: str = "eleven_turbo_v2_5",
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0,
        output_format: str = "pcm_16000",
    ):
        """
        Initialize ElevenLabs TTS.
        
        Args:
            api_key: ElevenLabs API key (or set ELEVEN_API_KEY env var)
            voice_id: Voice ID or name from VOICES dict
            model_id: Model to use (eleven_turbo_v2_5, eleven_multilingual_v2)
            stability: Voice stability (0-1)
            similarity_boost: Voice similarity boost (0-1)
            style: Style exaggeration (0-1)
            output_format: Audio format (pcm_16000, mp3_44100, etc.)
        """
        if not HAS_ELEVENLABS:
            raise ImportError("elevenlabs not installed. Run: pip install elevenlabs")
        
        import os
        self._api_key = api_key or os.environ.get("ELEVEN_API_KEY")
        if not self._api_key:
            raise ValueError("ElevenLabs API key required")
        
        # Resolve voice name to ID
        self._voice_id = VOICES.get(voice_id.lower(), voice_id)
        self._model_id = model_id
        self._stability = stability
        self._similarity_boost = similarity_boost
        self._style = style
        self._output_format = output_format
        
        self._client: Optional[AsyncElevenLabs] = None
    
    @property
    def name(self) -> str:
        return "elevenlabs"
    
    async def initialize(self) -> None:
        """Initialize ElevenLabs client."""
        self._client = AsyncElevenLabs(api_key=self._api_key)
        logger.info("elevenlabs_initialized", voice_id=self._voice_id, model=self._model_id)
    
    async def shutdown(self) -> None:
        """Cleanup."""
        self._client = None
    
    def _get_audio_format(self) -> AudioFormat:
        """Convert output format to AudioFormat."""
        if "pcm_16000" in self._output_format:
            return AudioFormat.PCM_16KHZ
        elif "pcm_24000" in self._output_format:
            return AudioFormat.PCM_24KHZ
        elif "pcm_44100" in self._output_format or "pcm_48000" in self._output_format:
            return AudioFormat.PCM_48KHZ
        elif "mp3" in self._output_format:
            return AudioFormat.MP3
        return AudioFormat.PCM_16KHZ
    
    def _get_sample_rate(self) -> int:
        """Extract sample rate from format."""
        import re
        match = re.search(r'(\d+)', self._output_format)
        if match:
            return int(match.group(1))
        return 16000
    
    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
    ) -> TTSResult:
        """Synthesize text to speech."""
        if self._client is None:
            await self.initialize()
        
        voice = VOICES.get((voice_id or "").lower(), voice_id) or self._voice_id
        
        try:
            voice_settings = VoiceSettings(
                stability=self._stability,
                similarity_boost=self._similarity_boost,
                style=self._style,
            )
            
            audio_generator = await self._client.text_to_speech.convert(
                voice_id=voice,
                text=text,
                model_id=self._model_id,
                voice_settings=voice_settings,
                output_format=self._output_format,
            )
            
            # Collect all audio chunks
            audio_chunks = []
            async for chunk in audio_generator:
                audio_chunks.append(chunk)
            
            audio = b"".join(audio_chunks)
            
            return TTSResult(
                audio=audio,
                format=self._get_audio_format(),
                sample_rate=self._get_sample_rate(),
                provider=self.name,
                voice_id=voice,
            )
            
        except Exception as e:
            logger.error("elevenlabs_synthesize_failed", error=str(e))
            raise
    
    async def synthesize_stream(
        self,
        text: str,
        voice_id: Optional[str] = None,
    ) -> AsyncIterator[bytes]:
        """Stream synthesized audio."""
        if self._client is None:
            await self.initialize()
        
        voice = VOICES.get((voice_id or "").lower(), voice_id) or self._voice_id
        
        try:
            voice_settings = VoiceSettings(
                stability=self._stability,
                similarity_boost=self._similarity_boost,
                style=self._style,
            )
            
            audio_generator = await self._client.text_to_speech.convert(
                voice_id=voice,
                text=text,
                model_id=self._model_id,
                voice_settings=voice_settings,
                output_format=self._output_format,
            )
            
            async for chunk in audio_generator:
                yield chunk
                
        except Exception as e:
            logger.error("elevenlabs_stream_failed", error=str(e))
            raise
    
    @classmethod
    def list_voices(cls) -> dict[str, str]:
        """List well-known voice names and IDs."""
        return VOICES.copy()

