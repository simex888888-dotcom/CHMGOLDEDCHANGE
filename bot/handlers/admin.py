"""
Admin command handlers for CHM GOLD EXCHANGE bot.
All commands restricted to ADMIN_CHAT_ID.
"""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import func, select

from api.commission import DIRECTION_META, apply_buy_rate, apply_sell_rate
from api.cryptoxchange import get_rates
from database.engine import AsyncSessionLocal
from database.models import Order, OrderStatus

logger = logging.getLogger(__name__)

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

# Router with admin-only filter applied at the router level
from aiogram.filters import Filter

class IsAdmin(Filter):
    async def __call__(self, event) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and user.id == ADMIN_CHAT_ID)

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())
MINI_APP_URL = os.getenv("MINI_APP_URL", "")

DIRECTION_LABELS = {
    "USD_RUB": "USD → RUB",
    "EUR_RUB": "EUR → RUB",
    "USDT_RUB": "USDT → RUB",
    "RUB_USDT": "RUB → USDT",
    "CASH_RUB": "Наличные RUB",
}

STATUS_LABELS = {
    "pending": "⏳ Ожидает",
    "approved": "✅ Принята",
    "in_progress": "🔄 В работе",
    "completed": "✅ Выполнена",
    "cancelled": "❌ Отменена",
}



def _order_card(order: Order) -> str:
    short_id = str(order.id)[:8].upper()
    direction_label = DIRECTION_LABELS.get(order.direction, order.direction)
    status_label = STATUS_LABELS.get(order.status.value, order.status.value)

    text = (
        f"📋 <b>Заявка #{short_id}</b>\n"
        f"🆔 ID: <code>{order.id}</code>\n\n"
        f"👤 Пользователь: {f'@{order.username}' if order.username else 'без ника'} "
        f"(ID: <code>{order.user_id}</code>)\n"
        f"💱 Направление: {direction_label}\n"
        f"💰 Отдаёт: <b>{float(order.amount_from):,.2f}</b>\n"
        f"💵 Получает: <b>{float(order.amount_to):,.2f}</b>\n"
        f"📊 Базовый курс: {float(order.base_rate):.4f}\n"
        f"📊 Наш курс: {float(order.our_rate):.4f}\n"
        f"💸 Комиссия: {float(order.commission):,.2f}\n"
        f"📋 Реквизиты: <code>{order.requisites}</code>\n"
    )
    if order.city:
        text += f"🏙 Город: {order.city}\n"
    if order.cxc_order_id:
        text += f"🔗 CXC ID: <code>{order.cxc_order_id}</code>\n"
    text += (
        f"\n📅 Создана: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"🔄 Статус: {status_label}"
    )
    if order.admin_note:
        text += f"\n📝 Заметка: {order.admin_note}"
    return text


