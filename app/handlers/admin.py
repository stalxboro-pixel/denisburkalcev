from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app import db, keyboards as kb
from app.config import settings
from app.keyboards import AdminCB
from app.services import products as products_svc

log = logging.getLogger("bot.handlers.admin")

router = Router(name="admin")


class AdminStates(StatesGroup):
    waiting_field_value = State()
    waiting_new_product = State()
    waiting_user_balance = State()
    waiting_text_block = State()


def _is_admin(user_id: int | None) -> bool:
    return user_id is not None and settings.is_admin(user_id)


def admin_only(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    # Defence in depth — every admin handler re-checks the caller.
    async def wrapper(event, *args, **kwargs):  # type: ignore[no-untyped-def]
        user_id = getattr(getattr(event, "from_user", None), "id", None)
        if not _is_admin(user_id):
            if isinstance(event, CallbackQuery):
                await event.answer("🚫 Нет доступа.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("🚫 Нет доступа.")
            return None
        return await func(event, *args, **kwargs)

    return wrapper


# --- Entry points ---------------------------------------------------------

@router.message(Command("admin"))
@admin_only
async def admin_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await open_admin(message)


async def open_admin(message: Message) -> None:
    await message.answer("🛠 <b>Админ-панель</b>", reply_markup=kb.admin_root_keyboard())


@router.callback_query(AdminCB.filter(F.action == "root"))
@admin_only
async def admin_root(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if call.message:
        try:
            await call.message.edit_text("🛠 <b>Админ-панель</b>", reply_markup=kb.admin_root_keyboard())
        except TelegramBadRequest:
            await call.message.answer("🛠 <b>Админ-панель</b>", reply_markup=kb.admin_root_keyboard())
    await call.answer()


# --- Products list / view ------------------------------------------------

@router.callback_query(AdminCB.filter(F.action == "products"))
@admin_only
async def admin_products(call: CallbackQuery) -> None:
    items = await products_svc.list_all()
    keyboard = kb.admin_products_keyboard(
        [(p.id, p.title, p.price_rub, p.stock, p.enabled) for p in items]
    )
    if call.message:
        try:
            await call.message.edit_text("📦 <b>Товары</b>", reply_markup=keyboard)
        except TelegramBadRequest:
            await call.message.answer("📦 <b>Товары</b>", reply_markup=keyboard)
    await call.answer()


@router.callback_query(AdminCB.filter(F.action == "prod_view"))
@admin_only
async def admin_product_view(call: CallbackQuery, callback_data: AdminCB) -> None:
    product = await products_svc.get(callback_data.product_id)
    if product is None:
        await call.answer("Товар не найден.", show_alert=True)
        return
    text = _admin_product_text(product)
    keyboard = kb.admin_product_keyboard(product.id, product.enabled)
    if call.message:
        try:
            await call.message.edit_text(text, reply_markup=keyboard)
        except TelegramBadRequest:
            await call.message.answer(text, reply_markup=keyboard)
    await call.answer()


@router.callback_query(AdminCB.filter(F.action == "prod_toggle"))
@admin_only
async def admin_toggle(call: CallbackQuery, callback_data: AdminCB) -> None:
    new_state = await products_svc.toggle(callback_data.product_id)
    await call.answer("Включён." if new_state else "Выключен.")
    await admin_product_view(call, callback_data)


@router.callback_query(AdminCB.filter(F.action == "prod_delete"))
@admin_only
async def admin_delete(call: CallbackQuery, callback_data: AdminCB) -> None:
    await products_svc.delete(callback_data.product_id)
    await call.answer("Удалено.")
    await admin_products(call)


# --- Products edit (FSM) -------------------------------------------------

_FIELD_PROMPTS: dict[str, tuple[str, str]] = {
    "prod_edit_title": ("title", "Введите новое название:"),
    "prod_edit_desc": ("description", "Введите описание:"),
    "prod_edit_price": ("price_rub", "Введите цену в рублях (целое число):"),
    "prod_edit_stars": ("price_stars", "Введите цену в Stars (целое; 0 = авторасчёт):"),
    "prod_edit_stock": ("stock", "Введите остаток (целое):"),
    "prod_edit_photo": ("photo", "Отправьте file_id или URL фото (или '-' чтобы удалить):"),
}


@router.callback_query(AdminCB.filter(F.action.in_(set(_FIELD_PROMPTS.keys()))))
@admin_only
async def admin_edit_field(call: CallbackQuery, callback_data: AdminCB, state: FSMContext) -> None:
    field, prompt = _FIELD_PROMPTS[callback_data.action]
    await state.set_state(AdminStates.waiting_field_value)
    await state.update_data(product_id=callback_data.product_id, field=field)
    if call.message:
        await call.message.answer(prompt)
    await call.answer()


@router.message(AdminStates.waiting_field_value)
@admin_only
async def admin_apply_field(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    product_id = int(data.get("product_id", 0))
    field = str(data.get("field", ""))
    raw = (message.text or "").strip()

    try:
        value = _coerce_field_value(field, raw)
    except ValueError as exc:
        await message.answer(f"❌ Ошибка: {exc}")
        return

    try:
        await products_svc.update_field(product_id, field, value)
    except ValueError:
        await message.answer("❌ Запрещённое поле.")
        await state.clear()
        return

    await state.clear()
    await message.answer("✅ Сохранено.")


@router.callback_query(AdminCB.filter(F.action == "prod_add"))
@admin_only
async def admin_add_product(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_new_product)
    if call.message:
        await call.message.answer(
            "Введите новый товар одной строкой:\n"
            "<code>code | title | price_rub | stock | description</code>\n\n"
            "Пример:\n"
            "<code>wotb_50_top | 50+ топов | 600 | 1 | Премиум аккаунт</code>"
        )
    await call.answer()


@router.message(AdminStates.waiting_new_product)
@admin_only
async def admin_create_product(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 4:
        await message.answer("❌ Нужно минимум 4 поля через `|`.")
        return
    code, title = parts[0], parts[1]
    try:
        price_rub = int(parts[2])
        stock = int(parts[3])
    except ValueError:
        await message.answer("❌ Цена и сток должны быть числами.")
        return
    description = parts[4] if len(parts) > 4 else ""
    if not code or not title:
        await message.answer("❌ Код и название обязательны.")
        return

    try:
        product_id = await products_svc.create(
            code=code,
            title=title,
            description=description,
            price_rub=price_rub,
            stock=stock,
        )
    except Exception as exc:  # noqa: BLE001
        await message.answer(f"❌ Не удалось создать: {exc}")
        return

    await state.clear()
    await message.answer(f"✅ Создан товар #{product_id}.")


# --- Texts (info / support) ---------------------------------------------

@router.callback_query(AdminCB.filter(F.action.in_({"edit_info", "edit_support"})))
@admin_only
async def admin_edit_text(call: CallbackQuery, callback_data: AdminCB, state: FSMContext) -> None:
    key = "info_text" if callback_data.action == "edit_info" else "support_text"
    await state.set_state(AdminStates.waiting_text_block)
    await state.update_data(setting_key=key)
    if call.message:
        await call.message.answer("Отправьте новый текст блока:")
    await call.answer()


@router.message(AdminStates.waiting_text_block)
@admin_only
async def admin_save_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    key = str(data.get("setting_key", ""))
    if key not in {"info_text", "support_text", "info_photo"}:
        await state.clear()
        return
    await db.set_setting(key, message.text or message.caption or "")
    await state.clear()
    await message.answer("✅ Сохранено.")


# --- Users / orders ------------------------------------------------------

@router.callback_query(AdminCB.filter(F.action == "users"))
@admin_only
async def admin_users(call: CallbackQuery) -> None:
    rows = await db.fetchall(
        "SELECT user_id, username, balance, created_at FROM users ORDER BY created_at DESC LIMIT 25;"
    )
    lines = ["👥 <b>Последние пользователи</b>\n"]
    for r in rows:
        nick = f"@{r['username']}" if r["username"] else "—"
        lines.append(f"<code>{r['user_id']}</code> · {nick} · {float(r['balance']):.2f}₽")
    if not rows:
        lines.append("Пусто.")
    if call.message:
        try:
            await call.message.edit_text("\n".join(lines), reply_markup=kb.admin_root_keyboard())
        except TelegramBadRequest:
            await call.message.answer("\n".join(lines), reply_markup=kb.admin_root_keyboard())
    await call.answer()


@router.callback_query(AdminCB.filter(F.action == "orders"))
@admin_only
async def admin_orders(call: CallbackQuery) -> None:
    rows = await db.fetchall(
        """
        SELECT o.id, o.user_id, o.price_rub, o.price_stars, o.status, o.created_at, p.title
        FROM orders o
        JOIN products p ON p.id = o.product_id
        ORDER BY o.id DESC LIMIT 20;
        """
    )
    lines = ["🧾 <b>Последние заказы</b>\n"]
    for r in rows:
        lines.append(
            f"#{r['id']} · {r['status']} · {r['title']} · {r['price_rub']}₽ / {r['price_stars']}⭐ · uid <code>{r['user_id']}</code>"
        )
    if not rows:
        lines.append("Пусто.")
    if call.message:
        try:
            await call.message.edit_text("\n".join(lines), reply_markup=kb.admin_root_keyboard())
        except TelegramBadRequest:
            await call.message.answer("\n".join(lines), reply_markup=kb.admin_root_keyboard())
    await call.answer()


@router.message(Command("balance"))
@admin_only
async def admin_balance(message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Использование: /balance <user_id> <delta>")
        return
    try:
        user_id = int(parts[1])
        delta = float(parts[2])
    except ValueError:
        await message.answer("❌ Числа.")
        return
    await db.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?;",
        (delta, user_id),
    )
    await message.answer(f"✅ Баланс пользователя {user_id} изменён на {delta:+.2f} ₽.")


# --- helpers -------------------------------------------------------------

def _coerce_field_value(field: str, raw: str) -> object:
    if field in {"price_rub", "price_stars", "stock"}:
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError("ожидается целое число") from exc
        if value < 0:
            raise ValueError("значение не может быть отрицательным")
        return value
    if field == "photo":
        return None if raw in {"-", ""} else raw
    if field in {"title", "description"}:
        if not raw:
            raise ValueError("пустое значение")
        return raw[:1000]
    raise ValueError("неизвестное поле")


def _admin_product_text(product) -> str:
    return (
        f"📦 <b>{product.title}</b>\n"
        f"🔑 code: <code>{product.code}</code>\n"
        f"💰 {product.price_rub} ₽ · ⭐ {product.price_stars or product.stars} (auto)\n"
        f"📦 Сток: {product.stock}\n"
        f"⚙️ Включён: {'да' if product.enabled else 'нет'}\n\n"
        f"📝 {product.description or '—'}"
    )
