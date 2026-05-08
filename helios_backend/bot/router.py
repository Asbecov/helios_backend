"""Compose bot routers."""

from aiogram import Router

from helios_backend.bot.routes import (
	account,
	buy,
	connect,
	general,
	legal,
	proxies,
	support,
)

router = Router(name="subscription-bot")
router.include_router(general.router)
router.include_router(account.router)
router.include_router(buy.router)
router.include_router(connect.router)
router.include_router(proxies.router)
router.include_router(support.router)
router.include_router(legal.router)
