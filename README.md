# Helios Backend

Production-ready FastAPI backend for Telegram Mini App VPN subscription management.

No internal admin panel is included. The schema and API are designed for external admin tools (Retool, Appsmith, ToolJet, Supabase Studio) via direct PostgreSQL CRUD or REST integrations.

## Stack

- Python 3.12
- FastAPI
- PostgreSQL + Tortoise ORM
- Redis
- Taskiq (Redis broker)
- Gunicorn + Uvicorn workers
- JWT auth

## Architecture

- API controllers: thin handlers only
- Services: business rules
- DAO: all DB access
- Models: Tortoise entities

Modules:
- auth
- users
- plans
- subscriptions
- payments
- codes
- marzban
- notifications

## API

Base path: `/api`

- POST `/auth/telegram`
- GET `/plans`
- GET `/plans/base`
- GET `/subscription`
- GET `/subscription/status`
- POST `/subscription/freeze`
- GET `/subscription/url`
- POST `/payments/create`
- POST `/payments/webhook/{provider}`
- GET `/me`
- DELETE `/me`
- GET `/me/referral-code`
- GET `/me/referral-usages`
- GET `/health`

All user-facing endpoints require JWT except `/auth/telegram` and `/health`.

## Local Run

```bash
uv sync --locked
cp .env.example .env
aerich upgrade
uv run -m helios_backend
uv run taskiq worker helios_backend.tkq:broker
uv run taskiq scheduler helios_backend.tkq:broker
```

## Docker

```bash
docker-compose up --build
```

Dev mode with live reload:

```bash
docker-compose -f docker-compose.yml -f deploy/docker-compose.dev.yml --project-directory . up --build
```
