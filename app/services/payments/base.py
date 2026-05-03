from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from aiogram import Bot

from app.services.products import Product


@dataclass(slots=True)
class PaymentResult:
    ok: bool
    message: str = ""


class PaymentProvider(ABC):
    """Abstract payment adapter. Add CryptoBot/cards by subclassing this."""

    name: str = "base"
    currency: str = "XTR"

    @abstractmethod
    async def create_invoice(
        self,
        *,
        bot: Bot,
        chat_id: int,
        order_id: int,
        product: Product,
    ) -> PaymentResult:
        """Send an invoice/checkout link to the user."""

    @abstractmethod
    def amount_for(self, product: Product) -> int:
        """Return amount in the provider's smallest unit (stars / kopecks / etc)."""
