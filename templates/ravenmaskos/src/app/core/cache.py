import json
import ssl
from typing import Any

import redis.asyncio as redis
from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

pool: ConnectionPool | None = None
client: Redis | None = None


def _get_redis_ssl_context() -> ssl.SSLContext | None:
    """Create SSL context for Redis TLS connection.

    Returns:
        SSLContext configured for Redis, or None if TLS is disabled.
    """
    if not settings.REDIS_SSL:
        return None

    # Map string cert requirements to ssl constants
    cert_reqs_map = {
        "none": ssl.CERT_NONE,
        "optional": ssl.CERT_OPTIONAL,
        "required": ssl.CERT_REQUIRED,
    }

    ssl_context = ssl.create_default_context()
    ssl_context.verify_mode = cert_reqs_map.get(
        settings.REDIS_SSL_CERT_REQS.lower(), ssl.CERT_REQUIRED
    )

    # Load CA certificates if provided
    if settings.REDIS_SSL_CA_CERTS:
        ssl_context.load_verify_locations(settings.REDIS_SSL_CA_CERTS)

    # Load client certificate and key if provided (for mTLS)
    if settings.REDIS_SSL_CERTFILE and settings.REDIS_SSL_KEYFILE:
        ssl_context.load_cert_chain(
            certfile=settings.REDIS_SSL_CERTFILE,
            keyfile=settings.REDIS_SSL_KEYFILE,
        )

    return ssl_context


async def init_redis() -> None:
    """Initialize Redis connection with optional TLS support."""
    global pool, client

    # Mask password in URL for logging
    log_url = settings.REDIS_URL.split("@")[-1] if "@" in settings.REDIS_URL else settings.REDIS_URL
    logger.info(
        "Initializing Redis connection",
        url=log_url,
        ssl_enabled=settings.REDIS_SSL,
    )

    # Build connection pool options
    pool_kwargs: dict[str, Any] = {
        "max_connections": settings.REDIS_MAX_CONNECTIONS,
        "decode_responses": True,
    }

    # Add SSL context if TLS is enabled
    ssl_context = _get_redis_ssl_context()
    if ssl_context:
        pool_kwargs["ssl"] = ssl_context
        logger.info(
            "Redis TLS enabled",
            cert_reqs=settings.REDIS_SSL_CERT_REQS,
            ca_certs=bool(settings.REDIS_SSL_CA_CERTS),
            client_cert=bool(settings.REDIS_SSL_CERTFILE),
        )

    pool = ConnectionPool.from_url(settings.REDIS_URL, **pool_kwargs)
    client = Redis(connection_pool=pool)

    try:
        await client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error("Redis connection failed", error=str(e))
        raise


async def close_redis() -> None:
    global pool, client

    if client:
        logger.info("Closing Redis connection")
        await client.aclose()
        client = None

    if pool:
        await pool.disconnect()
        pool = None


async def check_redis_health() -> bool:
    if not client:
        return False

    try:
        await client.ping()
        return True
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        return False


def get_redis() -> Redis:
    if not client:
        raise RuntimeError("Redis not initialized")
    return client


async def cache_get(key: str) -> Any | None:
    r = get_redis()
    value = await r.get(key)
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    r = get_redis()
    if isinstance(value, (dict, list)):
        value = json.dumps(value)
    if ttl:
        await r.setex(key, ttl, value)
    else:
        await r.set(key, value)


async def cache_delete(key: str) -> None:
    r = get_redis()
    await r.delete(key)


async def cache_exists(key: str) -> bool:
    r = get_redis()
    return bool(await r.exists(key))


async def cache_increment(key: str, amount: int = 1) -> int:
    r = get_redis()
    return await r.incrby(key, amount)


async def cache_expire(key: str, ttl: int) -> None:
    r = get_redis()
    await r.expire(key, ttl)


async def cache_get_many(keys: list[str]) -> dict[str, Any]:
    r = get_redis()
    values = await r.mget(keys)
    result = {}
    for key, value in zip(keys, values, strict=False):
        if value is not None:
            try:
                result[key] = json.loads(value)
            except json.JSONDecodeError:
                result[key] = value
    return result


async def cache_set_many(mapping: dict[str, Any], ttl: int | None = None) -> None:
    r = get_redis()
    serialized = {}
    for key, value in mapping.items():
        if isinstance(value, (dict, list)):
            serialized[key] = json.dumps(value)
        else:
            serialized[key] = value

    async with r.pipeline() as pipe:
        await pipe.mset(serialized)
        if ttl:
            for key in serialized:
                await pipe.expire(key, ttl)
        await pipe.execute()
