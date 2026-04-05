from helios_backend.db.models.vpn.runtime_setting import RuntimeSetting


class RuntimeSettingDao:
    """DB access for runtime operational settings."""

    async def get_by_key(self, key: str) -> RuntimeSetting | None:
        """Return runtime setting by key if present."""
        return await RuntimeSetting.filter(key=key).first()

    async def get_all(self) -> list[RuntimeSetting]:
        """Return all persisted runtime settings."""
        return await RuntimeSetting.all().order_by("key")

    async def upsert(self, key: str, value: bool | int | str) -> RuntimeSetting:
        """Create or update a runtime setting value."""
        setting, created = await RuntimeSetting.get_or_create(
            key=key,
            defaults={"value": value},
        )
        if created:
            return setting

        setting.value = value
        await setting.save(update_fields=["value", "updated_at"])
        return setting
