import enum
import logging

from helios_backend.db.dao.vpn.runtime_setting_dao import RuntimeSettingDao
from helios_backend.settings import settings

logger = logging.getLogger(__name__)


class RuntimeSettingKey(enum.StrEnum):
    """Supported mutable runtime setting keys."""

    BASE_PLAN_NAME = "base_plan_name"
    BASE_PLAN_DURATION_DAYS = "base_plan_duration_days"
    REGISTRATIONS_ENABLED = "registrations_enabled"
    PAYMENTS_ENABLED = "payments_enabled"


RuntimeSettingValue = bool | int | str


class RuntimeSettingService:
    """Runtime settings resolution and mutation with validation."""

    def __init__(
        self,
        runtime_setting_dao: RuntimeSettingDao | None = None,
    ) -> None:
        """Initialize runtime settings service."""
        self._runtime_setting_dao = runtime_setting_dao or RuntimeSettingDao()

    @staticmethod
    def _defaults() -> dict[str, RuntimeSettingValue]:
        """Return immutable default values sourced from settings."""
        return {
            RuntimeSettingKey.BASE_PLAN_NAME.value: settings.base_plan_name,
            RuntimeSettingKey.BASE_PLAN_DURATION_DAYS.value: (
                settings.base_plan_duration_days
            ),
            RuntimeSettingKey.REGISTRATIONS_ENABLED.value: True,
            RuntimeSettingKey.PAYMENTS_ENABLED.value: True,
        }

    def allowed_keys(self) -> list[str]:
        """Return supported runtime setting keys."""
        return sorted(self._defaults().keys())

    async def get_all_effective(self) -> dict[str, RuntimeSettingValue]:
        """Return merged default+runtime setting values."""
        merged = self._defaults()
        stored = await self._runtime_setting_dao.get_all()
        for entry in stored:
            if entry.key not in merged:
                continue
            try:
                merged[entry.key] = self._validate(entry.key, entry.value)
            except ValueError as exc:
                logger.warning(
                    "Invalid runtime setting %s=%r, using default: %s",
                    entry.key,
                    entry.value,
                    exc,
                )
        return merged

    async def get_effective(self, key: str) -> RuntimeSettingValue:
        """Return one effective setting value with default fallback."""
        defaults = self._defaults()
        if key not in defaults:
            msg = "unsupported runtime setting key"
            raise ValueError(msg)

        entry = await self._runtime_setting_dao.get_by_key(key)
        if entry is None:
            return defaults[key]

        try:
            return self._validate(key, entry.value)
        except ValueError as exc:
            logger.warning(
                "Invalid runtime setting %s=%r, using default: %s",
                key,
                entry.value,
                exc,
            )
            return defaults[key]

    async def registrations_enabled(self) -> bool:
        """Return whether new registrations are currently allowed."""
        value = await self.get_effective(RuntimeSettingKey.REGISTRATIONS_ENABLED.value)
        return bool(value)

    async def payments_enabled(self) -> bool:
        """Return whether new payment creation is currently allowed."""
        value = await self.get_effective(RuntimeSettingKey.PAYMENTS_ENABLED.value)
        return bool(value)

    async def base_plan_name(self) -> str:
        """Return effective base plan name."""
        value = await self.get_effective(RuntimeSettingKey.BASE_PLAN_NAME.value)
        if not isinstance(value, str):
            msg = "base_plan_name must be a string"
            raise ValueError(msg)
        return value

    async def base_plan_duration_days(self) -> int:
        """Return effective base plan duration in days."""
        value = await self.get_effective(
            RuntimeSettingKey.BASE_PLAN_DURATION_DAYS.value,
        )
        if isinstance(value, bool) or not isinstance(value, int):
            msg = "base_plan_duration_days must be an integer"
            raise ValueError(msg)
        return value

    def _validate(self, key: str, value: object) -> RuntimeSettingValue:
        """Validate and normalize one setting value by key."""
        if key in {
            RuntimeSettingKey.REGISTRATIONS_ENABLED.value,
            RuntimeSettingKey.PAYMENTS_ENABLED.value,
        }:
            if not isinstance(value, bool):
                msg = f"{key} must be a boolean"
                raise ValueError(msg)
            return value

        if key == RuntimeSettingKey.BASE_PLAN_DURATION_DAYS.value:
            if isinstance(value, bool) or not isinstance(value, int):
                msg = "base_plan_duration_days must be an integer"
                raise ValueError(msg)
            if value < 1 or value > 3650:
                msg = "base_plan_duration_days must be between 1 and 3650"
                raise ValueError(msg)
            return value

        if key == RuntimeSettingKey.BASE_PLAN_NAME.value:
            if not isinstance(value, str):
                msg = "base_plan_name must be a string"
                raise ValueError(msg)
            normalized = value.strip()
            if not normalized:
                msg = "base_plan_name must not be empty"
                raise ValueError(msg)
            if len(normalized) > 120:
                msg = "base_plan_name is too long"
                raise ValueError(msg)
            return normalized

        msg = "unsupported runtime setting key"
        raise ValueError(msg)
