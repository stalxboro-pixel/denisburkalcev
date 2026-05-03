from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

log = logging.getLogger("bot.throttle")


class ThrottlingMiddleware(BaseMiddleware):
    """Token-bucket per-user throttling — protects against flood/abuse."""

    def __init__(self, rate: float, burst: int) -> None:
        self._rate = max(0.05, float(rate))
        self._burst = max(1, int(burst))
        self._buckets: dict[int, tuple[float, float]] = {}
        self._lock = asyncio.Lock()
        self._last_warn: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = self._user_id(event)
        if user_id is None:
            return await handler(event, data)

        if not await self._allow(user_id):
            await self._notify(event, user_id)
            return None

        return await handler(event, data)

    async def _allow(self, user_id: int) -> bool:
        # Classic token bucket: refill at `1/rate` tokens per second up to `burst`.
        now = time.monotonic()
        async with self._lock:
            tokens, ts = self._buckets.get(user_id, (float(self._burst), now))
            tokens = min(self._burst, tokens + (now - ts) / self._rate)
            if tokens < 1.0:
                self._buckets[user_id] = (tokens, now)
                return False
            self._buckets[user_id] = (tokens - 1.0, now)
            return True

    async def _notify(self, event: TelegramObject, user_id: int) -> None:
        # Warn users at most once every 5 seconds to avoid notification spam.
        now = time.monotonic()
        last = self._last_warn.get(user_id, 0.0)
        if now - last < 5.0:
            return
        self._last_warn[user_id] = now
        try:
            if isinstance(event, CallbackQuery):
                await event.answer("⏳ Слишком быстро. Подождите немного.", show_alert=False)
            elif isinstance(event, Message):
                await event.answer("⏳ Слишком быстро. Подождите немного.")
        except Exception:  # noqa: BLE001
            log.debug("throttle notify failed", exc_info=True)

    @staticmethod
    def _user_id(event: TelegramObject) -> int | None:
        user = getattr(event, "from_user", None)
        return getattr(user, "id", None) if user else None