def _order_inline_kb(order: Order) -> InlineKeyboardMarkup:
    order_id = str(order.id)
    buttons = []
    status = order.status

    if status == OrderStatus.pending:
        buttons.append(InlineKeyboardButton(text="✅ Принять", callback_data=f"approve:{order_id}"))
    if status in (OrderStatus.pending, OrderStatus.approved):
        buttons.append(InlineKeyboardButton(text="🔄 В работе", callback_data=f"inprogress:{order_id}"))
    if status in (OrderStatus.approved, OrderStatus.in_progress):
        buttons.append(InlineKeyboardButton(text="✅ Выполнено", callback_data=f"complete:{order_id}"))
    if status not in (OrderStatus.completed, OrderStatus.cancelled):
        buttons.append(InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel:{order_id}"))

    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --------------------------------------------------------------------------
# /start
# --------------------------------------------------------------------------
@router.message(Command("start"))
async def cmd_start(message: Message):
    text = (
        "👋 <b>CHM GOLD EXCHANGE — Панель администратора</b>\n\n"
        "Доступные команды:\n\n"
        "📋 <b>Заявки</b>\n"
        "/orders — список всех заявок\n"
        "/order &lt;id&gt; — детали заявки\n"
        "/approve &lt;id&gt; — принять заявку\n"
        "/complete &lt;id&gt; — выполнить заявку\n"
        "/cancel &lt;id&gt; &lt;причина&gt; — отменить заявку\n\n"
        "💱 <b>Курсы</b>\n"
        "/rates — текущие курсы\n"
        "/setrate &lt;пара&gt; &lt;значение&gt; — установить курс вручную\n\n"
        "📊 <b>Статистика</b>\n"
        "/stats — статистика за день/неделю"
    )
    await message.answer(text, parse_mode="HTML")


# --------------------------------------------------------------------------
# /orders — list with pagination
# --------------------------------------------------------------------------
@router.message(Command("orders"))
async def cmd_orders(message: Message):
    await _show_orders_page(message, page=0)


async def _show_orders_page(event, page: int = 0, edit: bool = False):
    PAGE_SIZE = 5
    offset = page * PAGE_SIZE

    async with AsyncSessionLocal() as db:
        total_result = await db.execute(select(func.count(Order.id)))
        total = total_result.scalar() or 0

        result = await db.execute(
            select(Order)
            .order_by(Order.created_at.desc())
            .offset(offset)
            .limit(PAGE_SIZE)
        )
        orders = result.scalars().all()

    if not orders:
        text = "📭 Заявок пока нет."
        if isinstance(event, Message):
            await event.answer(text)
        else:
            await event.message.edit_text(text)
        return

    lines = [f"📋 <b>Заявки</b> (стр. {page + 1}, всего: {total})\n"]
    for o in orders:
        short_id = str(o.id)[:8].upper()
        direction_label = DIRECTION_LABELS.get(o.direction, o.direction)
        status_label = STATUS_LABELS.get(o.status.value, o.status.value)
        lines.append(
            f"• <code>{short_id}</code> | {direction_label} | "
            f"{float(o.amount_from):,.0f} | {status_label}"
        )

    text = "\n".join(lines)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀ Назад", callback_data=f"page:{page-1}"))
    if offset + PAGE_SIZE < total:
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ▶", callback_data=f"page:{page+1}"))

    kb = InlineKeyboardMarkup(inline_keyboard=[nav_buttons] if nav_buttons else [])

    if isinstance(event, Message):
        await event.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("page:"))
async def cb_page(callback: CallbackQuery):
    if not is_admin(callback):
        return
    page = int(callback.data.split(":")[1])
    await _show_orders_page(callback, page=page, edit=True)
    await callback.answer()


# --------------------------------------------------------------------------
# /order <id>
# --------------------------------------------------------------------------
@router.message(Command("order"))
async def cmd_order(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /order &lt;id&gt;", parse_mode="HTML")
        return

    order_id_str = parts[1].strip()
    order = await _find_order(order_id_str)
    if not order:
        await message.answer(f"❌ Заявка не найдена: {order_id_str}")
        return

    await message.answer(_order_card(order), parse_mode="HTML", reply_markup=_order_inline_kb(order))


async def _find_order(order_id_str: str) -> Order | None:
    """Find order by full UUID or short 8-char prefix."""
    async with AsyncSessionLocal() as db:
        # Try full UUID
        try:
            order_uuid = uuid.UUID(order_id_str)
            result = await db.execute(select(Order).where(Order.id == order_uuid))
            return result.scalar_one_or_none()
        except ValueError:
            pass

        # Try short ID (first 8 chars)
        if len(order_id_str) == 8:
            result = await db.execute(select(Order).order_by(Order.created_at.desc()).limit(200))
            orders = result.scalars().all()
            for o in orders:
                if str(o.id)[:8].upper() == order_id_str.upper():
                    return o

    return None


# --------------------------------------------------------------------------
# /approve <id>
# --------------------------------------------------------------------------
@router.message(Command("approve"))
async def cmd_approve(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /approve &lt;id&gt;", parse_mode="HTML")
        return
    await _approve_order(message, parts[1].strip())


@router.callback_query(F.data.startswith("approve:"))
async def cb_approve(callback: CallbackQuery):
    if not is_admin(callback):
        return
    order_id_str = callback.data.split(":", 1)[1]
    await _approve_order(callback, order_id_str)
    await callback.answer()


async def _approve_order(event, order_id_str: str):
    order = await _find_order(order_id_str)
    if not order:
        text = f"❌ Заявка не найдена: {order_id_str}"
        if isinstance(event, Message):
            await event.answer(text)
        else:
            await event.message.answer(text)
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Order).where(Order.id == order.id))
        order = result.scalar_one_or_none()
        if not order:
            return
        order.status = OrderStatus.approved

        # Create order on CXC
        try:
            from api.cryptoxchange import create_order as cxc_create
            cxc_result = await cxc_create(
                direction=order.direction,
                amount=float(order.amount_from),
                requisites=order.requisites,
                client_telegram_id=order.user_id,
            )
            cxc_id = cxc_result.get("order_id") or cxc_result.get("id")
            if cxc_id:
                order.cxc_order_id = str(cxc_id)
                logger.info("CXC order created: %s for order %s", cxc_id, order.id)
        except Exception as e:
            logger.error("Failed to create CXC order for %s: %s", order.id, e)

        await db.commit()
        await db.refresh(order)

    # Notify client
    try:
        from bot.handlers.client import notify_order_approved
        await notify_order_approved(order)
    except Exception as e:
        logger.error("Failed to send approval notification: %s", e)

    short_id = str(order.id)[:8].upper()
    text = f"✅ Заявка #{short_id} принята в работу."
    if order.cxc_order_id:
        text += f"\n🔗 CXC ID: {order.cxc_order_id}"

    if isinstance(event, Message):
        await event.answer(text)
    else:
        await event.message.answer(text)


