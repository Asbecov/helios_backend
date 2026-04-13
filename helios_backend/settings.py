import enum
from pathlib import Path
from tempfile import gettempdir

from pydantic_settings import BaseSettings, SettingsConfigDict
from yarl import URL

TEMP_DIR = Path(gettempdir())


class LogLevel(enum.StrEnum):
    """Possible log levels."""

    NOTSET = "NOTSET"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


class Settings(BaseSettings):
    """
    Application settings.

    These parameters can be configured
    with environment variables.
    """

    host: str = "127.0.0.1"
    port: int = 8000
    # quantity of workers for uvicorn
    workers_count: int = 1
    # Enable uvicorn reloading
    reload: bool = False

    # Current environment
    environment: str = "dev"

    log_level: LogLevel = LogLevel.INFO
    # Variables for the database
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "helios_backend"
    db_pass: str
    db_base: str = "admin"
    db_echo: bool = False

    # Variables for Redis
    redis_host: str = "helios_backend-redis"
    redis_port: int = 6379
    redis_user: str | None = None
    redis_pass: str | None = None
    redis_base: int | None = None

    # Sentry's configuration.
    sentry_dsn: str | None = None
    sentry_sample_rate: float = 1.0

    # JWT settings.
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_exp_minutes: int = 60

    # Telegram auth settings.
    telegram_bot_token: str = ""
    telegram_auth_max_age_seconds: int = 300
    telegram_terms_url: str = ""
    telegram_privacy_url: str = ""
    telegram_default_payment_provider: str = "dummy"
    telegram_support_contacts: str = ""
    telegram_support_url: str = ""
    telegram_help_image_url: str = ""
    telegram_my_image_url: str = ""
    telegram_buy_image_url: str = ""
    telegram_connect_image_url: str = ""
    telegram_support_image_url: str = ""
    telegram_terms_image_url: str = ""
    telegram_privacy_image_url: str = ""

    # Marzban integration.
    marzban_base_url: str | None = None
    marzban_admin_username: str | None = None
    marzban_admin_password: str | None = None

    # Base plan.
    base_plan_name: str = "Пробный план"
    base_plan_duration_days: int = 3

    # Runtime/admin configuration.
    admin_panel_username: str | None = None
    admin_panel_password: str | None = None
    admin_site_name: str = "Helios Admin"
    admin_secret_key: str | None = None

    # Billing settings.
    yookassa_shop_id: str | None = None
    yookassa_api_key: str | None = None
    yookassa_return_url: str | None = None

    # Rate-limit network trust policy.
    rate_limit_trust_forwarded_ip: bool = False

    @property
    def db_url(self) -> str | URL:
        """
        Assemble database URL from settings.

        :return: database URL.
        """
        if self.environment.lower() == "pytest":
            return "sqlite://:memory:"
        return URL.build(
            scheme="postgres",
            host=self.db_host,
            port=self.db_port,
            user=self.db_user,
            password=self.db_pass,
            path=f"/{self.db_base}",
        )

    @property
    def redis_url(self) -> URL:
        """
        Assemble REDIS URL from settings.

        :return: redis URL.
        """
        path = ""
        if self.redis_base is not None:
            path = f"/{self.redis_base}"
        return URL.build(
            scheme="redis",
            host=self.redis_host,
            port=self.redis_port,
            user=self.redis_user,
            password=self.redis_pass,
            path=path,
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="HELIOS_BACKEND_",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()  # type: ignore
