"""
Client-facing bot handlers for CHM GOLD EXCHANGE.
Full FSM-based order creation flow.
"""

import json
import logging
import os
import uuid
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from api.commission import DIRECTION_META, calculate_client_amount
from api.cryptoxchange import get_rates
from database.engine import AsyncSessionLocal
from database.models import Order, OrderStatus

logger = logging.getLogger(__name__)

router = Router()

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

# --------------------------------------------------------------------------
# FSM States
# --------------------------------------------------------------------------
class OrderFSM(StatesGroup):
    direction = State()
    amount    = State()
    requisites = State()
    city      = State()
    confirm   = State()


# --------------------------------------------------------------------------
# Direction config
# --------------------------------------------------------------------------
DIRECTIONS = {
    "USD_RUB":  ("🇺🇸 USD → RUB",        "USD", "RUB",  1000,  "sell"),
    "EUR_RUB":  ("🇪🇺 EUR → RUB",        "EUR", "RUB",  1000,  "sell"),
    "USDT_RUB": ("🔵 USDT → RUB",        "USDT","RUB",  100,   "sell"),
    "RUB_USDT": ("🔵 RUB → USDT",        "RUB", "USDT", 10000, "buy"),
    "CASH_RUB": ("💵 Наличные RUB",       "ANY", "RUB",  10000, "sell"),
}

STATUS_LABELS = {
    "pending":     "⏳ Ожидает подтверждения",
    "approved":    "✅ Принята в работу",
    "in_progress": "🔄 В обработке",
    "completed":   "✅ Выполнена",
    "cancelled":   "❌ Отменена",
}

REQUISITES_HINTS = {
    "USD_RUB":  "Введите банковские реквизиты или номер счёта получателя:",
    "EUR_RUB":  "Введите банковские реквизиты или номер счёта получателя:",
    "USDT_RUB": "Введите номер карты РФ (16 цифр) для получения рублей:",
    "RUB_USDT": "Введите USDT-кошелёк (TRC-20 или ERC-20):",
    "CASH_RUB": "Опишите пожелания (город, удобное время, сумма):",
}


# --------------------------------------------------------------------------
# Keyboards
# --------------------------------------------------------------------------
def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Актуальные курсы", callback_data="menu:rates")],
        [InlineKeyboardButton(text="💱 Создать заявку",    callback_data="menu:exchange")],
        [InlineKeyboardButton(text="📋 Мои заявки",        callback_data="menu:orders")],
    ])


def kb_directions() -> InlineKeyboardMarkup:
    rows = []
    for key, (label, *_) in DIRECTIONS.items():
        rows.append([InlineKeyboardButton(text=label, callback_data=f"dir:{key}")])
    rows.append([InlineKeyboardButton(text="◀ Назад", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="fsm:cancel")]
    ])


def kb_confirm(order_data: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить и отправить", callback_data="fsm:confirm")],
        [InlineKeyboardButton(text="✏️ Изменить",                callback_data="menu:exchange")],
        [InlineKeyboardButton(text="❌ Отменить",                callback_data="fsm:cancel")],
    ])


def kb_back_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")]
    ])


# --------------------------------------------------------------------------
# /start
# --------------------------------------------------------------------------
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    name = message.from_user.first_name or "друг"
    text = (
        f"👋 Привет, <b>{name}</b>!\n\n"
        "💎 <b>CHM GOLD EXCHANGE</b> — ваш надёжный обменник\n\n"
        "Мы работаем с:\n"
        "🇺🇸 USD → RUB (SWIFT-переводы)\n"
        "🇪🇺 EUR → RUB (SWIFT-переводы)\n"
        "🔵 USDT ↔ RUB (криптообмен)\n"
        "💵 Наличные RUB (по городам)\n\n"
        "Комиссия: <b>7%</b> — включена в курс\n"
        "Поддержка: <b>9:00–21:00 МСК</b>, без выходных\n\n"
        "Выберите действие:"
    )
    await message.answer(text, reply_markup=kb_main())


# --------------------------------------------------------------------------
# /rates command
# --------------------------------------------------------------------------
@router.message(Command("rates"))
async def cmd_rates(message: Message):
    await show_rates(message)


