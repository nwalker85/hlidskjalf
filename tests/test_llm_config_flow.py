import json
import pytest

from src.memory.huginn.state_agent import HuginnStateAgent, LLMConfiguration, LLMModelConfig
from src.norns.llm_config_registry import LLMConfigRegistry
from src.norns.squad_schema import Topics


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def setex(self, key, ttl, value):
        self.store[key] = value


class FakeProducer:
    def __init__(self):
        self.sent = []

    async def send_and_wait(self, topic, payload):
        self.sent.append((topic, payload))


@pytest.mark.asyncio
async def test_update_llm_config_emits_event(monkeypatch):
    agent = HuginnStateAgent(redis_url="redis://redis:6379/7", kafka_bootstrap="test")
    fake_redis = FakeRedis()
    fake_producer = FakeProducer()

    async def fake_get_redis(self):
        return fake_redis

    async def fake_get_kafka(self):
        return fake_producer

    monkeypatch.setattr(HuginnStateAgent, "_get_redis", fake_get_redis, raising=False)
    monkeypatch.setattr(HuginnStateAgent, "_get_kafka", fake_get_kafka, raising=False)

    config = LLMConfiguration(
        reasoning=LLMModelConfig(provider="ollama", model="llama3.1:8b", temperature=0.2)
    )

    await agent.update_llm_config("session-test", config)

    # Redis received serialized state
    stored = json.loads(fake_redis.store[agent._redis_key("session-test")])
    assert stored["llm_config"]["reasoning"]["model"] == "llama3.1:8b"

    # Kafka event emitted with correct topic/payload
    assert fake_producer.sent
    topic, payload = fake_producer.sent[0]
    assert topic == Topics.LLM_CONFIG
    event = json.loads(payload.decode("utf-8"))
    assert event["type"] == "llm.config.changed"
    assert event["session_id"] == "session-test"


def test_llm_config_registry_ingest_event():
    registry = LLMConfigRegistry(bootstrap_servers=None)
    event = {
        "type": "llm.config.changed",
        "session_id": "session-x",
        "config": {
            "reasoning": {"provider": "ollama", "model": "llama3.1:8b", "temperature": 0.2},
            "tools": {"provider": "ollama", "model": "nomic", "temperature": 0.1},
            "subagents": {"provider": "ollama", "model": "nomic", "temperature": 0.5},
        },
    }

    registry.ingest_event(event)
    cached = registry.get_config("session-x")
    assert cached is not None
    assert cached["reasoning"]["model"] == "llama3.1:8b"


