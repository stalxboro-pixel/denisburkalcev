from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import LabeledPrice

from app.services.payments.base import PaymentProvider, PaymentResult
from app.services.products import Product

log = logging.getLogger("bot.payments.stars")


class TelegramStarsProvider(PaymentProvider):
    name = "stars"
    currency = "XTR"

    def amount_for(self, product: Product) -> int:
        return max(1, int(product.stars))

    async def create_invoice(
        self,
        *,
        bot: Bot,
        chat_id: int,
        order_id: int,
        product: Product,
    ) -> PaymentResult:
        amount = self.amount_for(product)
        title = product.title[:32] or "Аккаунт"
        description = (product.description or product.title)[:255] or "Покупка аккаунта"
        prices = [LabeledPrice(label=title, amount=amount)]
        # provider_token must be empty for Telegram Stars; payload binds invoice → order.
        try:
            await bot.send_invoice(
                chat_id=chat_id,
                title=title,
                description=description,
                payload=self._payload(order_id),
                provider_token="",
                currency=self.currency,
                prices=prices,
                start_parameter="buy",
                need_name=False,
                need_email=False,
                need_phone_number=False,
                need_shipping_address=False,
                is_flexible=False,
                protect_content=True,
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("send_invoice failed: %s", exc)
            return PaymentResult(ok=False, message="Не удалось создать счёт. Попробуйте позже.")
        return PaymentResult(ok=True)

    @staticmethod
    def _payload(order_id: int) -> str:
        return f"order:{order_id}"

    @staticmethod
    def parse_payload(payload: str) -> int | None:
        if not payload or not payload.startswith("order:"):
            return None
        try:
            return int(payload.split(":", 1)[1])
        except ValueError:
            return None
