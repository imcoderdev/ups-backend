# IoT UPS Backend

Production-minded FastAPI backend for receiving IoT device readings, queueing them in Redis, processing them with a worker, and storing validated readings in Supabase PostgreSQL.

## What to do before running

1. Install Python 3.11+.
2. Install and start Redis.
3. Create the `readings` table in Supabase by running `supabase_schema.sql` in the Supabase SQL editor.
4. Put these values in `.env.local`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-or-server-side-key
REDIS_URL=redis://localhost:6379/0
```

Use a server-side Supabase key only on the backend. Do not expose it in frontend code.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Start Redis

With Docker:

```bash
docker run --name iot-redis -p 6379:6379 redis:7
```

Or with Docker Compose:

```bash
docker compose up -d redis
```

Or, if Redis is installed locally:

```bash
redis-server
```

## Run API server

```bash
uvicorn app.main:app --reload
```

API docs will be available at `http://127.0.0.1:8000/docs`.

## Run worker

Open a second terminal:

```bash
python -m app.worker
```

## Run simulator

Open a third terminal:

```bash
python test/simulator.py
```

## Endpoints

- `POST /api/data` queues one reading.
- `GET /api/latest` returns the latest 20 readings.
- `GET /api/device/{device_id}` returns recent readings for a device.

## Payload

```json
{
  "device_id": "UPS_001",
  "sequence": 123,
  "timestamp": 1719123123,
  "data": {
    "vin": 230,
    "vout": 220,
    "iin": 3,
    "iout": 2,
    "load": 80,
    "battery": 12.5
  }
}
```
