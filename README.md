# Helios Backend

Production-ready FastAPI backend for Telegram Mini App VPN subscription management.

Includes an internal FastAdmin dashboard at `/admin`.

Also includes a Telegram bot (aiogram 3) for account and subscription actions.

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

Telegram bot commands:
- `/my`
- `/buy`
- `/connect`
- `/support`
- `/terms`
- `/privacy`

## API

Base path: `/api`

- POST `/auth/telegram`
- GET `/plans`
- GET `/plans/base`
- GET `/subscription`
- GET `/subscription/status`
- POST `/subscription/activate`
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

Payment creation uses `plan_id` from `/plans`.

`GET /subscription/url` requires an already active subscription balance.
Activate balance first with `POST /subscription/activate`.

Admin panel bootstrap:
- Configure all runtime variables in `.env` (see `.env.example`).
- Set `HELIOS_BACKEND_ADMIN_PANEL_USERNAME` and `HELIOS_BACKEND_ADMIN_PANEL_PASSWORD` for first admin account bootstrap.
- Set `HELIOS_BACKEND_ADMIN_SECRET_KEY` for admin session signing.

## Local Run

```bash
uv sync --locked
cp .env.example .env
aerich upgrade
uv run -m helios_backend
uv run taskiq worker helios_backend.tkq:broker
uv run taskiq scheduler helios_backend.tkq:scheduler
uv run -m helios_backend.bot
```

Bot-related env vars:
- `HELIOS_BACKEND_TELEGRAM_BOT_TOKEN`
- `HELIOS_BACKEND_TELEGRAM_TERMS_URL`
- `HELIOS_BACKEND_TELEGRAM_PRIVACY_URL`
- `HELIOS_BACKEND_TELEGRAM_DEFAULT_PAYMENT_PROVIDER`
- `HELIOS_BACKEND_TELEGRAM_SUPPORT_CONTACTS`
- `HELIOS_BACKEND_TELEGRAM_SUPPORT_URL`
- `HELIOS_BACKEND_TELEGRAM_HELP_IMAGE_URL`
- `HELIOS_BACKEND_TELEGRAM_MY_IMAGE_URL`
- `HELIOS_BACKEND_TELEGRAM_BUY_IMAGE_URL`
- `HELIOS_BACKEND_TELEGRAM_CONNECT_IMAGE_URL`
- `HELIOS_BACKEND_TELEGRAM_SUPPORT_IMAGE_URL`
- `HELIOS_BACKEND_TELEGRAM_TERMS_IMAGE_URL`
- `HELIOS_BACKEND_TELEGRAM_PRIVACY_IMAGE_URL`

## Docker

```bash
docker-compose up --build
```

Dev mode with live reload:

```bash
docker-compose -f docker-compose.yml -f deploy/docker-compose.dev.yml --project-directory . up --build
```

Admin panel URL: `http://localhost:8000/admin` (sign-in page is `http://localhost:8000/admin/login`).

## Production on one domain (subdomains)

This repository includes a production override and edge proxy config for routing:

- `api.example.com` -> Helios API (`api:8000`)
- `sub.example.com` -> Marzban subscription host (`MARZBAN_SUBSCRIPTION_UPSTREAM`)
- `app.example.com` -> website service (`site`)

Files:

- `deploy/docker-compose.prod.yml`
- `deploy/caddy/Caddyfile`
- `deploy/site/index.html` (placeholder website)

### 1. Prepare DNS

Point `api`, `sub`, and `app` subdomains to your DigitalOcean Droplet public IP.

### 2. Prepare environment

Copy `.env.example` to `.env` and set production values:

- `HELIOS_BACKEND_ENVIRONMENT=production`
- `HELIOS_BACKEND_RELOAD=False`
- `HELIOS_BACKEND_RATE_LIMIT_TRUST_FORWARDED_IP=True`
- `CADDY_EMAIL`
- `API_DOMAIN`
- `SUBSCRIPTION_DOMAIN`
- `SITE_DOMAIN`
- `MARZBAN_SUBSCRIPTION_UPSTREAM`
- `MARZBAN_DOCKER_NETWORK`

For Marzban integration:

- Keep `HELIOS_BACKEND_MARZBAN_BASE_URL` on private/internal Marzban API endpoint.
- Keep public subscription host on `SUBSCRIPTION_DOMAIN`.

### 2.1 Caddy-only certificates for Marzban (no Certbot in Marzban)

If Marzban is installed separately (for example via `marzban.sh` in `/opt/marzban`),
leave TLS termination only on Caddy and run Marzban behind it.

1. Update `/opt/marzban/.env`:

```env
DEBUG=True
UVICORN_SSL_CERTFILE=
UVICORN_SSL_KEYFILE=
XRAY_SUBSCRIPTION_URL_PREFIX=https://sub.example.com
```

2. Restart Marzban:

```bash
cd /opt/marzban
docker compose up -d
```

3. Ensure `MARZBAN_DOCKER_NETWORK` in Helios `.env` matches Marzban network name.
Default from script-based install is usually `marzban_default`.

4. Start Helios production stack (with Caddy):

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
```

In this setup, certificates for `api`, `sub`, and `app` domains are issued by Caddy.

### 3. Run production stack

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
```

This command starts API, workers, bot, DB, Redis, migrator, website container, and Caddy with automatic TLS.

### 4. Website replacement

Replace `deploy/site` content with your real frontend build output.
