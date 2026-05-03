from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Iterable, Sequence

import aiosqlite

from app.config import settings

log = logging.getLogger("bot.db")

_SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id      INTEGER PRIMARY KEY,
        username     TEXT,
        first_name   TEXT,
        balance      REAL    NOT NULL DEFAULT 0,
        referrer_id  INTEGER,
        is_banned    INTEGER NOT NULL DEFAULT 0,
        created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (referrer_id) REFERENCES users(user_id) ON DELETE SET NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS products (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        code         TEXT    NOT NULL UNIQUE,
        title        TEXT    NOT NULL,
        description  TEXT    NOT NULL DEFAULT '',
        price_rub    INTEGER NOT NULL,
        price_stars  INTEGER NOT NULL DEFAULT 0,
        stock        INTEGER NOT NULL DEFAULT 0,
        enabled      INTEGER NOT NULL DEFAULT 1,
        photo        TEXT,
        position     INTEGER NOT NULL DEFAULT 0,
        created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS orders (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER NOT NULL,
        product_id   INTEGER NOT NULL,
        price_rub    INTEGER NOT NULL,
        price_stars  INTEGER NOT NULL,
        provider     TEXT    NOT NULL,
        payload      TEXT    NOT NULL UNIQUE,
        status       TEXT    NOT NULL DEFAULT 'pending',
        created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
        paid_at      TEXT,
        FOREIGN KEY (user_id)    REFERENCES users(user_id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS payments (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id          INTEGER NOT NULL,
        provider          TEXT    NOT NULL,
        provider_payload  TEXT    NOT NULL UNIQUE,
        amount            INTEGER NOT NULL,
        currency          TEXT    NOT NULL,
        raw               TEXT,
        created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (order_id) REFERENCES orders(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS referral_rewards (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id     INTEGER NOT NULL UNIQUE,
        referrer_id  INTEGER NOT NULL,
        referred_id  INTEGER NOT NULL,
        amount_rub   REAL    NOT NULL,
        created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (order_id)    REFERENCES orders(id),
        FOREIGN KEY (referrer_id) REFERENCES users(user_id),
        FOREIGN KEY (referred_id) REFERENCES users(user_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_products_enabled ON products(enabled, position);",
    "CREATE INDEX IF NOT EXISTS idx_orders_user      ON orders(user_id, status);",
    "CREATE INDEX IF NOT EXISTS idx_orders_status    ON orders(status);",
    "CREATE INDEX IF NOT EXISTS idx_users_referrer   ON users(referrer_id);",
)

# Initial seed for products. Stars price is computed from RUB if 0 at runtime.
_SEED_PRODUCTS: tuple[dict[str, Any], ...] = (
    {"code": "wotb_30_35",  "title": "30-35 топов",       "price_rub": 240, "stock": 2,   "position": 10},
    {"code": "wotb_20_26",  "title": "20-26 топов",       "price_rub": 140, "stock": 5,   "position": 20},
    {"code": "wotb_15_19",  "title": "15-19 топов",       "price_rub": 90,  "stock": 33,  "position": 30},
    {"code": "wotb_40_45",  "title": "40-45 топов",       "price_rub": 390, "stock": 3,   "position": 40},
    {"code": "wotb_5_9_eu", "title": "5-9 топов (EU)",    "price_rub": 40,  "stock": 262, "position": 50},
    {"code": "wotb_10_14",  "title": "10-14 топов",       "price_rub": 65,  "stock": 68,  "position": 60},
    {"code": "wotb_25_30",  "title": "25-30 топов",       "price_rub": 190, "stock": 2,   "position": 70},
)

_DEFAULT_INFO_TEXT = (
    "🛡 <b>Wot Blitz Shop</b>\n\n"
    "🎯 Магазин аккаунтов World of Tanks Blitz: тёмно-стильно, быстро, надёжно.\n\n"
    "📜 <b>Правила</b>\n"
    "• Покупка = согласие с условиями.\n"
    "• После оплаты выдача аккаунта в течение 5–30 минут.\n"
    "• Гарантия 24 часа на смену почты/первичный вход.\n\n"
    "💳 <b>Оплата</b>\n"
    "• Telegram Stars — мгновенно.\n"
    "• Скоро: CryptoBot, банковские карты.\n\n"
    "🛡 <b>Гарантии</b>\n"
    "• Замена при невалидном аккаунте в течение 24 ч.\n"
    "• Отзывы реальных клиентов.\n\n"
    "🗣 <b>Отзывы</b>: @BUMZILKA"
)

_DEFAULT_SUPPORT_TEXT = (
    "☎️ <b>Поддержка</b>\n\n"
    "По любым вопросам пишите: @BUMZILKA\n"
    "⏱ Ответ обычно в течение 1 часа.\n"
    "🛡 Не передавайте никому коды и пароли."
)


@asynccontextmanager
async def connect() -> AsyncIterator[aiosqlite.Connection]:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(settings.db_path) as conn:
        await conn.execute("PRAGMA foreign_keys = ON;")
        await conn.execute("PRAGMA journal_mode = WAL;")
        conn.row_factory = aiosqlite.Row
        yield conn


async def init_db() -> None:
    async with connect() as conn:
        for stmt in _SCHEMA:
            await conn.execute(stmt)
        await conn.commit()
    await _seed_products()
    await _seed_settings()


async def _seed_products() -> None:
    async with connect() as conn:
        cur = await conn.execute("SELECT COUNT(*) AS n FROM products;")
        row = await cur.fetchone()
        if row and row["n"] > 0:
            return
        for p in _SEED_PRODUCTS:
            await conn.execute(
                """
                INSERT INTO products (code, title, description, price_rub, price_stars, stock, enabled, position)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?);
                """,
                (
                    p["code"],
                    p["title"],
                    p.get("description", "Аккаунт WoT Blitz"),
                    int(p["price_rub"]),
                    int(p.get("price_stars", 0)),
                    int(p["stock"]),
                    int(p["position"]),
                ),
            )
        await conn.commit()
        log.info("seeded %d products", len(_SEED_PRODUCTS))


async def _seed_settings() -> None:
    defaults = {
        "info_text": _DEFAULT_INFO_TEXT,
        "info_photo": "",
        "support_text": _DEFAULT_SUPPORT_TEXT,
    }
    async with connect() as conn:
        for key, value in defaults.items():
            await conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);",
                (key, value),
            )
        await conn.commit()


# Generic helpers — never use string concat for SQL values.

async def fetchone(query: str, params: Sequence[Any] = ()) -> aiosqlite.Row | None:
    async with connect() as conn:
        cur = await conn.execute(query, params)
        return await cur.fetchone()


async def fetchall(query: str, params: Sequence[Any] = ()) -> list[aiosqlite.Row]:
    async with connect() as conn:
        cur = await conn.execute(query, params)
        return list(await cur.fetchall())


async def execute(query: str, params: Sequence[Any] = ()) -> int:
    async with connect() as conn:
        cur = await conn.execute(query, params)
        await conn.commit()
        return cur.lastrowid or 0


async def executemany(query: str, params_list: Iterable[Sequence[Any]]) -> None:
    async with connect() as conn:
        await conn.executemany(query, list(params_list))
        await conn.commit()


async def get_setting(key: str, default: str = "") -> str:
    row = await fetchone("SELECT value FROM settings WHERE key = ?;", (key,))
    return row["value"] if row else default


async def set_setting(key: str, value: str) -> None:
    await execute(
        """
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value;
        """,
        (key, value),
    )
