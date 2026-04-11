from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "users" (
    "id" UUID NOT NULL PRIMARY KEY,
    "telegram_id" BIGINT NOT NULL UNIQUE,
    "username" VARCHAR(255),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "marzban_username" VARCHAR(120) UNIQUE
);
COMMENT ON TABLE "users" IS 'Telegram user profile for subscription management.';
CREATE TABLE IF NOT EXISTS "balances" (
    "id" UUID NOT NULL PRIMARY KEY,
    "remaining_frozen_days" INT NOT NULL DEFAULT 0,
    "is_frozen" BOOL NOT NULL DEFAULT True,
    "frozen_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expires_at" TIMESTAMPTZ,
    "activated_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "balances" IS 'User remaining days balance for VPN access.';
CREATE TABLE IF NOT EXISTS "subscription_plans" (
    "id" UUID NOT NULL PRIMARY KEY,
    "name" VARCHAR(120) NOT NULL UNIQUE,
    "duration_days" INT NOT NULL,
    "price" DECIMAL(12,2) NOT NULL,
    "is_base" BOOL NOT NULL DEFAULT False,
    "tags" JSONB NOT NULL
);
COMMENT ON TABLE "subscription_plans" IS 'Subscription plan entity.';
CREATE TABLE IF NOT EXISTS "codes" (
    "id" UUID NOT NULL PRIMARY KEY,
    "code" VARCHAR(64) NOT NULL UNIQUE,
    "type" VARCHAR(8) NOT NULL,
    "discount_percent" INT,
    "reward_days_percent" INT,
    "expires_at" TIMESTAMPTZ,
    "is_active" BOOL NOT NULL DEFAULT True,
    "owner_id" UUID REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "codes"."type" IS 'PROMO: PROMO\nREFERRAL: REFERRAL';
COMMENT ON TABLE "codes" IS 'Unified promo and referral code model.';
CREATE TABLE IF NOT EXISTS "payments" (
    "id" UUID NOT NULL PRIMARY KEY,
    "amount" DECIMAL(12,2) NOT NULL,
    "status" VARCHAR(7) NOT NULL DEFAULT 'pending',
    "provider" VARCHAR(64) NOT NULL,
    "external_id" VARCHAR(255) NOT NULL UNIQUE,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "code_id" UUID REFERENCES "codes" ("id") ON DELETE CASCADE,
    "plan_id" UUID NOT NULL REFERENCES "subscription_plans" ("id") ON DELETE CASCADE,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "payments"."status" IS 'PENDING: pending\nPAID: paid\nFAILED: failed';
COMMENT ON TABLE "payments" IS 'Payment entity for subscription purchase attempts.';
CREATE TABLE IF NOT EXISTS "code_usages" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "code_id" UUID NOT NULL REFERENCES "codes" ("id") ON DELETE CASCADE,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_code_usages_user_id_f73c04" UNIQUE ("user_id", "code_id")
);
COMMENT ON TABLE "code_usages" IS 'Tracks per-user code usage to enforce one-time usage per code per user.';
CREATE TABLE IF NOT EXISTS "base_plan_grants" (
    "id" UUID NOT NULL PRIMARY KEY,
    "telegram_id" BIGINT NOT NULL UNIQUE,
    "granted_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" UUID REFERENCES "users" ("id") ON DELETE SET NULL
);
COMMENT ON TABLE "base_plan_grants" IS 'Tracks one-time base-plan grants by Telegram identity.';
CREATE TABLE IF NOT EXISTS "runtime_settings" (
    "id" UUID NOT NULL PRIMARY KEY,
    "key" VARCHAR(120) NOT NULL UNIQUE,
    "value" JSONB NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "runtime_settings" IS 'Mutable operational settings persisted in database.';
CREATE TABLE IF NOT EXISTS "admin_accounts" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "username" VARCHAR(50) NOT NULL UNIQUE,
    "password" VARCHAR(200) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "admin_accounts" IS 'Credentials used by FastAPI-Admin panel login provider.';
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "eJztXWtP4zgU/StWP81IgKA8d7RaqYUy010oiMfsah6K3MQtFomTSRygM+K/r+08mocT0p"
    "A26ZAvQ2v73sbHr3Ou7cyvjmFqSHe2bh1kdz6AXx0CDcQ+xNI3QAda1jyVJ1A41kVBl5UQ"
    "KXDsUBuqlCVOoO4glqQhR7WxRbFJeNEbpKOpDQ3AbYBlmxOsIzAxbeC447AkMCCBU2QgQr"
    "e4X81UmWNMpuVduAT/cJFCzSmid6KiX7+zZEw09ISc4Kt1r0ww0rUYDljjDkS6QmeWSLu9"
    "HZ6cipL88caKauquQealrRm9M0lY3HWxtsVteN4UEWRDirQITMTVdR/OIMl7YpZAbReFj6"
    "rNEzQ0ga7Owe78OXGJKqotfon/s/dXJwU//5UEnH6SahLedJhQjsWvZ69W8zqL1A7/qeNP"
    "vat3uwfvRS1Nh05tkSkQ6TwLQ0ihZypwnQNJ/ZZTZIj28XRIqBzThGECXPbQy4E1gKschu"
    "yB2J/NP7rd3d3D7vbuwdH+3uHh/tH2ESsrHimddZgDfH/4cTi64TU12RjzRh5P4JjPMeaD"
    "QnxOAXx8B205vFGbBLasQgWw9ZELoQ2KzLGdTwcVgWvAJ0VHZErv2Nfu/n4OcJ97V6LTsl"
    "Lv4/CN/KyulxdHUrURr7ECaRrLE5ZDsYHkeMYtE4hqvulW8KFM310BwKwO2gXRZ37z5uB7"
    "MzwfXN/0zi95TQzH+aELiHo3A57TFamzROq7g0RThE7Av8ObT4B/BV8uRoPkNBOWu/nS4c"
    "8EXWoqxHxUoBYZw0FqAEysYQ1o/xxDopQZKjLbSobM0mej2IDZ6W4XGDCsVOaAEXnPz3zR"
    "nNxHZnueMIbq/SO0NSWWM2+AMdQhUZEjWQR8y9N/rpAORR3TAPu8pO95aebweQ46TpA6H0"
    "aRGYZV5JUgHLM/jZygCwFgwRknaK/E4NLzsuYdgU0pjK9W0B1uuZ81BmMMHaRYbGwrjPK9"
    "unP0mbdL5uwj97VeI4VPpWbXzJpc01lG10imCBGk+b/NfykxeUr0XmRezZZ80Sn8ZdXHJS"
    "SwkcFqx5AAGpw5wPcghNvnyxGAKnPnpOXegratzivR9yrWeWFrKRPb/ImIwhstjW2m3Mu0"
    "r0b4FRnS269gWp7u6+7sHe4d7R7shXIvTMlTeWlFhx0fBslEaJo6giSjg0btEsiNmeGyoA"
    "t7bdU9sn9xcRaTGP1hQg6Pbs/7A8ZbRadlhTDNUMl+v1pc2sUMW2XXMGWHnizMvJVo17hl"
    "BQ1bG49oejsG1c5tSMYm8EPJ6EvStm3MmhuzDaT9ptMtD4JJY/nZrDliUiV1rnVAvsCUUy"
    "GyOIBp9E5NG+Ep+QfNBIZD9hyBIJNr3GCHrmk7IFnKliXb8DFUYNFOwSrHqoQ83nbcuz7u"
    "nQw6z9lBxWVq5OvIdiIPIXQkYjlVZiNPNUc3KEWIo6B+jv4K4HYAEYrpLK2Wc0u22ng1I3"
    "4jRxsvuuHwqk2G1e95LmeXIbroaK4tQn6LBhVSdqsLJlSyj1xZPMGysSrpgidIxQbU5eCF"
    "NkkO5hlt+cbNBDAHnZPB8fC8d8b62UY3ETQIuudeqgdiR+Ex6sXDMYHVCoMx8gWlYdEYCq"
    "eSkfz39cUo4ziIXz6B4y1htfuqYZVuAB079PuyQI0sNWMX6xQTZ4v/7JJWGw5EDOlgfnx3"
    "3vsvOXUen130k8sSd9Avu1n7lvfolskuxc6thFEGO7rZLDLcNi6w8UIwexyNn5IzTACJBm"
    "w0QbYNdcC9AOFdsudS2KyllPVTStXvMUUpZVB+HSnlwV4BRnmwl0koeVZi8eHVl6I3IK6R"
    "UuDxhci3rQbJ0hNd5/Lq4vziAxB/vpGrweng6qp39gEEn5IDvAjSRwWAPsrE+ShF27Gjmi"
    "6hioVs1V8JijJ3iWkp8l7DMcWKubuNxMLDJUwJIDOs3yiW7WZR86PQhfYXmLISez4lFNnc"
    "rt0gj2FqPpKFY/tRm1cQtUYNhvKxfYHG6oL7zTm3tpGI7ke7xaLh/fpkaHPwTGy5vd1Dos"
    "tU40HHkAjySJ/J1uTR7vmyLPdd+nsz6btrlmurd9BBAFKKDItKjkWWc9HK9dWsCxs5ch0a"
    "XMwsGICfG7UReC6wIXUls2Ax1T63Xp1u71iIaBwiyWQwGJ0MRx8/AL/IN3LZG56wrxBr38"
    "hpb3g2OOEusY60MkI+TxUFEB9mCvnDJPaWbT5gTUZtsiNOUZuaYyWNiTuhJ8qvkOlSkp0N"
    "ZcJsHWN47W3N9pBZ8UNm4m7UYuQjYvJGdGhsguZXpxYDLGLyVk7ltecYf59zjM2Jdbx4kj"
    "E5UCtATXYEcX0RjExFLyMo3/lcGMG1u0SdBC2y4DXpAO080JRxziGMQuUfdohcjS7whiGW"
    "fe8wMWVvihcEiQMLwgGgJkBkYtoqAiZBm5zO+TlWUJB/4GaS1w5V51cShfkazqGiT39voz"
    "JLWfNzDlG0+qHVD5Xqh7Uidy0dbulwzXR4tWSuwag1lM3F36QifXFI4lUrea8PSb/jpTC1"
    "CzkW97IpLjl5XsB4BsK3Q2It645UeTft9ln9RK19ieTyXyIpxkEpMhy3bMlww8hwbdRunY"
    "LpjWF2zQ04ZRG768ENGN2endXFUa5cwueVa0SpV80USUmUyGUptldWcbzCBVnKuSscANNC"
    "3o1TqIPAA48DOdhhLQ4wAXyN4+QjTVFK+mj5Sf385B7NFtnP94uv4z7+Uq53P0DdlcjA7M"
    "ugoUFdt0GXtkxVdu+zPSfxFqidpZVs2Lhl27C1Nmx40rngRe1lsqmeZmDSU8XlOxmXiuXn"
    "MinISyrQK1qQRx3bSMReWC7fOtN4WOYUOrR3OdwUvwwsSJAOdHPKP/tHDNNc6hV+KuZTma"
    "GJohEJv7s0ICDxylt42fSplv+/omYitV+ER+1n06j9FIuyoOM8mvZCJ0ujNut5SLe7XQRI"
    "Vir7YOl2CsqWMP0W66pHmJqysCIbq3fSJdXLyV9M52VeWkSz27ld2la+tD3wuI0pOfKXPS"
    "dHTNZ0Sl7GWX8+NBYA0S++ngDuFFrTdnLWtB3JmmYSKn11RHaYJWLSBlqyAi21Li/P/wMx"
    "xdc1"
)
