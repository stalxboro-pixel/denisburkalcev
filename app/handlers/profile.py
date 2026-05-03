from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

from app import db
from app.services import referrals

router = Router(name="profile")


async def show_profile(message: Message) -> None:
    if message.from_user is None:
        return
    user = message.from_user
    row = await db.fetchone(
        "SELECT user_id, username, balance, created_at FROM users WHERE user_id = ?;",
        (user.id,),
    )
    if row is None:
        await message.answer("Сначала нажмите /start.")
        return

    nickname = (
        f"@{row['username']}" if row["username"] else (user.first_name or "—")
    )
    balance = float(row["balance"] or 0.0)
    referrals_count = (await db.fetchone(
        "SELECT COUNT(*) AS n FROM users WHERE referrer_id = ?;",
        (user.id,),
    ))["n"]

    text = (
        "👤 <b>Профиль</b>\n\n"
        f"🆔 ID: <code>{row['user_id']}</code>\n"
        f"🏷 Никнейм: {nickname}\n"
        f"💰 Баланс: <b>{balance:.2f} ₽</b>\n"
        f"📅 С нами с: {row['created_at']}\n\n"
        "💎 <b>Реферальная система</b>\n"
        "Приглашайте друзей и зарабатывайте!\n"
        "Вы будете получать <b>5%</b> от каждой покупки вашего реферала.\n\n"
        f"👥 Приглашено: <b>{referrals_count}</b>\n"
        f"🔗 Ваша ссылка:\n<code>{referrals.referral_link(user.id)}</code>"
    )
    await message.answer(text)
