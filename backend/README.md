# Boond backend

Python package `boond`, deployed as two AWS Lambda functions (region `ap-south-1`):

- **`boond.api.handler`**, behind an API Gateway HTTP API, serves the dashboard.
- **`boond.daily.handler`**, run by EventBridge Scheduler at 06:00 Asia/Kolkata, refreshes every active field
  and sends the morning Web Push notification.

Both import the engine (`../engine`) unchanged. The season is recomputed from the sowing date on every
run with all check-ins, so no engine state is stored and a check-in for any past day is always applied.

## Modules

| Module | Does |
|---|---|
| `api.py` | routes, validation, JSON responses |
| `daily.py` | the 06:00 run: weather once per 0.01° cell, one field's failure never stops the others |
| `refresh.py` | one field end to end: engine → text → audio → DynamoDB → push (once per day) |
| `advise.py` | builds the engine field and calls `advance_field` |
| `weather.py` | Open-Meteo forecast + ERA5 archive, merged; cached per cell and day in S3; stale fallback |
| `wording.py` | engine template text; optional Bedrock rewrite accepted only if every number comes from the engine, no number words, Hindi in Devanagari |
| `audio.py` | Polly `Kajal` (neural, hi-IN / en-IN), cached in S3 by text, presigned links |
| `push.py`, `vapid.py` | Web Push sending; VAPID key generation |
| `store.py` | DynamoDB single table (the only module that knows the key layout) |
| `aws.py` | builds the real dependencies from environment variables |

## API

| Method and path | Body | Response |
|---|---|---|
| `POST /fields` | `{language, latitude, longitude, crop:"wheat", sowing_date, soil, area_acres, pump_type, lift_m, consent:true}` | `201 {field_token}` |
| `GET /fields/{token}` | | `200` profile + `latest_advice` (engine advice, `advice_text {hi,en}`, `audio_url`, `generated_at`, `weather_stale`) |
| `POST /fields/{token}/events` | `{type:"WATERED"\|"RAIN", level, date}` | `201`, advice recomputed |
| `POST /fields/{token}/push-subscription` | `PushSubscription.toJSON()` | `201` |
| `DELETE /fields/{token}` | | `204`, every item of the field removed |
| `GET /config` | | `200 {vapid_public_key}` |

## Tests

```bash
python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements-dev.txt
cd backend && .venv/bin/pytest -q
```
AWS services are mocked with moto; Polly, Bedrock and push use small test doubles. Weather tests use
recorded Open-Meteo responses (`tests/fixtures/`); engine tests use the 2021-22 Ludhiana replay weather.

## Data and credits

Weather: [Open-Meteo](https://open-meteo.com/) (forecast API and ERA5 archive), CC BY 4.0.

## Deploy

See [`../infra/DEPLOY.md`](../infra/DEPLOY.md). Nothing is deployed by the tests.
