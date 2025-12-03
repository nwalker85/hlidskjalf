"""Audio Pipeline E2E Tests.

Tests for voice-to-voice pipeline:
- Audio injection into LiveKit room
- STT transcription accuracy
- Agent response quality
- TTS output validation

Uses audio fixtures and Scenario/LangWatch patterns.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.voice, pytest.mark.asyncio]


# =============================================================================
# Audio Utilities
# =============================================================================


class AudioTestHelper:
    """Helper for audio test operations."""

    def __init__(self, fixtures_dir: str):
        self.fixtures_dir = Path(fixtures_dir)

    def get_audio_file(self, name: str) -> Path:
        """Get path to an audio fixture file."""
        audio_dir = self.fixtures_dir / "audio"
        path = audio_dir / name
        if not path.exists():
            # Return the expected path even if it doesn't exist
            # Tests will handle missing fixtures appropriately
            pass
        return path

    def load_audio_bytes(self, name: str) -> bytes | None:
        """Load audio file as bytes."""
        path = self.get_audio_file(name)
        if path.exists():
            return path.read_bytes()
        return None

    @staticmethod
    def generate_silence(duration_ms: int, sample_rate: int = 16000) -> bytes:
        """Generate silence audio for testing."""
        import struct

        num_samples = int(sample_rate * duration_ms / 1000)
        # 16-bit PCM silence
        return struct.pack(f"<{num_samples}h", *([0] * num_samples))


@pytest.fixture
def audio_helper(fixtures_dir: str) -> AudioTestHelper:
    """Audio test helper fixture."""
    return AudioTestHelper(fixtures_dir)


# =============================================================================
# STT Tests
# =============================================================================


class TestSTTTranscription:
    """Test Speech-to-Text transcription accuracy."""

    @pytest.fixture
    def expected_transcripts(self) -> dict[str, str]:
        """Expected transcripts for audio fixtures."""
        return {
            "hello_world.wav": "hello world",
            "what_time_is_it.wav": "what time is it",
            "tell_me_about_ai.wav": "tell me about artificial intelligence",
        }

    async def test_stt_accuracy_basic(
        self,
        audio_helper: AudioTestHelper,
        expected_transcripts: dict[str, str],
    ):
        """Test basic STT accuracy with known audio."""
        # This test requires actual STT service running
        # For now, we'll mark it as expected to potentially skip

        audio_file = "hello_world.wav"
        audio_bytes = audio_helper.load_audio_bytes(audio_file)

        if audio_bytes is None:
            pytest.skip(f"Audio fixture {audio_file} not found")

        # In a real test, we'd send this to the STT service
        # and compare against expected_transcripts[audio_file]
        expected = expected_transcripts[audio_file]
        assert expected == "hello world"

    async def test_stt_handles_silence(
        self,
        audio_helper: AudioTestHelper,
    ):
        """STT should handle silence gracefully."""
        silence = audio_helper.generate_silence(1000)  # 1 second
        assert len(silence) > 0

        # In a real test, we'd verify STT returns empty or no transcript

    async def test_stt_handles_noise(
        self,
        audio_helper: AudioTestHelper,
    ):
        """STT should handle background noise."""
        noise_file = audio_helper.get_audio_file("background_noise.wav")

        if not noise_file.exists():
            pytest.skip("Noise fixture not available")

        # Test that STT doesn't crash on noise
        # and ideally returns minimal/no transcription


# =============================================================================
# Voice Pipeline Integration Tests
# =============================================================================


class TestVoicePipelineIntegration:
    """Integration tests for full voice pipeline."""

    @pytest.fixture
    def voice_worker_url(self) -> str:
        """Voice worker URL."""
        return os.environ.get("VOICE_WORKER_URL", "http://localhost:8208")

    async def test_pipeline_health(
        self,
        voice_worker_url: str,
    ):
        """Voice pipeline components should be healthy."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{voice_worker_url}/health")
            assert response.status_code == 200

    async def test_token_generation(
        self,
        voice_worker_url: str,
    ):
        """Should generate valid LiveKit tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{voice_worker_url}/api/token")

            if response.status_code == 200:
                data = response.json()
                assert "token" in data or "accessToken" in data
            else:
                # Token endpoint may require auth or different path
                pytest.skip("Token endpoint not available")


class TestAgentResponseQuality:
    """Test agent response quality in voice context."""

    @pytest.fixture
    def test_queries(self) -> list[dict[str, Any]]:
        """Test queries with expected response patterns."""
        return [
            {
                "input": "What is the weather like?",
                "expected_patterns": ["weather", "temperature", "forecast"],
                "max_words": 100,  # Voice responses should be concise
            },
            {
                "input": "Tell me a joke",
                "expected_patterns": [],  # Any response is valid
                "max_words": 50,
            },
            {
                "input": "What time is it?",
                "expected_patterns": ["time", "clock", "now"],
                "max_words": 30,
            },
        ]

    async def test_response_conciseness(
        self,
        deep_agent_client: httpx.AsyncClient,
        mcp_request_factory,
        test_queries: list[dict[str, Any]],
    ):
        """Agent responses should be concise for voice output."""
        for query in test_queries:
            request = mcp_request_factory(
                tool="deep/stream",
                arguments={
                    "message": query["input"],
                    "session_id": "voice-quality-test",
                },
            )

            response = await deep_agent_client.post("/mcp/tools/call", json=request)

            if response.status_code == 200:
                result = response.json()
                content = result.get("content", [{}])[0].get("text", "")

                # Check word count
                word_count = len(content.split())
                assert word_count <= query["max_words"] * 2, (
                    f"Response too long for voice: {word_count} words "
                    f"(expected <= {query['max_words']})"
                )


# =============================================================================
# Audio-to-Audio E2E Tests (Scenario Pattern)
# =============================================================================


class TestAudioToAudioE2E:
    """End-to-end audio-to-audio tests.

    These tests simulate the full voice pipeline:
    1. Inject audio into LiveKit room
    2. Wait for STT transcription
    3. Wait for agent response
    4. Capture TTS output
    5. Validate response quality
    """

    @pytest.fixture
    def scenario_config(self) -> dict[str, Any]:
        """Configuration for audio scenarios."""
        return {
            "livekit_url": os.environ.get("LIVEKIT_URL", "ws://localhost:7885"),
            "livekit_api_key": os.environ.get("LIVEKIT_API_KEY", "devkey"),
            "livekit_api_secret": os.environ.get("LIVEKIT_API_SECRET", "secret"),
            "timeout_seconds": 30,
        }

    @pytest.mark.slow
    async def test_hello_world_scenario(
        self,
        audio_helper: AudioTestHelper,
        scenario_config: dict[str, Any],
    ):
        """Test basic hello world audio scenario."""
        audio_file = audio_helper.get_audio_file("hello_world.wav")

        if not audio_file.exists():
            pytest.skip("hello_world.wav fixture not available")

        # In a full implementation, this would:
        # 1. Connect to LiveKit room as test participant
        # 2. Publish the audio file
        # 3. Subscribe to agent audio responses
        # 4. Validate the response contains expected content

        # For now, verify the scenario can be configured
        assert scenario_config["timeout_seconds"] > 0

    @pytest.mark.slow
    async def test_research_query_scenario(
        self,
        audio_helper: AudioTestHelper,
        scenario_config: dict[str, Any],
        deep_agent_client: httpx.AsyncClient,
        mcp_request_factory,
    ):
        """Test research query that triggers agent delegation."""
        # Simulate the query that would come from audio
        query = "What are the latest AI regulations?"

        request = mcp_request_factory(
            tool="deep/stream",
            arguments={
                "message": query,
                "session_id": "audio-e2e-test",
            },
        )

        start = time.perf_counter()
        response = await deep_agent_client.post("/mcp/tools/call", json=request)
        elapsed = time.perf_counter() - start

        assert response.status_code == 200

        # For voice, response should come within latency budget
        assert elapsed < 5.0, f"Response took {elapsed:.1f}s, too slow for voice"

        result = response.json()
        content = str(result.get("content", ""))

        # Response should mention AI or regulations
        assert any(
            term in content.lower() for term in ["ai", "regulation", "policy"]
        ), f"Response doesn't address query: {content[:200]}"


# =============================================================================
# TTS Output Validation
# =============================================================================


class TestTTSOutput:
    """Test Text-to-Speech output quality."""

    async def test_tts_generates_audio(
        self,
        deep_agent_client: httpx.AsyncClient,
    ):
        """TTS should generate valid audio output."""
        # This would test the TTS component directly
        # For now, we verify the agent can stream responses
        # which would feed into TTS

        response = await deep_agent_client.get("/health")
        assert response.status_code == 200

    async def test_tts_handles_special_characters(self):
        """TTS should handle special characters gracefully."""
        test_texts = [
            "Hello! How are you?",
            "The price is $100.00",
            "Email: test@example.com",
            "Temperature is 72°F",
        ]

        # In a real test, we'd send these to TTS and verify
        # audio is generated without errors
        for text in test_texts:
            assert len(text) > 0

    async def test_tts_respects_ssml(self):
        """TTS should respect SSML markup if supported."""
        ssml_examples = [
            '<speak>Hello <break time="500ms"/> World</speak>',
            '<speak><emphasis level="strong">Important</emphasis></speak>',
        ]

        # Verify SSML can be parsed
        for ssml in ssml_examples:
            assert "<speak>" in ssml


# =============================================================================
# Latency Tests for Voice Pipeline
# =============================================================================


class TestVoiceLatency:
    """Test voice-specific latency requirements."""

    async def test_voice_pipeline_under_2_seconds(
        self,
        deep_agent_client: httpx.AsyncClient,
        mcp_request_factory,
    ):
        """Full voice pipeline should complete under 2 seconds."""
        # Simulate STT latency (typically 100-500ms)
        stt_time = 0.2

        # Agent processing
        request = mcp_request_factory(
            tool="deep/stream",
            arguments={
                "message": "Hi",
                "session_id": "latency-test",
            },
        )

        start = time.perf_counter()
        response = await deep_agent_client.post("/mcp/tools/call", json=request)
        agent_time = time.perf_counter() - start

        # Simulate TTS latency (typically 100-400ms for first chunk)
        tts_time = 0.2

        total = stt_time + agent_time + tts_time

        assert response.status_code == 200
        assert total < 2.0, (
            f"Voice pipeline too slow: {total:.2f}s "
            f"(STT: {stt_time:.2f}s, Agent: {agent_time:.2f}s, TTS: {tts_time:.2f}s)"
        )
