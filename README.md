# Helios Backend

Backend-платформа для VPN-сервиса с Telegram-ботом, REST API, платежами,
админкой и интеграцией с Marzban.

## Что входит в проект

- FastAPI API (JWT auth, тарифы, подписки, платежи, пользователи)
- Telegram-бот на aiogram 3
- FastAdmin панель по адресу `/admin`
- PostgreSQL + Tortoise ORM
- Redis + Taskiq (worker/scheduler)
- Интеграция с Marzban
- Поддержка YooKassa (при наличии ключей) и dummy-провайдера для тестов

## Технологии

- Python 3.12
- FastAPI
- aiogram 3
- PostgreSQL 18
- Redis 8
- Taskiq
- Gunicorn/Uvicorn
- Aerich (миграции)

## API

Базовый префикс: `/api`

Эндпоинты:

- POST `/api/auth/telegram`
- GET `/api/plans`
- GET `/api/plans/base`
- GET `/api/subscription`
- GET `/api/subscription/status`
- POST `/api/subscription/activate`
- POST `/api/subscription/freeze`
- GET `/api/subscription/url`
- POST `/api/payments/create`
- POST `/api/payments/webhook/{provider}`
- GET `/api/users/me`
- DELETE `/api/users/me`
- GET `/api/users/me/referral-code`
- GET `/api/users/me/referral-usages`
- GET `/api/health`

Документация OpenAPI:

- `/api/docs`
- `/api/redoc`

Аутентификация:

- JWT нужен для всех пользовательских маршрутов, кроме
	`/api/auth/telegram` и `/api/health`.

## Telegram-бот

Основные команды:

- `/start`
- `/help`
- `/my`
- `/buy`
- `/connect`
- `/support`
- `/terms`
- `/privacy`

`/terms` и `/privacy` возвращают ссылки из переменных окружения:

- `HELIOS_BACKEND_TELEGRAM_TERMS_URL`
- `HELIOS_BACKEND_TELEGRAM_PRIVACY_URL`

## Локальный запуск

### 1. Установка зависимостей

```bash
uv sync --locked
```

### 2. Настройка окружения

Создайте `.env` на основе `.env.example`.

Linux/macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Минимально проверьте значения:

- `HELIOS_BACKEND_DB_PASS`
- `HELIOS_BACKEND_JWT_SECRET`
- `HELIOS_BACKEND_TELEGRAM_BOT_TOKEN` (если запускаете бота)

### 3. Миграции

```bash
uv run aerich upgrade
```

### 4. Запуск сервисов (в отдельных терминалах)

API:

```bash
uv run -m helios_backend
```

Worker:

```bash
uv run taskiq worker helios_backend.tkq:broker
```

Scheduler:

```bash
uv run taskiq scheduler helios_backend.tkq:scheduler --update-interval 1 --loop-interval 1
```

Telegram-бот:

```bash
uv run -m helios_backend.bot
```

## Docker

### Базовый запуск

```bash
docker compose up --build
```

Поднимутся: API, worker, scheduler, bot, db, redis, migrator.

### Dev-режим (live reload + проброс портов)

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.dev.yml up --build
```

### Production-оверлей (Caddy + static)

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
```

В production-режиме Caddy проксирует:

- `${API_DOMAIN}` -> `api:8000`
- `${SITE_DOMAIN}` -> `static:80`

## Админка

- URL: `/admin`
- Логин-страница: `/admin/login`

Для bootstrap-аккаунта задайте в `.env`:

- `HELIOS_BACKEND_ADMIN_PANEL_USERNAME`
- `HELIOS_BACKEND_ADMIN_PANEL_PASSWORD`
- `HELIOS_BACKEND_ADMIN_SECRET_KEY`

Пароль хранится в виде хеша; легаси plaintext-аккаунты автоматически
мигрируют при успешном входе.

## Ключевые переменные окружения

Полный список см. в `.env.example`. На практике чаще всего нужны:

- Core: `HELIOS_BACKEND_ENVIRONMENT`, `HELIOS_BACKEND_RELOAD`
- DB: `HELIOS_BACKEND_DB_HOST`, `HELIOS_BACKEND_DB_PORT`,
	`HELIOS_BACKEND_DB_USER`, `HELIOS_BACKEND_DB_PASS`,
	`HELIOS_BACKEND_DB_BASE`
- Redis: `HELIOS_BACKEND_REDIS_HOST`, `HELIOS_BACKEND_REDIS_PORT`
- JWT: `HELIOS_BACKEND_JWT_SECRET`, `HELIOS_BACKEND_JWT_ALGORITHM`
- Bot: `HELIOS_BACKEND_TELEGRAM_BOT_TOKEN`,
	`HELIOS_BACKEND_TELEGRAM_DEFAULT_PAYMENT_PROVIDER`,
	`HELIOS_BACKEND_TELEGRAM_SUPPORT_CONTACTS`,
	`HELIOS_BACKEND_TELEGRAM_SUPPORT_URL`,
	`HELIOS_BACKEND_TELEGRAM_TERMS_URL`,
	`HELIOS_BACKEND_TELEGRAM_PRIVACY_URL`
- Payments: `HELIOS_BACKEND_YOOKASSA_SHOP_ID`,
	`HELIOS_BACKEND_YOOKASSA_API_KEY`,
	`HELIOS_BACKEND_YOOKASSA_RETURN_URL`
- Marzban: `HELIOS_BACKEND_MARZBAN_BASE_URL`,
	`HELIOS_BACKEND_MARZBAN_ADMIN_USERNAME`,
	`HELIOS_BACKEND_MARZBAN_ADMIN_PASSWORD`

## Команды разработки

Проверки качества:

```bash
uv run ruff check .
uv run mypy .
uv run pytest
```

Создание миграции:

```bash
uv run aerich migrate --name <migration_name>
```

## Примечания по legal

Бот не хранит длинный текст условий внутри обработчиков `/terms` и `/privacy`:
эти команды выдают внешние ссылки из env-переменных.

Рекомендуется публиковать актуальные версии документов на отдельной
статической странице и указывать ссылки через:

- `HELIOS_BACKEND_TELEGRAM_TERMS_URL`
- `HELIOS_BACKEND_TELEGRAM_PRIVACY_URL`
