from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# Main menu labels — these strings are also used by handlers as filters.
BTN_BUY = "📖 Купить акк"
BTN_PROFILE = "👤 Профиль"
BTN_INFO = "ℹ️ Инфо"
BTN_SUPPORT = "☎️ Поддержка"
BTN_ADMIN = "🛠 Админка"


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = [
        [KeyboardButton(text=BTN_BUY)],
        [KeyboardButton(text=BTN_PROFILE), KeyboardButton(text=BTN_INFO)],
        [KeyboardButton(text=BTN_SUPPORT)],
    ]
    if is_admin:
        rows.append([KeyboardButton(text=BTN_ADMIN)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)


# --- Callback factories ---------------------------------------------------

class ProductCB(CallbackData, prefix="prod"):
    action: str  # view | buy | back
    product_id: int = 0


class BuyCB(CallbackData, prefix="buy"):
    provider: str  # stars | contact
    product_id: int


class AdminCB(CallbackData, prefix="adm"):
    action: str
    product_id: int = 0
    page: int = 0


# --- Inline keyboards -----------------------------------------------------

def products_keyboard(products: list[tuple[int, str, int, int]]) -> InlineKeyboardMarkup:
    # products: list of (id, title, price_rub, stock)
    buttons: list[list[InlineKeyboardButton]] = []
    for pid, title, price, stock in products:
        label = f"{title} | {price} ₽ | {stock} шт."
        buttons.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=ProductCB(action="view", product_id=pid).pack(),
                )
            ]
        )
    if not buttons:
        buttons.append(
            [InlineKeyboardButton(text="Нет товаров", callback_data="noop")]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_card_keyboard(product_id: int, support_contact: str, can_buy: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_buy:
        rows.append(
            [
                InlineKeyboardButton(
                    text="⭐ Купить за Stars",
                    callback_data=BuyCB(provider="stars", product_id=product_id).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="💬 Купить через менеджера",
                url=f"https://t.me/{support_contact}",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅ Назад к списку",
                callback_data=ProductCB(action="back").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_root_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📦 Товары", callback_data=AdminCB(action="products").pack())],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data=AdminCB(action="users").pack())],
        [InlineKeyboardButton(text="🧾 Заказы", callback_data=AdminCB(action="orders").pack())],
        [InlineKeyboardButton(text="✏️ Текст «Инфо»", callback_data=AdminCB(action="edit_info").pack())],
        [InlineKeyboardButton(text="✏️ Текст «Поддержка»", callback_data=AdminCB(action="edit_support").pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_products_keyboard(items: list[tuple[int, str, int, int, bool]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for pid, title, price, stock, enabled in items:
        flag = "🟢" if enabled else "⚪"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{flag} {title} | {price}₽ | {stock}шт",
                    callback_data=AdminCB(action="prod_view", product_id=pid).pack(),
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data=AdminCB(action="prod_add").pack())]
    )
    rows.append(
        [InlineKeyboardButton(text="⬅ Назад", callback_data=AdminCB(action="root").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_product_keyboard(product_id: int, enabled: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="✏️ Название", callback_data=AdminCB(action="prod_edit_title", product_id=product_id).pack()),
            InlineKeyboardButton(text="📝 Описание", callback_data=AdminCB(action="prod_edit_desc", product_id=product_id).pack()),
        ],
        [
            InlineKeyboardButton(text="💰 Цена ₽", callback_data=AdminCB(action="prod_edit_price", product_id=product_id).pack()),
            InlineKeyboardButton(text="⭐ Цена Stars", callback_data=AdminCB(action="prod_edit_stars", product_id=product_id).pack()),
        ],
        [
            InlineKeyboardButton(text="📦 Сток", callback_data=AdminCB(action="prod_edit_stock", product_id=product_id).pack()),
            InlineKeyboardButton(text="🖼 Фото", callback_data=AdminCB(action="prod_edit_photo", product_id=product_id).pack()),
        ],
        [
            InlineKeyboardButton(
                text=("⏸ Выключить" if enabled else "▶️ Включить"),
                callback_data=AdminCB(action="prod_toggle", product_id=product_id).pack(),
            ),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=AdminCB(action="prod_delete", product_id=product_id).pack()),
        ],
        [InlineKeyboardButton(text="⬅ К списку", callback_data=AdminCB(action="products").pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
