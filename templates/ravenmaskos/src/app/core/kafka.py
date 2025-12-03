import json
import ssl
from collections.abc import AsyncGenerator, Callable
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

producer: AIOKafkaProducer | None = None
consumers: dict[str, AIOKafkaConsumer] = {}


def _get_kafka_ssl_context() -> ssl.SSLContext | None:
    """Create SSL context for Kafka TLS connection.

    Returns:
        SSLContext configured for Kafka, or None if TLS is not enabled.
    """
    if settings.KAFKA_SECURITY_PROTOCOL not in ("SSL", "SASL_SSL"):
        return None

    ssl_context = ssl.create_default_context()

    # Load CA certificate if provided
    if settings.KAFKA_SSL_CAFILE:
        ssl_context.load_verify_locations(settings.KAFKA_SSL_CAFILE)

    # Load client certificate and key if provided (for mTLS)
    if settings.KAFKA_SSL_CERTFILE and settings.KAFKA_SSL_KEYFILE:
        ssl_context.load_cert_chain(
            certfile=settings.KAFKA_SSL_CERTFILE,
            keyfile=settings.KAFKA_SSL_KEYFILE,
            password=settings.KAFKA_SSL_PASSWORD,
        )

    return ssl_context


def _get_kafka_security_config() -> dict[str, Any]:
    """Build Kafka security configuration for TLS and SASL.

    Returns:
        Dictionary of security-related configuration options.
    """
    config: dict[str, Any] = {
        "security_protocol": settings.KAFKA_SECURITY_PROTOCOL,
    }

    # Add SSL context if using TLS
    ssl_context = _get_kafka_ssl_context()
    if ssl_context:
        config["ssl_context"] = ssl_context

    # Add SASL configuration if using SASL authentication
    if settings.KAFKA_SECURITY_PROTOCOL in ("SASL_PLAINTEXT", "SASL_SSL"):
        if settings.KAFKA_SASL_MECHANISM:
            config["sasl_mechanism"] = settings.KAFKA_SASL_MECHANISM
            config["sasl_plain_username"] = settings.KAFKA_SASL_USERNAME
            config["sasl_plain_password"] = settings.KAFKA_SASL_PASSWORD

    return config


async def init_kafka() -> None:
    """Initialize Kafka producer with optional TLS and SASL support."""
    global producer

    logger.info(
        "Initializing Kafka producer",
        servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        security_protocol=settings.KAFKA_SECURITY_PROTOCOL,
    )

    # Get security configuration
    security_config = _get_kafka_security_config()

    if settings.KAFKA_SECURITY_PROTOCOL != "PLAINTEXT":
        logger.info(
            "Kafka security enabled",
            protocol=settings.KAFKA_SECURITY_PROTOCOL,
            sasl_mechanism=settings.KAFKA_SASL_MECHANISM,
            ssl_enabled=settings.KAFKA_SECURITY_PROTOCOL in ("SSL", "SASL_SSL"),
        )

    try:
        producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            enable_idempotence=True,
            max_batch_size=16384,
            linger_ms=10,
            **security_config,
        )
        await producer.start()
        logger.info("Kafka producer initialized")
    except KafkaError as e:
        logger.warning("Kafka producer initialization failed", error=str(e))
        producer = None


async def close_kafka() -> None:
    global producer

    for topic, consumer in consumers.items():
        logger.info("Closing Kafka consumer", topic=topic)
        await consumer.stop()
    consumers.clear()

    if producer:
        logger.info("Closing Kafka producer")
        await producer.stop()
        producer = None


async def check_kafka_health() -> bool:
    if not producer:
        return False

    try:
        await producer.client.check_version()
        return True
    except Exception as e:
        logger.error("Kafka health check failed", error=str(e))
        return False


async def publish(topic: str, value: dict[str, Any], key: str | None = None) -> None:
    if not producer:
        raise RuntimeError("Kafka producer not initialized")

    try:
        await producer.send_and_wait(topic, value=value, key=key)
        logger.debug("Message published", topic=topic, key=key)
    except KafkaError as e:
        logger.error("Failed to publish message", topic=topic, key=key, error=str(e))
        raise


async def publish_batch(
    topic: str, messages: list[tuple[str | None, dict[str, Any]]]
) -> None:
    if not producer:
        raise RuntimeError("Kafka producer not initialized")

    batch = producer.create_batch()
    for key, value in messages:
        serialized_key = key.encode("utf-8") if key else None
        serialized_value = json.dumps(value).encode("utf-8")
        batch.append(key=serialized_key, value=serialized_value, timestamp=None)

    try:
        await producer.send_batch(batch, topic, partition=0)
        logger.debug("Batch published", topic=topic, count=len(messages))
    except KafkaError as e:
        logger.error("Failed to publish batch", topic=topic, error=str(e))
        raise


async def create_consumer(
    topics: list[str], group_id: str | None = None
) -> AIOKafkaConsumer:
    """Create a Kafka consumer with optional TLS and SASL support."""
    # Get security configuration (same as producer)
    security_config = _get_kafka_security_config()

    consumer = AIOKafkaConsumer(
        *topics,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=group_id or settings.KAFKA_CONSUMER_GROUP,
        auto_offset_reset=settings.KAFKA_AUTO_OFFSET_RESET,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        key_deserializer=lambda k: k.decode("utf-8") if k else None,
        enable_auto_commit=True,
        auto_commit_interval_ms=5000,
        **security_config,
    )

    await consumer.start()

    for topic in topics:
        consumers[topic] = consumer

    logger.info("Kafka consumer created", topics=topics, group_id=group_id)
    return consumer


async def consume(
    topics: list[str],
    handler: Callable[[str, str | None, dict[str, Any]], Any],
    group_id: str | None = None,
) -> AsyncGenerator[None, None]:
    consumer = await create_consumer(topics, group_id)

    try:
        async for msg in consumer:
            try:
                await handler(msg.topic, msg.key, msg.value)
            except Exception as e:
                logger.error(
                    "Error processing message",
                    topic=msg.topic,
                    key=msg.key,
                    error=str(e),
                )
                yield
    finally:
        await consumer.stop()
        for topic in topics:
            consumers.pop(topic, None)
