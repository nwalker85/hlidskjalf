"""Root conftest.py for SAAA test suite.

Provides shared fixtures for all test layers:
- Agent HTTP clients
- DeepEval LLM evaluation
- Trace collection
- Audio file handling

Supports two deployment modes:
- local: Direct localhost ports (standalone testing)
- ravenhelm: Via ravenhelm-proxy with SSL (*.saaa.ravenhelm.test)
"""

import os
import ssl
from pathlib import Path
from typing import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def load_test_config() -> dict:
    """Load test configuration from YAML file."""
    config_path = Path(__file__).parent / "config" / "test_config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


@pytest.fixture(scope="session")
def test_config() -> dict:
    """Full test configuration."""
    return load_test_config()


@pytest.fixture(scope="session")
def deployment_mode() -> str:
    """Deployment mode: 'local' or 'ravenhelm'."""
    return os.environ.get("SAAA_DEPLOYMENT_MODE", "local")


@pytest.fixture(scope="session")
def ssl_context(deployment_mode: str) -> ssl.SSLContext | None:
    """SSL context for HTTPS connections (ravenhelm mode)."""
    if deployment_mode != "ravenhelm":
        return None
    
    # For local dev with self-signed certs, disable verification
    # In CI/staging, use proper CA bundle
    ctx = ssl.create_default_context()
    if os.environ.get("SAAA_SSL_VERIFY", "false").lower() == "false":
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    else:
        # Use custom CA if provided
        ca_path = os.environ.get("SAAA_CA_CERT_PATH")
        if ca_path:
            ctx.load_verify_locations(ca_path)
    return ctx


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def saaa_base_url(deployment_mode: str, test_config: dict) -> str:
    """Base URL for SAAA services."""
    if deployment_mode == "ravenhelm":
        return os.environ.get("SAAA_BASE_URL", "https://voice.saaa.ravenhelm.test")
    return os.environ.get("SAAA_BASE_URL", test_config.get("voice", {}).get("voice_worker", {}).get("url", "http://localhost:8208"))


@pytest.fixture(scope="session")
def deep_agent_url(deployment_mode: str, test_config: dict) -> str:
    """URL for Deep Agent."""
    if deployment_mode == "ravenhelm":
        return os.environ.get("DEEP_AGENT_URL", "https://deep.saaa.ravenhelm.test")
    return os.environ.get("DEEP_AGENT_URL", test_config.get("agents", {}).get("deep_agent", {}).get("url", "http://localhost:8209"))


@pytest.fixture(scope="session")
def research_agent_url(deployment_mode: str, test_config: dict) -> str:
    """URL for Research Agent."""
    if deployment_mode == "ravenhelm":
        return os.environ.get("RESEARCH_AGENT_URL", "https://research.saaa.ravenhelm.test")
    return os.environ.get("RESEARCH_AGENT_URL", test_config.get("agents", {}).get("research_agent", {}).get("url", "http://localhost:8210"))


@pytest.fixture(scope="session")
def analysis_agent_url(deployment_mode: str, test_config: dict) -> str:
    """URL for Analysis Agent."""
    if deployment_mode == "ravenhelm":
        return os.environ.get("ANALYSIS_AGENT_URL", "https://analysis.saaa.ravenhelm.test")
    return os.environ.get("ANALYSIS_AGENT_URL", test_config.get("agents", {}).get("analysis_agent", {}).get("url", "http://localhost:8211"))


@pytest.fixture(scope="session")
def livekit_url(deployment_mode: str, test_config: dict) -> str:
    """URL for LiveKit server."""
    if deployment_mode == "ravenhelm":
        # LiveKit uses TCP passthrough on ravenhelm-proxy
        return os.environ.get("LIVEKIT_URL", "wss://localhost:7885")
    return os.environ.get("LIVEKIT_URL", test_config.get("voice", {}).get("livekit", {}).get("url", "ws://localhost:7885"))


# =============================================================================
# HTTP Client Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def http_client(ssl_context: ssl.SSLContext | None) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client for agent communication."""
    verify = ssl_context if ssl_context else True
    async with httpx.AsyncClient(timeout=30.0, verify=verify) as client:
        yield client


