from __future__ import annotations

from aiogram import Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app import db
from app.config import settings

router = Router(name="support")


async def show_support(message: Message) -> None:
    text = await db.get_setting("support_text", "")
    if not text:
        text = "☎️ Поддержка: @" + settings.support_contact
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Написать в поддержку", url=f"https://t.me/{settings.support_contact}")]
        ]
    )
    await message.answer(text, reply_markup=keyboard)
