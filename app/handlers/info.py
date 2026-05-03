from __future__ import annotations

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from app import db

router = Router(name="info")


async def show_info(message: Message) -> None:
    text = await db.get_setting("info_text", "")
    photo = await db.get_setting("info_photo", "")
    if not text:
        text = "ℹ️ Информация скоро появится."
    if photo:
        try:
            await message.answer_photo(photo, caption=text)
            return
        except TelegramBadRequest:
            pass
    await message.answer(text)
