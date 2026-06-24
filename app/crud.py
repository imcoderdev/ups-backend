from __future__ import annotations

import asyncio
from typing import Any

from postgrest.exceptions import APIError
from supabase import Client

from app.schemas import ReadingIn


READINGS_TABLE = "readings"


class DuplicateReadingError(Exception):
    """Raised when Supabase rejects a duplicate device_id + sequence pair."""


async def reading_exists(client: Client, device_id: str, sequence: int) -> bool:
    def _select() -> bool:
        response = (
            client.table(READINGS_TABLE)
            .select("id")
            .eq("device_id", device_id)
            .eq("sequence", sequence)
            .limit(1)
            .execute()
        )
        return bool(response.data)

    return await asyncio.to_thread(_select)


async def get_latest_device_sequence(client: Client, device_id: str) -> int | None:
    def _select() -> int | None:
        response = (
            client.table(READINGS_TABLE)
            .select("sequence")
            .eq("device_id", device_id)
            .order("sequence", desc=True)
            .limit(1)
            .execute()
        )
        data = response.data or []
        return int(data[0]["sequence"]) if data else None

    return await asyncio.to_thread(_select)


async def insert_reading(client: Client, reading: ReadingIn) -> dict[str, Any]:
    row = reading.to_supabase_row()

    def _insert() -> dict[str, Any]:
        response = client.table(READINGS_TABLE).insert(row).execute()
        data = response.data or []
        return data[0] if data else row

    try:
        return await asyncio.to_thread(_insert)
    except APIError as exc:
        if "duplicate key" in str(exc).lower() or getattr(exc, "code", None) == "23505":
            raise DuplicateReadingError from exc
        raise


async def get_latest_readings(client: Client, limit: int = 20) -> list[dict[str, Any]]:
    def _select() -> list[dict[str, Any]]:
        response = (
            client.table(READINGS_TABLE)
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []

    return await asyncio.to_thread(_select)


async def get_device_readings(
    client: Client,
    device_id: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    def _select() -> list[dict[str, Any]]:
        response = (
            client.table(READINGS_TABLE)
            .select("*")
            .eq("device_id", device_id)
            .order("sequence", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []

    return await asyncio.to_thread(_select)
