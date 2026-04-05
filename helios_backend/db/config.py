from helios_backend.settings import settings

MODELS_MODULES: list[str] = [
    "helios_backend.db.models.vpn.user",
    "helios_backend.db.models.vpn.balance",
    "helios_backend.db.models.vpn.subscription_plan",
    "helios_backend.db.models.vpn.payment",
    "helios_backend.db.models.vpn.code",
    "helios_backend.db.models.vpn.code_usage",
]

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
