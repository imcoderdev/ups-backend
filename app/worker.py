from __future__ import annotations

import asyncio
import json
import logging
import signal
from contextlib import suppress

from pydantic import ValidationError
from redis.asyncio import Redis

from app import crud
from app.config import Settings, get_settings
from app.database import get_supabase_client
from app.queue import create_redis_client, dequeue_reading
from app.schemas import ReadingIn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


class ReadingProcessor:
    def __init__(self, redis_client: Redis, settings: Settings) -> None:
        self.redis = redis_client
        self.settings = settings
        self.supabase = get_supabase_client()

    async def process_payload(self, payload: dict) -> None:
        try:
            reading = ReadingIn.model_validate(payload)
        except ValidationError as exc:
            logger.warning("Dropping invalid queued payload: %s", exc)
            return

        processed_key = f"iot:processed:{reading.device_id}:{reading.sequence}"
        is_new = await self.redis.set(
            processed_key,
            "1",
            nx=True,
            ex=self.settings.redis_processed_ttl_seconds,
        )
        if not is_new:
            logger.info(
                "Duplicate reading skipped before database insert",
                extra={"device_id": reading.device_id, "sequence": reading.sequence},
            )
            return

        try:
            await crud.insert_reading(self.supabase, reading)
        except crud.DuplicateReadingError:
            logger.info(
                "Duplicate reading rejected by database",
                extra={"device_id": reading.device_id, "sequence": reading.sequence},
            )
            return
        except Exception:
            # Remove the short-circuit duplicate marker so a replay can be retried.
            await self.redis.delete(processed_key)
            logger.exception(
                "Failed to store reading",
                extra={"device_id": reading.device_id, "sequence": reading.sequence},
            )
            return

        try:
            await self._warn_on_missing_sequence(reading)
        except Exception:
            logger.exception(
                "Stored reading, but failed to update sequence tracking",
                extra={"device_id": reading.device_id, "sequence": reading.sequence},
            )

        logger.info(
            "Stored reading",
            extra={"device_id": reading.device_id, "sequence": reading.sequence},
        )

    async def _warn_on_missing_sequence(self, reading: ReadingIn) -> None:
        last_key = f"iot:last_sequence:{reading.device_id}"
        previous = await self.redis.get(last_key)
        if previous is not None:
            previous_sequence = int(previous)
            if reading.sequence > previous_sequence + 1:
                logger.warning(
                    "Missing sequence detected for %s: expected %s, got %s",
                    reading.device_id,
                    previous_sequence + 1,
                    reading.sequence,
                )
            elif reading.sequence <= previous_sequence:
                logger.info(
                    "Out-of-order or repeated sequence observed for %s: last=%s current=%s",
                    reading.device_id,
                    previous_sequence,
                    reading.sequence,
                )

        # Keep the highest seen sequence so late packets do not move the marker backward.
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(last_key)
                    current = await pipe.get(last_key)
                    if current is None or reading.sequence > int(current):
                        pipe.multi()
                        pipe.set(last_key, reading.sequence)
                        await pipe.execute()
                    else:
                        await pipe.unwatch()
                    break
                except Exception:
                    await pipe.reset()
                    raise


async def run_worker() -> None:
    settings = get_settings()
    redis_client = create_redis_client(settings)
    processor = ReadingProcessor(redis_client, settings)
    stop_event = asyncio.Event()

    def _request_stop() -> None:
        logger.info("Shutdown requested")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, _request_stop)

    logger.info("Worker started; consuming queue %s", settings.redis_queue_name)
    try:
        while not stop_event.is_set():
            try:
                payload = await dequeue_reading(redis_client, settings.redis_queue_name)
            except json.JSONDecodeError:
                logger.warning("Dropping malformed JSON payload from queue")
                continue

            if payload is not None:
                await processor.process_payload(payload)
    finally:
        await redis_client.aclose()
        logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(run_worker())
