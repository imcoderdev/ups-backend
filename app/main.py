from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app import crud
from app.config import get_settings
from app.database import get_supabase_client
from app.schemas import EnqueueResponse, ErrorResponse, ReadingIn, ReadingOut

settings = get_settings()

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings
    logger.info("API startup complete")
    try:
        yield
    finally:
        logger.info("API shutdown complete")


app = FastAPI(
    title="IoT UPS Backend",
    version="1.0.0",
    lifespan=lifespan,
    responses={500: {"model": ErrorResponse}},
)


async def process_and_store(payload: dict) -> None:
    try:
        reading = ReadingIn.model_validate(payload)
    except ValidationError as exc:
        logger.warning("Dropping invalid background payload: %s", exc)
        return

    try:
        supabase = get_supabase_client()
        if await crud.reading_exists(
            supabase,
            device_id=reading.device_id,
            sequence=reading.sequence,
        ):
            logger.info(
                "Duplicate reading skipped before database insert",
                extra={"device_id": reading.device_id, "sequence": reading.sequence},
            )
            return

        previous_sequence = await crud.get_latest_device_sequence(
            supabase,
            device_id=reading.device_id,
        )
        if previous_sequence is not None:
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

        await crud.insert_reading(supabase, reading)
    except crud.DuplicateReadingError:
        logger.info(
            "Duplicate reading rejected by database",
            extra={"device_id": reading.device_id, "sequence": reading.sequence},
        )
        return
    except Exception:
        logger.exception(
            "Failed to store reading",
            extra={"device_id": reading.device_id, "sequence": reading.sequence},
        )
        return

    logger.info(
        "Stored reading",
        extra={"device_id": reading.device_id, "sequence": reading.sequence},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    logger.warning("Validation failed: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(exc.errors())},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/data", response_model=EnqueueResponse, status_code=status.HTTP_202_ACCEPTED)
async def receive_data(reading: ReadingIn, background_tasks: BackgroundTasks) -> EnqueueResponse:
    background_tasks.add_task(process_and_store, reading.dict())
    logger.info(
        "Scheduled reading for background processing",
        extra={"device_id": reading.device_id, "sequence": reading.sequence},
    )
    return EnqueueResponse(status="queued", queue="background")


@app.get("/api/latest", response_model=list[ReadingOut])
async def latest_readings() -> list[dict]:
    try:
        return await crud.get_latest_readings(get_supabase_client(), limit=20)
    except Exception:
        logger.exception("Failed to fetch latest readings")
        raise HTTPException(status_code=500, detail="Failed to fetch readings")


@app.get("/api/device/{device_id}", response_model=list[ReadingOut])
async def device_readings(device_id: str) -> list[dict]:
    try:
        return await crud.get_device_readings(get_supabase_client(), device_id=device_id)
    except Exception:
        logger.exception("Failed to fetch device readings for %s", device_id)
        raise HTTPException(status_code=500, detail="Failed to fetch device readings")
