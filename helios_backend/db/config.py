from helios_backend.settings import settings

MODELS_MODULES: list[str] = [
    "helios_backend.db.models.vpn.user",
    "helios_backend.db.models.vpn.balance",
    "helios_backend.db.models.vpn.subscription_plan",
    "helios_backend.db.models.vpn.payment",
    "helios_backend.db.models.vpn.code",
    "helios_backend.db.models.vpn.code_usage",
    "helios_backend.db.models.vpn.base_plan_grant",
    "helios_backend.db.models.vpn.runtime_setting",
]

if settings.environment.lower() != "pytest":
    MODELS_MODULES.append("helios_backend.db.models.vpn.admin_account")

TORTOISE_CONFIG = {
    "connections": {
        "default": str(settings.db_url),
    },
    "apps": {
        "models": {
            "models": [*MODELS_MODULES, "aerich.models"],
            "default_connection": "default",
        },
    },
}