# --------------------------------------------------------------------------
# /myorders command
# --------------------------------------------------------------------------
@router.message(Command("myorders"))
async def cmd_myorders(message: Message):
    await show_orders(message)


# --------------------------------------------------------------------------
# /exchange command
# --------------------------------------------------------------------------
@router.message(Command("exchange"))
async def cmd_exchange(message: Message, state: FSMContext):
    await state.clear()
    await show_direction_select(message)


# --------------------------------------------------------------------------
# Menu callbacks
# --------------------------------------------------------------------------
@router.callback_query(F.data == "menu:main")
async def cb_menu_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    name = callback.from_user.first_name or "друг"
    text = (
        f"👋 Привет, <b>{name}</b>!\n\n"
        "💎 <b>CHM GOLD EXCHANGE</b> — ваш надёжный обменник\n\n"
        "Выберите действие:"
    )
    await callback.message.edit_text(text, reply_markup=kb_main())
    await callback.answer()


@router.callback_query(F.data == "menu:rates")
async def cb_menu_rates(callback: CallbackQuery):
    await callback.answer()
    await show_rates(callback.message, edit=True)


@router.callback_query(F.data == "menu:exchange")
async def cb_menu_exchange(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await show_direction_select(callback.message, edit=True)


@router.callback_query(F.data == "menu:orders")
async def cb_menu_orders(callback: CallbackQuery):
    await callback.answer()
    await show_orders(callback.message, user_id=callback.from_user.id, edit=True)


# --------------------------------------------------------------------------
# Show rates
# --------------------------------------------------------------------------
async def show_rates(message: Message, edit: bool = False):
    try:
        rates = await get_rates()
    except Exception as e:
        logger.error("Failed to get rates: %s", e)
        text = "😞 Не удалось загрузить курсы. Попробуйте позже."
        if edit:
            await message.edit_text(text, reply_markup=kb_back_main())
        else:
            await message.answer(text, reply_markup=kb_back_main())
        return

    from api.commission import apply_buy_rate, apply_sell_rate

    usd_base  = rates.get("USD_RUB",  90.0)
    eur_base  = rates.get("EUR_RUB",  98.0)
    usdt_base = rates.get("USDT_RUB", 90.5)

    text = (
        "📊 <b>АКТУАЛЬНЫЕ КУРСЫ</b>\n"
        "<b>CHM GOLD EXCHANGE</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💵 <b>SWIFT-переводы</b>\n"
        f"🇺🇸 USD → RUB: <b>{apply_sell_rate(usd_base):,.2f} ₽</b>\n"
        f"🇪🇺 EUR → RUB: <b>{apply_sell_rate(eur_base):,.2f} ₽</b>\n"
        "• Мин. сумма: 1 000 USD/EUR\n"
        "• Срок: 1–3 рабочих дня\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 <b>Обмен USDT ↔ RUB</b>\n"
        f"📈 Купить 1 USDT = <b>{apply_buy_rate(usdt_base):,.2f} ₽</b>\n"
        f"📉 Продать 1 USDT = <b>{apply_sell_rate(usdt_base):,.2f} ₽</b>\n"
        "• Мин. сумма: 100 USDT\n"
        "• Срок: 15–60 минут\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💵 <b>Наличные RUB</b>\n"
        "• Сумма: 10 000 – 500 000 ₽\n"
        "• Комиссия: 7%\n"
        "• Напишите город — уточним детали\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ Все курсы включают комиссию <b>7%</b>\n"
        "🕐 Обновление: 10:00 и 20:00 МСК"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💱 Создать заявку", callback_data="menu:exchange")],
        [InlineKeyboardButton(text="🏠 Главное меню",   callback_data="menu:main")],
    ])

    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


