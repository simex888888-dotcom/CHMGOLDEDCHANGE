"""
APScheduler for auto-posting exchange rates to Telegram channel.
Posts at 10:00 and 20:00 MSK daily.
"""

import logging
import os
from datetime import datetime

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from api.commission import apply_buy_rate, apply_sell_rate
from api.cryptoxchange import get_rates

logger = logging.getLogger(__name__)

CHANNEL_ID = os.getenv("CHANNEL_ID", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")  # optional: @YourBot
MOSCOW_TZ = pytz.timezone("Europe/Moscow")


def _build_post_text(rates: dict, now: datetime) -> str:
    date_str = now.strftime("%d.%m.%Y")
    time_str = now.strftime("%H:%M")

    usd_base = rates.get("USD_RUB", 90.0)
    eur_base = rates.get("EUR_RUB", 98.0)
    usdt_base = rates.get("USDT_RUB", 90.5)

    usd_rub = apply_sell_rate(usd_base)
    eur_rub = apply_sell_rate(eur_base)
    usdt_buy = apply_buy_rate(usdt_base)   # Client buys USDT (pays RUB)
    usdt_sell = apply_sell_rate(usdt_base)  # Client sells USDT (gets RUB)

    text = (
        "📊 <b>АКТУАЛЬНЫЕ КУРСЫ ОБМЕНА</b>\n"
        "<b>CHM GOLD EXCHANGE</b>\n\n"
        f"📅 {date_str} | 🕐 {time_str} МСК\n"
        "Курс действителен до следующего обновления\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💵 <b>SWIFT-переводы (межбанковские)</b>\n"
        f"🇺🇸 USD → RUB: <b>{usd_rub:,.2f} ₽</b> за 1 USD\n"
        f"🇪🇺 EUR → RUB: <b>{eur_rub:,.2f} ₽</b> за 1 EUR\n"
        "• Мин. сумма: 1 000 USD/EUR\n"
        "• Срок: 1–3 рабочих дня\n"
        "• Комиссия: 7%\n"
        "• Документы: паспорт, ИНН, реквизиты счёта\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 <b>Обмен USDT ↔ RUB</b>\n"
        f"📈 Купить 1 USDT = <b>{usdt_buy:,.2f} ₽</b>\n"
        f"📉 Продать 1 USDT = <b>{usdt_sell:,.2f} ₽</b>\n"
        "• Мин. сумма: 100 USDT\n"
        "• Способ: карта РФ / наличные по договорённости\n"
        "• Срок: 15–60 минут после оплаты\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🪙 <b>Вывод на крипто-кошелёк</b>\n"
        "USDT (TRC-20 / ERC-20): комиссия 7%\n"
        "Мин. сумма: 500 USD\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💵 <b>Получение наличных RUB</b>\n"
        "• Сумма: 10 000 – 500 000 ₽\n"
        "• Комиссия: 7%\n"
        "• Напишите ваш город — сообщим курс, сумму, место и время\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ <b>Примечания</b>\n"
        "• Обновление курсов: 10:00 и 20:00 МСК\n"
        "• Крипто-операции — только после верификации аккаунта\n"
        "• Наличные — при наличии резерва в вашем городе\n"
        "• Комиссии могут меняться в зависимости от суммы\n\n"
        "🕐 Поддержка: 9:00–21:00 МСК, без выходных\n"
        "👇 Оставить заявку:"
    )
    return text


def _build_post_kb(bot_username: str = "") -> InlineKeyboardMarkup:
    url = f"https://t.me/{bot_username}" if bot_username else "https://t.me/"
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="💱 Обменять", url=url)
        ]]
    )


async def post_rates(bot: Bot) -> None:
    """Post current rates to the channel."""
    if not CHANNEL_ID:
        logger.warning("CHANNEL_ID not set, skipping rate post")
        return

    try:
        rates = await get_rates()
    except Exception as e:
        logger.error("Failed to get rates for scheduled post: %s", e)
        return

    now = datetime.now(MOSCOW_TZ)
    text = _build_post_text(rates, now)
    kb = _build_post_kb(BOT_USERNAME)

    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode="HTML",
            reply_markup=kb,
        )
        logger.info("Rate post sent to channel %s at %s", CHANNEL_ID, now.strftime("%Y-%m-%d %H:%M"))
    except Exception as e:
        logger.error("Failed to send rate post to channel %s: %s", CHANNEL_ID, e)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Configure and return the scheduler."""
    scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)

    # Post at 10:00 MSK
    scheduler.add_job(
        post_rates,
        trigger="cron",
        hour=10,
        minute=0,
        args=[bot],
        id="post_rates_morning",
        replace_existing=True,
    )

    # Post at 20:00 MSK
    scheduler.add_job(
        post_rates,
        trigger="cron",
        hour=20,
        minute=0,
        args=[bot],
        id="post_rates_evening",
        replace_existing=True,
    )

    logger.info("Scheduler configured: posts at 10:00 and 20:00 MSK")
    return scheduler
