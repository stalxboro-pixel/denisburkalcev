from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from app import db
from app.config import settings
from app.keyboards import main_menu
from app.services import referrals

log = logging.getLogger("bot.handlers.start")

router = Router(name="start")


WELCOME = (
    "🛡 <b>Wot Blitz Shop</b>\n\n"
    "🎮 Здесь ты покупаешь топовые аккаунты быстро и безопасно.\n"
    "⭐ Оплата через Telegram Stars.\n"
    "👇 Выбирай, что нужно:"
)


@router.message(CommandStart(deep_link=True))
async def start_with_payload(message: Message, command: CommandObject) -> None:
    await _ensure_user(message)
    referrer_id = referrals.parse_payload(command.args)
    if referrer_id and message.from_user and referrer_id != message.from_user.id:
        attached = await referrals.attach_referrer(message.from_user.id, referrer_id)
        if attached:
            log.info("user %s attached referrer %s", message.from_user.id, referrer_id)
    await _send_welcome(message)


@router.message(CommandStart())
async def start_plain(message: Message) -> None:
    await _ensure_user(message)
    await _send_welcome(message)


@router.message(F.text == "/menu")
async def show_menu(message: Message) -> None:
    await _ensure_user(message)
    await _send_welcome(message)


async def _ensure_user(message: Message) -> None:
    user = message.from_user
    if user is None:
        return
    await db.execute(
        """
        INSERT INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username   = excluded.username,
            first_name = excluded.first_name;
        """,
        (user.id, user.username or "", user.first_name or ""),
    )


async def _send_welcome(message: Message) -> None:
    is_admin = bool(message.from_user and settings.is_admin(message.from_user.id))
    await message.answer(WELCOME, reply_markup=main_menu(is_admin=is_admin))