# --------------------------------------------------------------------------
# Show orders
# --------------------------------------------------------------------------
async def show_orders(message: Message, user_id: int = None, edit: bool = False):
    uid = user_id or message.chat.id

    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Order)
            .where(Order.user_id == uid)
            .order_by(Order.created_at.desc())
            .limit(10)
        )
        orders = result.scalars().all()

    if not orders:
        text = (
            "📭 <b>У вас пока нет заявок</b>\n\n"
            "Создайте свою первую заявку на обмен!"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💱 Создать заявку", callback_data="menu:exchange")],
            [InlineKeyboardButton(text="🏠 Главное меню",   callback_data="menu:main")],
        ])
        if edit:
            await message.edit_text(text, reply_markup=kb)
        else:
            await message.answer(text, reply_markup=kb)
        return

    lines = ["📋 <b>Ваши заявки</b> (последние 10):\n"]
    for o in orders:
        short_id = str(o.id)[:8].upper()
        label = DIRECTIONS.get(o.direction, (o.direction,))[0]
        status = STATUS_LABELS.get(o.status.value, o.status.value)
        lines.append(
            f"• <code>#{short_id}</code> | {label}\n"
            f"  {float(o.amount_from):,.2f} → {float(o.amount_to):,.2f}\n"
            f"  {status}\n"
        )

    text = "\n".join(lines)

    # Build per-order detail buttons
    rows = [[InlineKeyboardButton(
        text=f"#{str(o.id)[:8].upper()} — {STATUS_LABELS.get(o.status.value, '?')[:12]}",
        callback_data=f"order:{o.id}"
    )] for o in orders[:5]]
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


# --------------------------------------------------------------------------
# Order detail callback
# --------------------------------------------------------------------------
@router.callback_query(F.data.startswith("order:"))
async def cb_order_detail(callback: CallbackQuery):
    order_id_str = callback.data.split(":", 1)[1]
    from sqlalchemy import select
    try:
        order_uuid = uuid.UUID(order_id_str)
    except ValueError:
        await callback.answer("Неверный ID")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Order).where(Order.id == order_uuid))
        order = result.scalar_one_or_none()

    if not order or order.user_id != callback.from_user.id:
        await callback.answer("Заявка не найдена")
        return

    await callback.answer()

    short_id = str(order.id)[:8].upper()
    label = DIRECTIONS.get(order.direction, (order.direction,))[0]
    status = STATUS_LABELS.get(order.status.value, order.status.value)

    text = (
        f"📋 <b>Заявка #{short_id}</b>\n\n"
        f"💱 {label}\n"
        f"💰 Отдаёте: <b>{float(order.amount_from):,.2f}</b>\n"
        f"💵 Получаете: <b>{float(order.amount_to):,.2f}</b>\n"
        f"📊 Курс: {float(order.our_rate):.2f} (комиссия 7%)\n"
        f"📋 Реквизиты: <code>{order.requisites}</code>\n"
    )
    if order.city:
        text += f"🏙 Город: {order.city}\n"
    if order.cxc_order_id:
        text += f"🔗 CXC ID: <code>{order.cxc_order_id}</code>\n"
    if order.admin_note:
        text += f"📝 Примечание: {order.admin_note}\n"
    text += (
        f"\n📅 Создана: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"🔄 Статус: <b>{status}</b>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀ Мои заявки", callback_data="menu:orders")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)


# --------------------------------------------------------------------------
# FSM: Direction selection
# --------------------------------------------------------------------------
async def show_direction_select(message: Message, edit: bool = False):
    text = (
        "💱 <b>Создание заявки</b>\n\n"
        "Выберите направление обмена:"
    )
    if edit:
        await message.edit_text(text, reply_markup=kb_directions())
    else:
        await message.answer(text, reply_markup=kb_directions())


@router.callback_query(F.data.startswith("dir:"))
async def cb_direction(callback: CallbackQuery, state: FSMContext):
    direction = callback.data.split(":", 1)[1]
    if direction not in DIRECTIONS:
        await callback.answer("Неверное направление")
        return

    label, from_curr, to_curr, min_amount, trade_dir = DIRECTIONS[direction]
    await state.update_data(direction=direction)
    await state.set_state(OrderFSM.amount)
    await callback.answer()

    text = (
        f"💱 <b>{label}</b>\n\n"
        f"Введите сумму в <b>{from_curr}</b>:\n\n"
        f"📌 Минимальная сумма: <b>{min_amount:,} {from_curr}</b>"
    )
    await callback.message.edit_text(text, reply_markup=kb_cancel())


# --------------------------------------------------------------------------
# FSM: Amount
# --------------------------------------------------------------------------
@router.message(OrderFSM.amount)
async def fsm_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", ".").replace(" ", ""))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректную сумму (число больше 0):", reply_markup=kb_cancel())
        return

    data = await state.get_data()
    direction = data["direction"]
    label, from_curr, to_curr, min_amount, trade_dir = DIRECTIONS[direction]

    if amount < min_amount:
        await message.answer(
            f"❌ Минимальная сумма — <b>{min_amount:,} {from_curr}</b>\n\nВведите бо́льшую сумму:",
            reply_markup=kb_cancel(),
        )
        return

    # Fetch rates and calculate
    try:
        rates = await get_rates()
    except Exception:
        rates = {}

    rate_key = f"{from_curr}_{to_curr}"
    alt_key = f"{to_curr}_{from_curr}"
    if direction == "CASH_RUB":
        base_rate = rates.get("USD_RUB", 90.0)
    else:
        base_rate = rates.get(rate_key) or rates.get(alt_key) or 90.0

    calc = calculate_client_amount(base_rate, amount, trade_dir)

    await state.update_data(
        amount=amount,
        base_rate=base_rate,
        calc=calc,
    )
    await state.set_state(OrderFSM.requisites)

    hint = REQUISITES_HINTS.get(direction, "Введите реквизиты:")
    calc_text = (
        f"\n\n💡 <b>Предварительный расчёт:</b>\n"
        f"  Базовый курс: {calc['base_rate']:.2f}\n"
        f"  Наш курс (7%): <b>{calc['our_rate']:.2f}</b>\n"
        f"  Комиссия: {calc['commission']:,.2f} {to_curr}\n"
        f"  ✅ К получению: <b>{calc['total']:,.2f} {to_curr}</b>"
    )

    await message.answer(hint + calc_text, reply_markup=kb_cancel())


