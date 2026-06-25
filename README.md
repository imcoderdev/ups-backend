# IoT UPS Backend

Production-minded FastAPI backend for receiving IoT device readings, processing them with FastAPI background tasks, and storing validated readings in Supabase PostgreSQL.

## What to do before running

1. Install Python 3.11+.
2. Create the `readings` table in Supabase by running `supabase_schema.sql` in the Supabase SQL editor.
3. Put these values in `.env.local`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-or-server-side-key
```

Use a server-side Supabase key only on the backend. Do not expose it in frontend code.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run API server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

API docs will be available at `http://127.0.0.1:8000/docs`.

## Run simulator

Open another terminal:

```bash
python test/simulator.py
```

## Endpoints

- `POST /api/data` schedules one reading for background processing.
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
    "battery": 12.5,
    "load": 462,
    "temperature": 60,
    "ups_status": "UPS ON"
  }
}
```
