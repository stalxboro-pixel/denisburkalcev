from __future__ import annotations

import logging

from app import db
from app.config import settings

log = logging.getLogger("bot.referrals")

_PREFIX = "r_"


def parse_payload(payload: str | None) -> int | None:
    """/start payload `r_<id>` → referrer user id, else None."""
    if not payload:
        return None
    payload = payload.strip()
    if not payload.startswith(_PREFIX):
        return None
    try:
        return int(payload[len(_PREFIX) :])
    except ValueError:
        return None


def referral_link(user_id: int) -> str:
    return f"https://t.me/{settings.bot_username}?start={_PREFIX}{user_id}"


async def attach_referrer(user_id: int, referrer_id: int) -> bool:
    if user_id == referrer_id:
        return False
    referrer = await db.fetchone("SELECT 1 FROM users WHERE user_id = ?;", (referrer_id,))
    if not referrer:
        return False
    user = await db.fetchone("SELECT referrer_id FROM users WHERE user_id = ?;", (user_id,))
    if not user or user["referrer_id"] is not None:
        return False
    await db.execute(
        "UPDATE users SET referrer_id = ? WHERE user_id = ? AND referrer_id IS NULL;",
        (referrer_id, user_id),
    )
    return True


async def reward_for_order(order_id: int, buyer_id: int, amount_rub: int) -> tuple[int, float] | None:
    """Apply referral reward once per order. Returns (referrer_id, reward) or None."""
    user = await db.fetchone("SELECT referrer_id FROM users WHERE user_id = ?;", (buyer_id,))
    if not user or not user["referrer_id"]:
        return None
    referrer_id = int(user["referrer_id"])
    reward = round(amount_rub * (settings.referral_percent / 100.0), 2)
    if reward <= 0:
        return None

    async with db.connect() as conn:
        try:
            await conn.execute(
                """
                INSERT INTO referral_rewards (order_id, referrer_id, referred_id, amount_rub)
                VALUES (?, ?, ?, ?);
                """,
                (order_id, referrer_id, buyer_id, reward),
            )
        except Exception:  # noqa: BLE001
            # Unique constraint on order_id keeps payouts idempotent.
            await conn.rollback()
            log.info("referral reward already applied for order %s", order_id)
            return None
        await conn.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?;",
            (reward, referrer_id),
        )
        await conn.commit()
    return referrer_id, reward