# --------------------------------------------------------------------------
# FSM: Requisites
# --------------------------------------------------------------------------
@router.message(OrderFSM.requisites)
async def fsm_requisites(message: Message, state: FSMContext):
    requisites = message.text.strip()
    if len(requisites) < 5:
        await message.answer("❌ Реквизиты слишком короткие. Введите подробнее:", reply_markup=kb_cancel())
        return

    data = await state.get_data()
    direction = data["direction"]

    await state.update_data(requisites=requisites)

    if direction == "CASH_RUB":
        await state.set_state(OrderFSM.city)
        await message.answer(
            "🏙 Укажите ваш <b>город</b> для получения наличных:",
            reply_markup=kb_cancel(),
        )
    else:
        await state.set_state(OrderFSM.confirm)
        await show_confirmation(message, state)


# --------------------------------------------------------------------------
# FSM: City (CASH_RUB only)
# --------------------------------------------------------------------------
@router.message(OrderFSM.city)
async def fsm_city(message: Message, state: FSMContext):
    city = message.text.strip()
    if len(city) < 2:
        await message.answer("❌ Введите название города:", reply_markup=kb_cancel())
        return
    await state.update_data(city=city)
    await state.set_state(OrderFSM.confirm)
    await show_confirmation(message, state)


# --------------------------------------------------------------------------
# FSM: Confirm
# --------------------------------------------------------------------------
async def show_confirmation(message: Message, state: FSMContext):
    data = await state.get_data()
    direction = data["direction"]
    amount = data["amount"]
    calc = data["calc"]
    requisites = data["requisites"]
    city = data.get("city")

    label, from_curr, to_curr, _, _ = DIRECTIONS[direction]

    text = (
        "📋 <b>Подтверждение заявки</b>\n\n"
        f"💱 {label}\n"
        f"💰 Вы отдаёте: <b>{amount:,.2f} {from_curr}</b>\n"
        f"💵 Вы получаете: <b>{calc['total']:,.2f} {to_curr}</b>\n"
        f"📊 Курс: <b>{calc['our_rate']:.2f}</b> (включая комиссию 7%)\n"
        f"💸 Комиссия: {calc['commission']:,.2f} {to_curr}\n"
        f"📋 Реквизиты: <code>{requisites}</code>\n"
    )
    if city:
        text += f"🏙 Город: {city}\n"
    text += "\n<b>Всё верно?</b>"

    await message.answer(text, reply_markup=kb_confirm(data))


