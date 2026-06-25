from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReadingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vin: float = Field(..., ge=0, description="Input voltage")
    vout: float = Field(..., ge=0, description="Output voltage")
    load: float = Field(..., ge=0, description="Load in Watts (W)")
    battery: float = Field(..., ge=0, description="Battery voltage")
    temperature: float
    ups_status: str


class ReadingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(..., min_length=1, max_length=64)
    sequence: int = Field(..., ge=0)
    timestamp: int = Field(..., gt=0, description="Unix timestamp in seconds")
    data: ReadingData

    @field_validator("device_id")
    @classmethod
    def normalize_device_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("device_id cannot be blank")
        return normalized

    @field_validator("timestamp")
    @classmethod
    def reject_unreasonable_timestamp(cls, value: int) -> int:
        # 2000-01-01 through 2100-01-01 keeps obvious device clock failures out.
        if value < 946684800 or value > 4102444800:
            raise ValueError("timestamp must be a Unix timestamp between 2000 and 2100")
        return value

    def to_supabase_row(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "sequence": self.sequence,
            "device_timestamp": datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat(),
            "vin": self.data.vin,
            "vout": self.data.vout,
            "load": self.data.load,
            "battery": self.data.battery,
            "temperature": self.data.temperature,
            "ups_status": self.data.ups_status,
            "raw_payload": self.model_dump(mode="json"),
        }


class EnqueueResponse(BaseModel):
    status: str
    queue: str


class ReadingOut(BaseModel):
    id: int | None = None
    device_id: str
    sequence: int
    device_timestamp: str
    vin: float
    vout: float
    load: float
    battery: float
    temperature: float
    ups_status: str
    created_at: str | None = None


class ErrorResponse(BaseModel):
    detail: str
