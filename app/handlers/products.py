from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from app import db, keyboards as kb
from app.config import settings
from app.keyboards import BuyCB, ProductCB
from app.services import products as products_svc
from app.services.payments.telegram_stars import TelegramStarsProvider

log = logging.getLogger("bot.handlers.products")

router = Router(name="products")

CATALOG_HEADER = (
    "➖➖➖ <b>Wot Blitz · WARGAMING</b> ➖➖➖\n\n"
    "🛒 Выберите товар из списка ниже."
)


async def show_catalog(message: Message) -> None:
    items = await products_svc.list_active()
    if not items:
        await message.answer("📭 Товары временно отсутствуют. Загляните позже.")
        return
    keyboard = kb.products_keyboard(
        [(p.id, p.title, p.price_rub, p.stock) for p in items]
    )
    await message.answer(CATALOG_HEADER, reply_markup=keyboard)


@router.callback_query(ProductCB.filter(F.action == "view"))
async def product_view(call: CallbackQuery, callback_data: ProductCB) -> None:
    product = await products_svc.get(callback_data.product_id)
    if product is None or not product.enabled:
        await call.answer("Товар недоступен.", show_alert=True)
        return

    text = _format_product(product)
    can_buy = product.stock > 0
    keyboard = kb.product_card_keyboard(product.id, settings.support_contact, can_buy=can_buy)

    if call.message:
        try:
            if product.photo:
                await call.message.answer_photo(product.photo, caption=text, reply_markup=keyboard)
            else:
                await call.message.edit_text(text, reply_markup=keyboard)
        except TelegramBadRequest:
            await call.message.answer(text, reply_markup=keyboard)
    await call.answer()


@router.callback_query(ProductCB.filter(F.action == "back"))
async def product_back(call: CallbackQuery) -> None:
    items = await products_svc.list_active()
    keyboard = kb.products_keyboard([(p.id, p.title, p.price_rub, p.stock) for p in items])
    if call.message:
        try:
            await call.message.edit_text(CATALOG_HEADER, reply_markup=keyboard)
        except TelegramBadRequest:
            await call.message.answer(CATALOG_HEADER, reply_markup=keyboard)
    await call.answer()


@router.callback_query(BuyCB.filter(F.provider == "stars"))
async def buy_stars(call: CallbackQuery, callback_data: BuyCB, bot: Bot) -> None:
    if call.from_user is None or call.message is None:
        await call.answer("Ошибка.", show_alert=True)
        return

    product = await products_svc.get(callback_data.product_id)
    if product is None or not product.enabled:
        await call.answer("Товар недоступен.", show_alert=True)
        return
    if product.stock <= 0:
        await call.answer("К сожалению, товар закончился.", show_alert=True)
        return

    provider = TelegramStarsProvider()
    amount_stars = provider.amount_for(product)
    order_id = await db.execute(
        """
        INSERT INTO orders (user_id, product_id, price_rub, price_stars, provider, payload, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending');
        """,
        (
            call.from_user.id,
            product.id,
            product.price_rub,
            amount_stars,
            provider.name,
            f"order:tmp:{call.from_user.id}:{product.id}:{call.id}",
        ),
    )
    # Bind order to a stable payload aligned with provider format.
    await db.execute(
        "UPDATE orders SET payload = ? WHERE id = ?;",
        (f"order:{order_id}", order_id),
    )

    result = await provider.create_invoice(
        bot=bot, chat_id=call.message.chat.id, order_id=order_id, product=product
    )
    if not result.ok:
        await db.execute(
            "UPDATE orders SET status = 'failed' WHERE id = ?;",
            (order_id,),
        )
        await call.answer(result.message or "Ошибка оплаты.", show_alert=True)
        return

    await call.answer("⭐ Счёт отправлен. Подтвердите оплату в Telegram.")


def _format_product(product) -> str:
    stock_emoji = "🟢" if product.stock > 0 else "🔴"
    desc = product.description.strip() or "Аккаунт World of Tanks Blitz."
    return (
        f"📦 <b>{product.title}</b>\n\n"
        f"📝 {desc}\n\n"
        f"💰 Цена: <b>{product.price_rub} ₽</b>\n"
        f"⭐ Stars: <b>{product.stars}</b>\n"
        f"{stock_emoji} В наличии: <b>{product.stock} шт.</b>"
    )