@router.callback_query(F.data == "fsm:confirm")
async def cb_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data:
        await callback.answer("Сессия истекла. Начните заново.", show_alert=True)
        await state.clear()
        return

    await callback.answer()

    direction = data["direction"]
    amount = data["amount"]
    calc = data["calc"]
    requisites = data["requisites"]
    city = data.get("city")
    label, from_curr, to_curr, _, _ = DIRECTIONS[direction]

    # Create order in DB
    order = Order(
        id=uuid.uuid4(),
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        direction=direction,
        amount_from=amount,
        amount_to=calc["total"],
        base_rate=calc["base_rate"],
        our_rate=calc["our_rate"],
        commission=calc["commission"],
        requisites=requisites,
        city=city,
        status=OrderStatus.pending,
    )

    async with AsyncSessionLocal() as db:
        db.add(order)
        await db.commit()
        await db.refresh(order)

    await state.clear()

    short_id = str(order.id)[:8].upper()
    text = (
        f"✅ <b>Заявка #{short_id} принята!</b>\n\n"
        f"💱 {label}\n"
        f"💰 Вы отдаёте: <b>{amount:,.2f} {from_curr}</b>\n"
        f"💵 Вы получаете: <b>{calc['total']:,.2f} {to_curr}</b>\n"
        f"📊 Курс: <b>{calc['our_rate']:.2f}</b> (включая комиссию 7%)\n"
        f"📋 Реквизиты: <code>{requisites}</code>\n"
    )
    if city:
        text += f"🏙 Город: {city}\n"
    text += (
        "\n⏳ <b>Статус:</b> Ожидает подтверждения\n\n"
        "Наш менеджер свяжется с вами в рабочее время:\n"
        "🕐 9:00–21:00 МСК, без выходных"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Мои заявки",   callback_data="menu:orders")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)

    logger.info(
        "Order created via bot: id=%s user_id=%s direction=%s amount=%s",
        order.id, callback.from_user.id, direction, amount,
    )

    # Notify admin
    await _notify_admin_new_order(callback.bot, order)


@router.callback_query(F.data == "fsm:cancel")
async def cb_fsm_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Отменено")
    await callback.message.edit_text(
        "❌ Создание заявки отменено.",
        reply_markup=kb_main(),
    )


# --------------------------------------------------------------------------
# Admin notification on new order
# --------------------------------------------------------------------------
async def _notify_admin_new_order(bot, order: Order) -> None:
    if not ADMIN_CHAT_ID:
        return

    short_id = str(order.id)[:8].upper()
    label = DIRECTIONS.get(order.direction, (order.direction,))[0]
    user_link = f"@{order.username}" if order.username else f"ID {order.user_id}"

    text = (
        f"🔔 <b>Новая заявка #{short_id}</b>\n\n"
        f"👤 Клиент: {user_link}\n"
        f"💱 {label}\n"
        f"💰 Отдаёт: <b>{float(order.amount_from):,.2f}</b>\n"
        f"💵 Получает: <b>{float(order.amount_to):,.2f}</b>\n"
        f"📊 Наш курс: {float(order.our_rate):.2f}\n"
        f"💸 Комиссия: {float(order.commission):,.2f}\n"
        f"📋 Реквизиты: <code>{order.requisites}</code>\n"
    )
    if order.city:
        text += f"🏙 Город: {order.city}\n"
    text += f"\n🆔 Полный ID: <code>{order.id}</code>"

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять",   callback_data=f"approve:{order.id}"),
            InlineKeyboardButton(text="❌ Отменить",  callback_data=f"cancel:{order.id}"),
        ]
    ])

    try:
        await bot.send_message(ADMIN_CHAT_ID, text, reply_markup=kb)
    except Exception as e:
        logger.error("Failed to notify admin about new order %s: %s", order.id, e)


