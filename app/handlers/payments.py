from __future__ import annotations

import json
import logging

from aiogram import Bot, F, Router
from aiogram.types import Message, PreCheckoutQuery

from app import db
from app.services import products as products_svc, referrals
from app.services.payments.telegram_stars import TelegramStarsProvider

log = logging.getLogger("bot.handlers.payments")

router = Router(name="payments")


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, bot: Bot) -> None:
    order_id = TelegramStarsProvider.parse_payload(query.invoice_payload or "")
    ok = False
    error = "Заказ не найден."
    if order_id is not None:
        row = await db.fetchone(
            "SELECT id, status, price_stars, product_id FROM orders WHERE id = ?;",
            (order_id,),
        )
        if row and row["status"] == "pending":
            product = await products_svc.get(int(row["product_id"]))
            if product is None or not product.enabled:
                error = "Товар недоступен."
            elif product.stock <= 0:
                error = "Товар закончился."
            elif int(row["price_stars"]) != int(query.total_amount):
                error = "Сумма не совпадает."
            else:
                ok = True

    try:
        await bot.answer_pre_checkout_query(query.id, ok=ok, error_message=None if ok else error)
    except Exception:  # noqa: BLE001
        log.exception("pre_checkout answer failed")


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    sp = message.successful_payment
    if sp is None or message.from_user is None:
        return

    order_id = TelegramStarsProvider.parse_payload(sp.invoice_payload or "")
    if order_id is None:
        log.warning("successful_payment with bad payload: %s", sp.invoice_payload)
        return

    # Idempotency: claim the order atomically; reject if already paid.
    async with db.connect() as conn:
        cur = await conn.execute(
            """
            UPDATE orders
            SET status = 'paid', paid_at = datetime('now')
            WHERE id = ? AND status = 'pending';
            """,
            (order_id,),
        )
        await conn.commit()
        if cur.rowcount == 0:
            log.info("duplicate payment ignored for order %s", order_id)
            return

    row = await db.fetchone(
        "SELECT user_id, product_id, price_rub, price_stars FROM orders WHERE id = ?;",
        (order_id,),
    )
    if row is None:
        return

    product_id = int(row["product_id"])
    buyer_id = int(row["user_id"])
    price_rub = int(row["price_rub"])

    if not await products_svc.decrement_stock(product_id):
        log.error("stock race lost for order %s product %s", order_id, product_id)

    await db.execute(
        """
        INSERT OR IGNORE INTO payments (order_id, provider, provider_payload, amount, currency, raw)
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (
            order_id,
            "stars",
            sp.telegram_payment_charge_id or sp.provider_payment_charge_id or f"order:{order_id}",
            int(sp.total_amount or 0),
            sp.currency or "XTR",
            json.dumps(sp.model_dump(mode="json"), ensure_ascii=False),
        ),
    )

    rewarded = await referrals.reward_for_order(order_id, buyer_id, price_rub)

    product = await products_svc.get(product_id)
    title = product.title if product else "Товар"
    text = (
        "✅ <b>Оплата получена!</b>\n\n"
        f"📦 Товар: <b>{title}</b>\n"
        f"⭐ Списано Stars: <b>{int(row['price_stars'])}</b>\n"
        f"🧾 Заказ #️⃣ <code>{order_id}</code>\n\n"
        "🚚 Аккаунт будет выдан менеджером в течение 5–30 минут.\n"
        "✉️ Если в течение часа не пришли данные — пишите в поддержку."
    )
    await message.answer(text)

    if rewarded:
        ref_id, amount = rewarded
        try:
            await message.bot.send_message(
                ref_id,
                f"💎 Реферальный бонус: +{amount:.2f} ₽ за покупку вашего реферала.",
            )
        except Exception:  # noqa: BLE001
            log.debug("failed to notify referrer %s", ref_id, exc_info=True)
