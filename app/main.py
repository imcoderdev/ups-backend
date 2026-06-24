from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app import crud
from app.config import Settings, get_settings
from app.database import get_supabase_client
from app.queue import create_redis_client, enqueue_reading
from app.schemas import EnqueueResponse, ErrorResponse, ReadingIn, ReadingOut

settings = get_settings()

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = create_redis_client(settings)
    app.state.redis = redis_client
    app.state.settings = settings
    logger.info("API startup complete")
    try:
        yield
    finally:
        await redis_client.aclose()
        logger.info("API shutdown complete")


app = FastAPI(
    title="IoT UPS Backend",
    version="1.0.0",
    lifespan=lifespan,
    responses={429: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)


@app.middleware("http")
async def redis_rate_limit(request: Request, call_next):
    if request.url.path in {"/docs", "/openapi.json", "/redoc"}:
        return await call_next(request)

    redis_client: Redis = request.app.state.redis
    active_settings: Settings = request.app.state.settings
    client_host = request.client.host if request.client else "unknown"
    key = f"iot:rate:{client_host}:{request.url.path}"

    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, active_settings.rate_limit_window_seconds)
        if count > active_settings.rate_limit_requests:
            logger.warning("Rate limit exceeded for %s", client_host)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded"},
            )
    except Exception:
        logger.exception("Rate limiter failed")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Rate limiter unavailable"},
        )

    return await call_next(request)


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
async def receive_data(reading: ReadingIn, request: Request) -> EnqueueResponse:
    try:
        await enqueue_reading(request.app.state.redis, request.app.state.settings, reading)
    except Exception:
        logger.exception(
            "Failed to enqueue reading",
            extra={"device_id": reading.device_id, "sequence": reading.sequence},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Queue unavailable",
        )

    return EnqueueResponse(status="queued", queue=request.app.state.settings.redis_queue_name)


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