# --------------------------------------------------------------------------
# Notification senders (called from admin handler / routes)
# --------------------------------------------------------------------------
def _get_bot():
    try:
        from bot.main import bot
        return bot
    except Exception:
        return None


async def notify_order_created(order) -> None:
    bot = _get_bot()
    if not bot:
        return
    short_id = str(order.id)[:8].upper()
    label = DIRECTIONS.get(order.direction, (order.direction,))[0]
    text = (
        f"✅ <b>Заявка #{short_id} принята!</b>\n\n"
        f"💱 {label}\n"
        f"💰 Отдаёте: <b>{float(order.amount_from):,.2f}</b>\n"
        f"💵 Получаете: <b>{float(order.amount_to):,.2f}</b>\n"
        f"📊 Курс: {float(order.our_rate):.2f} (комиссия 7%)\n\n"
        "⏳ Статус: Ожидает подтверждения\n"
        "🕐 9:00–21:00 МСК, без выходных"
    )
    try:
        await bot.send_message(order.user_id, text)
    except Exception as e:
        logger.error("notify_order_created failed for user %s: %s", order.user_id, e)


async def notify_order_approved(order) -> None:
    bot = _get_bot()
    if not bot:
        return
    short_id = str(order.id)[:8].upper()
    label = DIRECTIONS.get(order.direction, (order.direction,))[0]
    text = (
        f"✅ <b>Заявка #{short_id} принята в работу!</b>\n\n"
        f"💱 {label}\n"
        f"💵 К получению: <b>{float(order.amount_to):,.2f}</b>\n\n"
        "Ожидайте — мы обрабатываем вашу заявку."
    )
    if order.admin_note:
        text += f"\n📝 Комментарий: {order.admin_note}"
    try:
        await bot.send_message(order.user_id, text)
    except Exception as e:
        logger.error("notify_order_approved failed for user %s: %s", order.user_id, e)


async def notify_order_in_progress(order) -> None:
    bot = _get_bot()
    if not bot:
        return
    short_id = str(order.id)[:8].upper()
    label = DIRECTIONS.get(order.direction, (order.direction,))[0]
    text = (
        f"🔄 <b>Заявка #{short_id} в обработке!</b>\n\n"
        f"💱 {label}\n\n"
        "Операция выполняется. Уведомим вас о завершении."
    )
    try:
        await bot.send_message(order.user_id, text)
    except Exception as e:
        logger.error("notify_order_in_progress failed for user %s: %s", order.user_id, e)


async def notify_order_completed(order) -> None:
    bot = _get_bot()
    if not bot:
        return
    short_id = str(order.id)[:8].upper()
    label = DIRECTIONS.get(order.direction, (order.direction,))[0]
    text = (
        f"🎉 <b>Заявка #{short_id} выполнена!</b>\n\n"
        f"💱 {label}\n"
        f"💵 Вы получили: <b>{float(order.amount_to):,.2f}</b>\n\n"
        "Спасибо за доверие к CHM GOLD EXCHANGE! 🙏\n"
        "Будем рады видеть вас снова."
    )
    if order.admin_note:
        text += f"\n\n📝 Комментарий: {order.admin_note}"
    try:
        await bot.send_message(order.user_id, text)
    except Exception as e:
        logger.error("notify_order_completed failed for user %s: %s", order.user_id, e)


async def notify_order_cancelled(order, reason: str = "") -> None:
    bot = _get_bot()
    if not bot:
        return
    short_id = str(order.id)[:8].upper()
    label = DIRECTIONS.get(order.direction, (order.direction,))[0]
    text = (
        f"❌ <b>Заявка #{short_id} отменена</b>\n\n"
        f"💱 {label}\n"
    )
    if reason:
        text += f"\n📝 Причина: {reason}"
    text += "\n\nЕсли есть вопросы — напишите нам. Будем рады помочь."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💱 Новая заявка", callback_data="menu:exchange")]
    ])
    try:
        await bot.send_message(order.user_id, text, reply_markup=kb)
    except Exception as e:
        logger.error("notify_order_cancelled failed for user %s: %s", order.user_id, e)
