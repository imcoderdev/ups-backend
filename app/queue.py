from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as redis

from app.config import Settings
from app.schemas import ReadingIn

logger = logging.getLogger(__name__)


def create_redis_client(settings: Settings) -> redis.Redis:
    return redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        health_check_interval=30,
    )


async def enqueue_reading(client: redis.Redis, settings: Settings, reading: ReadingIn) -> None:
    payload = reading.model_dump_json()
    await client.rpush(settings.redis_queue_name, payload)
    logger.info(
        "Queued reading",
        extra={"device_id": reading.device_id, "sequence": reading.sequence},
    )


async def dequeue_reading(
    client: redis.Redis,
    queue_name: str,
    timeout_seconds: int = 5,
) -> dict[str, Any] | None:
    result = await client.blpop(queue_name, timeout=timeout_seconds)
    if result is None:
        return None

    _, payload = result
    return json.loads(payload)
