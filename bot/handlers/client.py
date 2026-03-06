"""
Client notification handlers for CHM GOLD EXCHANGE bot.
"""

import logging
import os

logger = logging.getLogger(__name__)

DIRECTION_LABELS = {
    "USD_RUB": "USD → RUB (SWIFT)",
    "EUR_RUB": "EUR → RUB (SWIFT)",
    "USDT_RUB": "USDT → RUB",
    "RUB_USDT": "RUB → USDT",
    "CASH_RUB": "Наличные RUB",
}

CURRENCY_LABELS = {
    "USD_RUB": ("USD", "RUB"),
    "EUR_RUB": ("EUR", "RUB"),
    "USDT_RUB": ("USDT", "RUB"),
    "RUB_USDT": ("RUB", "USDT"),
    "CASH_RUB": ("USD", "RUB"),
}


def _get_bot():
    """Lazy-import bot instance to avoid circular imports."""
    try:
        from bot.main import bot
        return bot
    except Exception:
        return None


async def notify_order_created(order) -> None:
    """Send order confirmation to client."""
    bot = _get_bot()
    if not bot:
        logger.warning("Bot not available, skipping client notification for order %s", order.id)
        return

    direction_label = DIRECTION_LABELS.get(order.direction, order.direction)
    from_curr, to_curr = CURRENCY_LABELS.get(order.direction, ("?", "?"))
    short_id = str(order.id)[:8].upper()

    text = (
        f"✅ <b>Заявка #{short_id} принята!</b>\n\n"
        f"💱 {direction_label}\n"
        f"💰 Вы отдаёте: <b>{float(order.amount_from):,.2f} {from_curr}</b>\n"
        f"💵 Вы получаете: <b>{float(order.amount_to):,.2f} {to_curr}</b>\n"
        f"📊 Курс: <b>{float(order.our_rate):.2f}</b> (включая комиссию 7%)\n"
        f"📋 Реквизиты: <code>{order.requisites}</code>\n"
    )
    if order.city:
        text += f"🏙 Город: {order.city}\n"

    text += (
        "\n⏳ <b>Статус:</b> Ожидает подтверждения\n\n"
        "Наш менеджер свяжется с вами в рабочее время:\n"
        "🕐 9:00–21:00 МСК, без выходных"
    )

    try:
        await bot.send_message(order.user_id, text, parse_mode="HTML")
        logger.info("Order creation notification sent to user %s for order %s", order.user_id, order.id)
    except Exception as e:
        logger.error("Failed to send order creation notification to user %s: %s", order.user_id, e)


async def notify_order_approved(order) -> None:
    """Notify client that order was approved."""
    bot = _get_bot()
    if not bot:
        return

    direction_label = DIRECTION_LABELS.get(order.direction, order.direction)
    from_curr, to_curr = CURRENCY_LABELS.get(order.direction, ("?", "?"))
    short_id = str(order.id)[:8].upper()

    text = (
        f"✅ <b>Заявка #{short_id} подтверждена!</b>\n\n"
        f"💱 {direction_label}\n"
        f"💰 Сумма: <b>{float(order.amount_from):,.2f} {from_curr}</b>\n"
        f"💵 К получению: <b>{float(order.amount_to):,.2f} {to_curr}</b>\n\n"
        f"🔄 <b>Статус:</b> Подтверждена\n\n"
        "Ваша заявка принята в работу. Ожидайте выполнения.\n"
        "🕐 Время обработки: 15 минут – 3 рабочих дня в зависимости от типа операции."
    )
    if order.admin_note:
        text += f"\n\n📝 Комментарий: {order.admin_note}"

    try:
        await bot.send_message(order.user_id, text, parse_mode="HTML")
        logger.info("Approval notification sent to user %s for order %s", order.user_id, order.id)
    except Exception as e:
        logger.error("Failed to send approval notification to user %s: %s", order.user_id, e)


async def notify_order_in_progress(order) -> None:
    """Notify client that order is being processed."""
    bot = _get_bot()
    if not bot:
        return

    short_id = str(order.id)[:8].upper()
    direction_label = DIRECTION_LABELS.get(order.direction, order.direction)

    text = (
        f"🔄 <b>Заявка #{short_id} в обработке!</b>\n\n"
        f"💱 {direction_label}\n\n"
        "Ваша операция выполняется прямо сейчас. Мы уведомим вас о завершении."
    )

    try:
        await bot.send_message(order.user_id, text, parse_mode="HTML")
        logger.info("In-progress notification sent to user %s for order %s", order.user_id, order.id)
    except Exception as e:
        logger.error("Failed to send in-progress notification to user %s: %s", order.user_id, e)


async def notify_order_completed(order) -> None:
    """Notify client that order is completed."""
    bot = _get_bot()
    if not bot:
        return

    direction_label = DIRECTION_LABELS.get(order.direction, order.direction)
    from_curr, to_curr = CURRENCY_LABELS.get(order.direction, ("?", "?"))
    short_id = str(order.id)[:8].upper()

    text = (
        f"🎉 <b>Заявка #{short_id} выполнена!</b>\n\n"
        f"💱 {direction_label}\n"
        f"💵 Вы получили: <b>{float(order.amount_to):,.2f} {to_curr}</b>\n\n"
        "✅ Операция успешно завершена. Спасибо за доверие к CHM GOLD EXCHANGE!\n\n"
        "💬 Если у вас есть вопросы — напишите нам."
    )
    if order.admin_note:
        text += f"\n\n📝 Комментарий: {order.admin_note}"

    try:
        await bot.send_message(order.user_id, text, parse_mode="HTML")
        logger.info("Completion notification sent to user %s for order %s", order.user_id, order.id)
    except Exception as e:
        logger.error("Failed to send completion notification to user %s: %s", order.user_id, e)


async def notify_order_cancelled(order, reason: str = "") -> None:
    """Notify client that order was cancelled."""
    bot = _get_bot()
    if not bot:
        return

    direction_label = DIRECTION_LABELS.get(order.direction, order.direction)
    short_id = str(order.id)[:8].upper()

    text = (
        f"❌ <b>Заявка #{short_id} отменена</b>\n\n"
        f"💱 {direction_label}\n\n"
        "К сожалению, ваша заявка была отменена."
    )
    if reason:
        text += f"\n\n📝 Причина: {reason}"

    text += (
        "\n\n💬 Если у вас есть вопросы или вы хотите повторить заявку — "
        "свяжитесь с нашим менеджером."
    )

    try:
        await bot.send_message(order.user_id, text, parse_mode="HTML")
        logger.info("Cancellation notification sent to user %s for order %s", order.user_id, order.id)
    except Exception as e:
        logger.error("Failed to send cancellation notification to user %s: %s", order.user_id, e)
