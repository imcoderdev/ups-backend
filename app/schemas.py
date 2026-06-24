from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReadingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vin: float = Field(..., ge=0, description="Input voltage")
    vout: float = Field(..., ge=0, description="Output voltage")
    iin: float = Field(..., ge=0, description="Input current")
    iout: float = Field(..., ge=0, description="Output current")
    load: float = Field(..., ge=0, le=100, description="Load percentage")
    battery: float = Field(..., ge=0, description="Battery voltage")


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
            "iin": self.data.iin,
            "iout": self.data.iout,
            "load": self.data.load,
            "battery": self.data.battery,
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
    iin: float
    iout: float
    load: float
    battery: float
    created_at: str | None = None


class ErrorResponse(BaseModel):
    detail: str
