"""
Deepgram STT Provider — Speech-to-Text via Deepgram API.

https://developers.deepgram.com/
"""

from typing import AsyncIterator, Optional

import structlog

from ravenvoice.providers.base import BaseSTT, STTResult, AudioFormat

logger = structlog.get_logger(__name__)

# Optional import
try:
    from deepgram import DeepgramClient, PrerecordedOptions, LiveOptions
    HAS_DEEPGRAM = True
except ImportError:
    HAS_DEEPGRAM = False


class DeepgramSTT(BaseSTT):
    """
    Deepgram Speech-to-Text provider.
    
    Features:
    - High-quality transcription
    - Real-time streaming
    - Word-level timestamps
    - Speaker diarization
    
    Configuration:
        stt = DeepgramSTT(
            api_key="your-api-key",
            model="nova-2",
            language="en",
        )
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "nova-2",
        language: str = "en",
        punctuate: bool = True,
        diarize: bool = False,
        smart_format: bool = True,
    ):
        """
        Initialize Deepgram STT.
        
        Args:
            api_key: Deepgram API key (or set DEEPGRAM_API_KEY env var)
            model: Model to use (nova-2, nova, base, enhanced)
            language: Language code
            punctuate: Add punctuation
            diarize: Enable speaker diarization
            smart_format: Smart formatting (numbers, dates, etc.)
        """
        if not HAS_DEEPGRAM:
            raise ImportError("deepgram-sdk not installed. Run: pip install deepgram-sdk")
        
        import os
        self._api_key = api_key or os.environ.get("DEEPGRAM_API_KEY")
        if not self._api_key:
            raise ValueError("Deepgram API key required")
        
        self._model = model
        self._language = language
        self._punctuate = punctuate
        self._diarize = diarize
        self._smart_format = smart_format
        
        self._client: Optional[DeepgramClient] = None
    
    @property
    def name(self) -> str:
        return "deepgram"
    
    async def initialize(self) -> None:
        """Initialize Deepgram client."""
        self._client = DeepgramClient(self._api_key)
        logger.info("deepgram_initialized", model=self._model)
    
    async def shutdown(self) -> None:
        """Cleanup."""
        self._client = None
    
    def _get_sample_rate(self, format: AudioFormat) -> int:
        """Get sample rate from format."""
        rates = {
            AudioFormat.PCM_16KHZ: 16000,
            AudioFormat.PCM_24KHZ: 24000,
            AudioFormat.PCM_48KHZ: 48000,
        }
        return rates.get(format, 16000)
    
    async def transcribe(
        self,
        audio: bytes,
        format: AudioFormat = AudioFormat.PCM_16KHZ,
        language: str = None,
    ) -> STTResult:
        """Transcribe audio using Deepgram."""
        if self._client is None:
            await self.initialize()
        
        options = PrerecordedOptions(
            model=self._model,
            language=language or self._language,
            punctuate=self._punctuate,
            diarize=self._diarize,
            smart_format=self._smart_format,
        )
        
        try:
            # Determine MIME type
            mime_type = "audio/wav"
            if format in [AudioFormat.PCM_16KHZ, AudioFormat.PCM_24KHZ, AudioFormat.PCM_48KHZ]:
                sample_rate = self._get_sample_rate(format)
                mime_type = f"audio/raw;encoding=linear16;sample_rate={sample_rate}"
            elif format == AudioFormat.MP3:
                mime_type = "audio/mp3"
            elif format == AudioFormat.OPUS:
                mime_type = "audio/opus"
            
            response = await self._client.listen.asyncrest.v("1").transcribe_file(
                {"buffer": audio, "mimetype": mime_type},
                options,
            )
            
            # Extract results
            result = response.results
            if result and result.channels and result.channels[0].alternatives:
                alt = result.channels[0].alternatives[0]
                
                # Extract words
                words = []
                if hasattr(alt, 'words') and alt.words:
                    words = [
                        {
                            "word": w.word,
                            "start": w.start,
                            "end": w.end,
                            "confidence": w.confidence,
                        }
                        for w in alt.words
                    ]
                
                return STTResult(
                    text=alt.transcript,
                    is_final=True,
                    confidence=alt.confidence,
                    words=words,
                    provider=self.name,
                    raw_response=response.to_dict() if hasattr(response, 'to_dict') else None,
                )
            
            return STTResult(text="", is_final=True, provider=self.name)
            
        except Exception as e:
            logger.error("deepgram_transcribe_failed", error=str(e))
            raise
    
    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        format: AudioFormat = AudioFormat.PCM_16KHZ,
        language: str = None,
    ) -> AsyncIterator[STTResult]:
        """
        Stream transcription using Deepgram Live API.
        
        Yields partial and final results as they arrive.
        """
        if self._client is None:
            await self.initialize()
        
        sample_rate = self._get_sample_rate(format)
        
        options = LiveOptions(
            model=self._model,
            language=language or self._language,
            punctuate=self._punctuate,
            smart_format=self._smart_format,
            encoding="linear16",
            sample_rate=sample_rate,
            channels=1,
            interim_results=True,
        )
        
        try:
            connection = self._client.listen.asynclive.v("1")
            
            async def on_message(result_self, result, **kwargs):
                """Handle incoming transcription results."""
                if result.channel and result.channel.alternatives:
                    alt = result.channel.alternatives[0]
                    yield STTResult(
                        text=alt.transcript,
                        is_final=result.is_final,
                        confidence=alt.confidence if hasattr(alt, 'confidence') else 1.0,
                        provider=self.name,
                    )
            
            await connection.start(options)
            
            # Send audio chunks
            async for chunk in audio_stream:
                await connection.send(chunk)
            
            await connection.finish()
            
        except Exception as e:
            logger.error("deepgram_stream_failed", error=str(e))
            raise

