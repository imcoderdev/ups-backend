from __future__ import annotations

import asyncio
import logging
import random
import time

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict


class SimulatorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    simulator_api_url: str = "http://127.0.0.1:8000"
    simulator_device_count: int = 3
    simulator_interval_seconds: float = 3.0


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def make_payload(device_id: str, sequence: int) -> dict:
    load = round(random.uniform(20, 95), 2)
    vin = round(random.uniform(215, 245), 2)
    if vin >= 200:
        ups_status = "online"
    elif vin > 0:
        ups_status = "on_battery"
    else:
        ups_status = "fault"

    return {
        "device_id": device_id,
        "sequence": sequence,
        "timestamp": int(time.time()),
        "data": {
            "vin": vin,
            "vout": round(random.uniform(210, 235), 2),
            "iin": round(random.uniform(1, 8), 2),
            "iout": round(random.uniform(1, 7), 2),
            "load": load,
            "battery": round(random.uniform(11.8, 13.8), 2),
            "temperature": round(random.uniform(25.0, 55.0), 2),
            "ups_status": ups_status,
        },
    }


async def simulate_device(client: httpx.AsyncClient, api_url: str, device_id: str, interval: float) -> None:
    sequence = 0
    while True:
        sequence += 1

        # Occasionally skip a number so the worker can demonstrate missing sequence warnings.
        if random.random() < 0.05:
            sequence += 1

        payload = make_payload(device_id, sequence)
        try:
            response = await client.post(f"{api_url}/api/data", json=payload)
            response.raise_for_status()
            logger.info("Sent %s seq=%s", device_id, sequence)

            # Occasionally resend the same payload so duplicate detection is exercised.
            if random.random() < 0.03:
                duplicate = await client.post(f"{api_url}/api/data", json=payload)
                logger.info("Sent duplicate %s seq=%s status=%s", device_id, sequence, duplicate.status_code)
        except httpx.HTTPError as exc:
            logger.error("Failed to send %s seq=%s: %s", device_id, sequence, exc)

        jitter = random.uniform(0, interval * 0.4)
        await asyncio.sleep(interval + jitter)


async def main() -> None:
    settings = SimulatorSettings()
    api_url = settings.simulator_api_url.rstrip("/")
    devices = [f"UPS_{index:03d}" for index in range(1, settings.simulator_device_count + 1)]

    async with httpx.AsyncClient(timeout=10) as client:
        await asyncio.gather(
            *(simulate_device(client, api_url, device_id, settings.simulator_interval_seconds) for device_id in devices)
        )


if __name__ == "__main__":
    asyncio.run(main())