# --------------------------------------------------------------------------
# In-progress callback
# --------------------------------------------------------------------------
@router.callback_query(F.data.startswith("inprogress:"))
async def cb_inprogress(callback: CallbackQuery):
    if not is_admin(callback):
        return
    order_id_str = callback.data.split(":", 1)[1]
    order = await _find_order(order_id_str)
    if not order:
        await callback.answer("Заявка не найдена")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Order).where(Order.id == order.id))
        order = result.scalar_one_or_none()
        if order:
            order.status = OrderStatus.in_progress
            await db.commit()
            await db.refresh(order)

    try:
        from bot.handlers.client import notify_order_in_progress
        await notify_order_in_progress(order)
    except Exception as e:
        logger.error("Failed to send in-progress notification: %s", e)

    short_id = str(order.id)[:8].upper()
    await callback.message.answer(f"🔄 Заявка #{short_id} переведена в статус 'В работе'.")
    await callback.answer()


# --------------------------------------------------------------------------
# /complete <id>
# --------------------------------------------------------------------------
@router.message(Command("complete"))
async def cmd_complete(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /complete &lt;id&gt;", parse_mode="HTML")
        return
    await _complete_order(message, parts[1].strip())


@router.callback_query(F.data.startswith("complete:"))
async def cb_complete(callback: CallbackQuery):
    if not is_admin(callback):
        return
    order_id_str = callback.data.split(":", 1)[1]
    await _complete_order(callback, order_id_str)
    await callback.answer()


async def _complete_order(event, order_id_str: str):
    order = await _find_order(order_id_str)
    if not order:
        text = f"❌ Заявка не найдена: {order_id_str}"
        if isinstance(event, Message):
            await event.answer(text)
        else:
            await event.message.answer(text)
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Order).where(Order.id == order.id))
        order = result.scalar_one_or_none()
        if order:
            order.status = OrderStatus.completed
            await db.commit()
            await db.refresh(order)

    try:
        from bot.handlers.client import notify_order_completed
        await notify_order_completed(order)
    except Exception as e:
        logger.error("Failed to send completion notification: %s", e)

    short_id = str(order.id)[:8].upper()
    text = f"✅ Заявка #{short_id} выполнена!"
    if isinstance(event, Message):
        await event.answer(text)
    else:
        await event.message.answer(text)


# --------------------------------------------------------------------------
# /cancel <id> <reason>
# --------------------------------------------------------------------------
@router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Использование: /cancel &lt;id&gt; [причина]", parse_mode="HTML")
        return
    order_id_str = parts[1].strip()
    reason = parts[2].strip() if len(parts) > 2 else ""
    await _cancel_order(message, order_id_str, reason)


@router.callback_query(F.data.startswith("cancel:"))
async def cb_cancel(callback: CallbackQuery):
    if not is_admin(callback):
        return
    order_id_str = callback.data.split(":", 1)[1]
    await _cancel_order(callback, order_id_str, "")
    await callback.answer()


async def _cancel_order(event, order_id_str: str, reason: str):
    order = await _find_order(order_id_str)
    if not order:
        text = f"❌ Заявка не найдена: {order_id_str}"
        if isinstance(event, Message):
            await event.answer(text)
        else:
            await event.message.answer(text)
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Order).where(Order.id == order.id))
        order = result.scalar_one_or_none()
        if order:
            order.status = OrderStatus.cancelled
            if reason:
                order.admin_note = reason
            await db.commit()
            await db.refresh(order)

    try:
        from bot.handlers.client import notify_order_cancelled
        await notify_order_cancelled(order, reason)
    except Exception as e:
        logger.error("Failed to send cancellation notification: %s", e)

    short_id = str(order.id)[:8].upper()
    text = f"❌ Заявка #{short_id} отменена."
    if reason:
        text += f"\nПричина: {reason}"
    if isinstance(event, Message):
        await event.answer(text)
    else:
        await event.message.answer(text)


