from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app import db
from app.config import settings
from app.handlers import register_routers
from app.middlewares.security import SecurityMiddleware
from app.middlewares.throttling import ThrottlingMiddleware
from app.utils.logging import setup_logging


def _build_session() -> AiohttpSession | None:
    if not settings.proxy_url:
        return None
    return AiohttpSession(proxy=settings.proxy_url)


def _build_bot() -> Bot:
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is empty. Set it in .env before running.")
    session = _build_session()
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session,
    )


def _build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    throttle = ThrottlingMiddleware(
        rate=settings.rate_limit_seconds,
        burst=settings.rate_limit_burst,
    )
    security = SecurityMiddleware()
    dp.message.middleware(security)
    dp.callback_query.middleware(security)
    dp.message.middleware(throttle)
    dp.callback_query.middleware(throttle)
    register_routers(dp)
    dp.errors.register(_on_error)
    return dp


async def _on_error(event: Any) -> bool:
    log = logging.getLogger("bot.errors")
    exc = getattr(event, "exception", None)
    update = getattr(event, "update", None)
    log.exception("unhandled error: %s", exc, exc_info=exc)
    # Best-effort user notification without leaking internal details.
    try:
        if update and update.message:
            await update.message.answer("⚠️ Внутренняя ошибка. Попробуйте позже.")
        elif update and update.callback_query:
            await update.callback_query.answer("⚠️ Ошибка. Попробуйте позже.", show_alert=False)
    except Exception:  # noqa: BLE001
        pass
    return True


async def run() -> None:
    log = setup_logging()
    log.info("starting bot...")
    await db.init_db()
    bot = _build_bot()
    dp = _build_dispatcher()
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


def main() -> None:
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