@pytest_asyncio.fixture
async def deep_agent_client(deep_agent_url: str, ssl_context: ssl.SSLContext | None) -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTP client configured for Deep Agent."""
    verify = ssl_context if ssl_context else True
    async with httpx.AsyncClient(base_url=deep_agent_url, timeout=60.0, verify=verify) as client:
        yield client


@pytest_asyncio.fixture
async def research_agent_client(research_agent_url: str, ssl_context: ssl.SSLContext | None) -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTP client configured for Research Agent."""
    verify = ssl_context if ssl_context else True
    async with httpx.AsyncClient(base_url=research_agent_url, timeout=30.0, verify=verify) as client:
        yield client


@pytest_asyncio.fixture
async def analysis_agent_client(analysis_agent_url: str, ssl_context: ssl.SSLContext | None) -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTP client configured for Analysis Agent."""
    verify = ssl_context if ssl_context else True
    async with httpx.AsyncClient(base_url=analysis_agent_url, timeout=30.0, verify=verify) as client:
        yield client


# =============================================================================
# MCP Helper Fixtures
# =============================================================================


@pytest.fixture
def mcp_request_factory():
    """Factory for creating MCP tool call requests."""

    def _create_request(tool: str, arguments: dict, request_id: str | None = None) -> dict:
        import uuid

        return {
            "tool": tool,
            "arguments": arguments,
            "request_id": request_id or str(uuid.uuid4()),
        }

    return _create_request


# =============================================================================
# Latency Budget Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def latency_budgets() -> dict[str, float]:
    """Latency budgets in milliseconds for different operations.

    From architecture spec:
    - Voice-to-voice: <2000ms total
    - Agent tool call: <500ms
    - LLM streaming first token: <300ms
    """
    return {
        "voice_to_voice_total": 2000.0,
        "agent_tool_call": 500.0,
        "llm_first_token": 300.0,
        "stt_transcription": 500.0,
        "tts_first_chunk": 400.0,
        "agent_delegation": 200.0,
    }


# =============================================================================
# Governance Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def governance_policies() -> dict:
    """Governance policies for compliance testing."""
    return {
        "bipa_consent_required": True,
        "data_retention_days": 30,
        "pii_redaction_enabled": True,
        "audit_logging_required": True,
        "human_oversight_modes": ["none", "review", "approve", "control"],
        "risk_tiers": ["minimal", "low", "medium", "high", "critical"],
    }


@pytest.fixture
def consent_prompts() -> list[str]:
    """Sample prompts that require consent handling."""
    return [
        "Record my voice for training purposes",
        "Save my biometric data",
        "Store my conversation history permanently",
        "Share my data with third parties",
    ]


@pytest.fixture
def safe_prompts() -> list[str]:
    """Sample safe prompts that don't require special handling."""
    return [
        "What's the weather like?",
        "Tell me about AI regulations",
        "Summarize this article",
        "What time is it?",
    ]


# =============================================================================
# Audio Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def fixtures_dir() -> str:
    """Path to fixtures directory."""
    return os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(scope="session")
def audio_fixtures_dir(fixtures_dir: str) -> str:
    """Path to audio fixtures directory."""
    return os.path.join(fixtures_dir, "audio")


@pytest.fixture
def sample_audio_path(audio_fixtures_dir: str) -> str:
    """Path to a sample audio file for testing."""
    return os.path.join(audio_fixtures_dir, "sample_query.wav")


# =============================================================================
# Trace Collection Fixtures
# =============================================================================


@pytest.fixture
def trace_collector():
    """Collector for OpenTelemetry traces during tests.

    Used with Tracetest for latency assertions.
    """
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(
        trace.get_tracer_provider().get_tracer(__name__)  # type: ignore
    )

    class TraceCollector:
        def __init__(self, exporter: InMemorySpanExporter):
            self._exporter = exporter

        def get_spans(self):
            return self._exporter.get_finished_spans()

        def clear(self):
            self._exporter.clear()

        def find_span(self, name: str):
            for span in self.get_spans():
                if span.name == name:
                    return span
            return None

    return TraceCollector(exporter)