# --------------------------------------------------------------------------
# /rates
# --------------------------------------------------------------------------
@router.message(Command("rates"))
async def cmd_rates(message: Message):
    try:
        base_rates = await get_rates()
    except Exception as e:
        await message.answer(f"❌ Ошибка получения курсов: {e}")
        return

    lines = ["💱 <b>Текущие курсы</b>\n"]
    lines.append("<b>Базовые (CXC):</b>")
    for pair, rate in base_rates.items():
        lines.append(f"  {pair}: {rate:.4f}")

    lines.append("\n<b>Наши (с комиссией 7%):</b>")
    for pair, rate in base_rates.items():
        buy = apply_buy_rate(rate)
        sell = apply_sell_rate(rate)
        lines.append(f"  {pair}: покупка {buy:.4f} / продажа {sell:.4f}")

    await message.answer("\n".join(lines), parse_mode="HTML")


# --------------------------------------------------------------------------
# /setrate <pair> <value>
# --------------------------------------------------------------------------
@router.message(Command("setrate"))
async def cmd_setrate(message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Использование: /setrate &lt;пара&gt; &lt;значение&gt;\nПример: /setrate USD_RUB 91.5", parse_mode="HTML")
        return

    pair = parts[1].upper()
    try:
        value = float(parts[2])
    except ValueError:
        await message.answer("❌ Неверное значение курса")
        return

    # Update rate cache in DB
    from database.models import RateCache
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(RateCache).where(RateCache.pair == pair))
        cache_entry = result.scalar_one_or_none()
        if cache_entry:
            cache_entry.rate = value
        else:
            cache_entry = RateCache(pair=pair, rate=value)
            db.add(cache_entry)
        await db.commit()

    # Also update in-memory cache
    from api.cryptoxchange import _rates_cache
    import time
    if _rates_cache["data"] is None:
        _rates_cache["data"] = {}
    _rates_cache["data"][pair] = value
    _rates_cache["expires_at"] = time.time() + 300

    buy = apply_buy_rate(value)
    sell = apply_sell_rate(value)
    await message.answer(
        f"✅ Курс {pair} обновлён: {value}\n"
        f"📈 Покупка: {buy} | 📉 Продажа: {sell}",
        parse_mode="HTML"
    )


# --------------------------------------------------------------------------
# /stats
# --------------------------------------------------------------------------
@router.message(Command("stats"))
async def cmd_stats(message: Message):
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(weeks=1)

    async with AsyncSessionLocal() as db:
        # Daily stats
        day_result = await db.execute(
            select(
                func.count(Order.id),
                func.sum(Order.amount_from),
                func.sum(Order.commission),
            ).where(Order.created_at >= day_ago)
        )
        day_count, day_volume, day_commission = day_result.one()

        # Weekly stats
        week_result = await db.execute(
            select(
                func.count(Order.id),
                func.sum(Order.amount_from),
                func.sum(Order.commission),
            ).where(Order.created_at >= week_ago)
        )
        week_count, week_volume, week_commission = week_result.one()

        # Status breakdown
        status_result = await db.execute(
            select(Order.status, func.count(Order.id))
            .group_by(Order.status)
        )
        status_counts = {row[0].value: row[1] for row in status_result.all()}

    text = (
        "📊 <b>Статистика CHM GOLD EXCHANGE</b>\n\n"
        f"<b>За сегодня (24ч):</b>\n"
        f"  📋 Заявок: {day_count or 0}\n"
        f"  💰 Объём: {float(day_volume or 0):,.2f}\n"
        f"  💸 Комиссия: {float(day_commission or 0):,.2f}\n\n"
        f"<b>За неделю (7д):</b>\n"
        f"  📋 Заявок: {week_count or 0}\n"
        f"  💰 Объём: {float(week_volume or 0):,.2f}\n"
        f"  💸 Комиссия: {float(week_commission or 0):,.2f}\n\n"
        f"<b>По статусам:</b>\n"
    )
    for status, label in [
        ("pending", "⏳ Ожидают"), ("approved", "✅ Приняты"),
        ("in_progress", "🔄 В работе"), ("completed", "✅ Выполнены"),
        ("cancelled", "❌ Отменены"),
    ]:
        count = status_counts.get(status, 0)
        text += f"  {label}: {count}\n"

    await message.answer(text, parse_mode="HTML")
