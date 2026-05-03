from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from app import keyboards as kb
from app.config import settings

router = Router(name="menu")


@router.message(F.text == kb.BTN_BUY)
async def buy_entry(message: Message) -> None:
    # Re-export to products handler to avoid circular import on startup.
    from app.handlers.products import show_catalog

    await show_catalog(message)


@router.message(F.text == kb.BTN_PROFILE)
async def profile_entry(message: Message) -> None:
    from app.handlers.profile import show_profile

    await show_profile(message)


@router.message(F.text == kb.BTN_INFO)
async def info_entry(message: Message) -> None:
    from app.handlers.info import show_info

    await show_info(message)


@router.message(F.text == kb.BTN_SUPPORT)
async def support_entry(message: Message) -> None:
    from app.handlers.support import show_support

    await show_support(message)


@router.message(F.text == kb.BTN_ADMIN)
async def admin_entry(message: Message) -> None:
    if not message.from_user or not settings.is_admin(message.from_user.id):
        await message.answer("🚫 Команда недоступна.")
        return
    from app.handlers.admin import open_admin

    await open_admin(message)
