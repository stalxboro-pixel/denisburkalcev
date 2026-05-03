from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app import db
from app.config import settings

log = logging.getLogger("bot.security")

# Hard cap on raw user input we ever accept. Defends against memory abuse.
MAX_TEXT_LEN = 4000
MAX_CALLBACK_LEN = 64


class SecurityMiddleware(BaseMiddleware):
    """Validates inbound user input and blocks banned users."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            if event.text and len(event.text) > MAX_TEXT_LEN:
                await event.answer("⚠️ Слишком длинное сообщение.")
                return None
        elif isinstance(event, CallbackQuery):
            if event.data and len(event.data) > MAX_CALLBACK_LEN:
                await event.answer("⚠️ Некорректные данные.", show_alert=False)
                return None

        user = getattr(event, "from_user", None)
        if user is not None:
            row = await db.fetchone(
                "SELECT is_banned FROM users WHERE user_id = ?;",
                (user.id,),
            )
            if row and int(row["is_banned"]) == 1:
                if isinstance(event, Message):
                    await event.answer("🚫 Доступ ограничен.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 Доступ ограничен.", show_alert=True)
                return None

            data["is_admin"] = settings.is_admin(user.id)
        else:
            data["is_admin"] = False

        return await handler(event, data)
