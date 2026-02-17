import asyncio
import os
import requests

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    FSInputFile,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder

from PIL import Image, ImageDraw, ImageFont

from configs.fonts import FONTS
from configs.layout import LAYOUT, BYBIT_CUSTOM_LAYOUT
from utils.draw_text import draw_text

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# =====================================================
# FSM
# =====================================================

class CustomExchange(StatesGroup):
    username = State()
    side = State()
    symbol = State()
    entry = State()
    exit_price = State()
    leverage = State()
    referral = State()      # реферальный код
    datetime_str = State()  # дата и время


class TradeForm(StatesGroup):
    exchange = State()
    symbol = State()
    side = State()
    entry = State()
    mark = State()
    amount = State()
    deposit = State()
    leverage = State()


BASE_H = 467


def scale_font(size: int, img_h: int) -> int:
    return max(10, int(size * img_h / BASE_H))


def px(val: float, size: int) -> int:
    return int(val * size)


# =====================================================
# BOT
# =====================================================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = Bot(token=TOKEN, timeout=60)
dp = Dispatcher(storage=MemoryStorage())

# =====================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =====================================================

async def safe_delete_message(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass


async def parse_float(message: Message) -> float | None:
    try:
        return float(message.text.replace(",", "."))
    except (ValueError, AttributeError):
        await message.answer("Введите число 🙏")
        return None


# =====================================================
# КЛАВИАТУРЫ
# =====================================================

restart_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔁 В начало", callback_data="restart")]
    ]
)

exchange_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⚫ Bybit", callback_data="exchange_bybit"),
            InlineKeyboardButton(text="🔵 BingX", callback_data="exchange_bingx"),
        ]
    ]
)

side_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="📈 Long", callback_data="side_long"),
            InlineKeyboardButton(text="📉 Short", callback_data="side_short"),
        ]
    ]
)

back_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ]
)

mark_price_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📡 Взять цену с биржи", callback_data="get_mark_price")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")],
    ]
)

skip_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_field")]
    ]
)


# =====================================================
# START / TEST
# =====================================================

@dp.message(Command("start"))
async def start(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Bybit", callback_data="exchange_bybit")
    kb.button(text="📊 BingX", callback_data="exchange_bingx")
    kb.button(text="🎨 Кастом Bybit", callback_data="custom_bybit")
    kb.button(text="🎨 Кастом BingX", callback_data="custom_bingx")
    kb.adjust(1)
    await message.answer("Выбери режим:", reply_markup=kb.as_markup())


@dp.message(Command("test_bybit"))
async def test_bybit(message: Message):
    exchange = "bybit"
    amount = 100
    entry = 42000
    mark = 43250
    leverage = 20

    qty = calculate_qty(exchange, amount, entry, leverage)
    cost = calculate_cost(exchange, amount, leverage)
    side = "long"
    percent, pnl = calculate_pnl(entry, mark, side, leverage)
    pnl_usdt = round(cost * pnl / 100, 2)

    fake_data = {
        "exchange": exchange,
        "symbol": "BTCUSDT",
        "side": "long",
        "entry": entry,
        "mark": mark,
        "amount": amount,
        "deposit": 5000,
        "leverage": leverage,
        "qty": qty,
        "liquidation": calculate_liquidation(entry, leverage, "long"),
        "cost": cost,
    }

    path = generate_trade_image(fake_data, percent, pnl, pnl_usdt)
    await message.answer_photo(FSInputFile(path))


@dp.message(Command("test_bingx"))
async def test_bingx(message: Message):
    exchange = "bingx"
    amount = 100
    entry = 42000
    mark = 43250
    leverage = 20
    side = "long"

    qty = calculate_qty(exchange, amount, entry, leverage)
    cost = calculate_cost(exchange, amount, leverage)

    pnl_usdt, margin_pos, percent = calculate_pnl_linear(
        entry,
        mark,
        qty,
        side,
        leverage,
    )
    pnl = percent

    liquidation = calculate_liquidation(entry, leverage, side)

    fake_data = {
        "exchange": exchange,
        "symbol": "BTCUSDT",
        "side": side,
        "entry": entry,
        "mark": mark,
        "amount": amount,
        "deposit": 5000,
        "leverage": leverage,
        "qty": qty,
        "liquidation": liquidation,
        "cost": cost,
    }

    path = generate_trade_image(fake_data, percent, pnl, pnl_usdt)
    await message.answer_photo(FSInputFile(path))


@dp.message(Command("test_bybit_custom"))
async def test_bybit_custom(message: Message):
    entry = 0.1068
    exit_price = 0.1092
    leverage_str = "50x"
    side = "long"
    leverage = float(leverage_str.replace("x", ""))

    if side == "long":
        pnl_percent = ((exit_price - entry) / entry * 100) * leverage
    else:
        pnl_percent = ((entry - exit_price) / entry * 100) * leverage

    image_data = {
        "username": "ТЕСТ ПОЛЬЗОВАТЕЛЬ",
        "symbol": "WLF IUSDT",
        "pnl": round(pnl_percent, 2),
        "entry": entry,
        "exit": exit_price,
        "leverage": leverage_str,
        "side": side,
        "referral": "D1BFA4",
        "datetime_str": "02/14 19:00",
    }

    path = generate_custom_bybit_image(image_data)
    await message.answer_photo(FSInputFile(path))


@dp.message(Command("test_bingx_custom"))
async def test_bingx_custom(message: Message):
    entry = 0.1068
    exit_price = 0.1092
    leverage_str = "50x"
    side = "long"
    leverage = float(leverage_str.replace("x", ""))

    if side == "long":
        pnl_percent = ((exit_price - entry) / entry * 100) * leverage
    else:
        pnl_percent = ((entry - exit_price) / entry * 100) * leverage

    image_data = {
        "username": "ТЕСТ ПОЛЬЗОВАТЕЛЬ",
        "symbol": "WLFIUSDT",
        "pnl": round(pnl_percent, 2),
        "entry": entry,
        "exit": exit_price,
        "leverage": leverage_str,
        "side": side,
        "referral": "D1BFA4",
        "datetime_str": "02/14 19:00",
    }

    path = generate_custom_bingx_image(image_data)
    await message.answer_photo(FSInputFile(path))


@dp.message(Command("test_all"))
async def test_all(message: Message):
    text = (
        "Тестовые команды:\n"
        "/test_bybit_long\n"
        "/test_bybit_short\n"
        "/test_bingx_long\n"
        "/test_bingx_short\n"
        "/test_custom_bybit_long\n"
        "/test_custom_bybit_short\n"
        "/test_custom_bingx_long\n"
        "/test_custom_bingx_short\n"
    )
    await message.answer(text)


# ===== Обычный Bybit =====

@dp.message(Command("test_bybit_long"))
async def test_bybit_long(message: Message):
    await _run_spot_test(message, exchange="bybit", side="long")


@dp.message(Command("test_bybit_short"))
async def test_bybit_short(message: Message):
    await _run_spot_test(message, exchange="bybit", side="short")


# ===== Обычный BingX =====

@dp.message(Command("test_bingx_long"))
async def test_bingx_long(message: Message):
    await _run_spot_test(message, exchange="bingx", side="long")


@dp.message(Command("test_bingx_short"))
async def test_bingx_short(message: Message):
    await _run_spot_test(message, exchange="bingx", side="short")


async def _run_spot_test(message: Message, exchange: str, side: str):
    amount = 100
    entry = 42000
    mark = 43250 if side == "long" else 41000
    leverage = 20

    qty = calculate_qty(exchange, amount, entry, leverage)
    cost = calculate_cost(exchange, amount, leverage)
    pnl_usdt, margin_pos, percent = calculate_pnl_linear(
        entry,
        mark,
        qty,
        side,
        leverage,
    )
    pnl = percent

    liquidation = calculate_liquidation(entry, leverage, side)

    data = {
        "exchange": exchange,
        "symbol": "PYTHUSDT",
        "side": side,
        "entry": entry,
        "mark": mark,
        "amount": amount,
        "deposit": 50,
        "leverage": leverage,
        "qty": qty,
        "liquidation": liquidation,
        "cost": cost,
    }

    path = generate_trade_image(data, percent, pnl, pnl_usdt)
    await message.answer_photo(FSInputFile(path))


# ===== Кастом Bybit =====

@dp.message(Command("test_custom_bybit_long"))
async def test_custom_bybit_long(message: Message):
    await _run_custom_test(message, exchange="bybit", side="long")


@dp.message(Command("test_custom_bybit_short"))
async def test_custom_bybit_short(message: Message):
    await _run_custom_test(message, exchange="bybit", side="short")


# ===== Кастом BingX =====

@dp.message(Command("test_custom_bingx_long"))
async def test_custom_bingx_long(message: Message):
    await _run_custom_test(message, exchange="bingx", side="long")


@dp.message(Command("test_custom_bingx_short"))
async def test_custom_bingx_short(message: Message):
    await _run_custom_test(message, exchange="bingx", side="short")


async def _run_custom_test(message: Message, exchange: str, side: str):
    entry = 0.1068
    exit_price = 0.1092 if side == "long" else 0.1040
    leverage_str = "50x"
    leverage = float(leverage_str.replace("x", ""))

    if side == "long":
        pnl_percent = ((exit_price - entry) / entry * 100) * leverage
    else:
        pnl_percent = ((entry - exit_price) / entry * 100) * leverage

    image_data = {
        "username": "ТЕСТ ПОЛЬЗОВАТЕЛЬ",
        "symbol": "PYTHUSDT",
        "pnl": round(pnl_percent, 2),
        "entry": entry,
        "exit": exit_price,
        "leverage": leverage_str,
        "side": side,
        "referral": "D1BFA4",
        "datetime_str": "02/14 19:00",
    }

    if exchange == "bingx":
        path = generate_custom_bingx_image(image_data)
    else:
        path = generate_custom_bybit_image(image_data)

    await message.answer_photo(FSInputFile(path))


# =====================================================
# НАВИГАЦИЯ TRADEFORM
# =====================================================

@dp.callback_query(lambda c: c.data == "restart")
async def restart(call: CallbackQuery, state: FSMContext):
    await state.clear()

    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Bybit", callback_data="exchange_bybit")
    kb.button(text="📊 BingX", callback_data="exchange_bingx")
    kb.button(text="🎨 Кастом Bybit", callback_data="custom_bybit")
    kb.button(text="🎨 Кастом BingX", callback_data="custom_bingx")
    kb.adjust(1)

    await call.message.answer("Выбери режим:", reply_markup=kb.as_markup())
    await call.answer()


@dp.callback_query(lambda c: c.data == "back")
async def go_back(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prev = data.get("prev_state")

    steps = {
        TradeForm.symbol: ("Введи монету (например BTCUSDT)", TradeForm.symbol, None),
        TradeForm.side: ("Выбери направление 👇", TradeForm.side, side_kb),
        TradeForm.entry: ("Введите цену входа:", TradeForm.entry, back_kb),
        TradeForm.mark: ("Введите цену маркировки:", TradeForm.mark, mark_price_kb),
        TradeForm.amount: ("На какую сумму заходишь? (USDT)", TradeForm.amount, back_kb),
        TradeForm.deposit: ("Какой депозит? (USDT)", TradeForm.deposit, back_kb),
        TradeForm.leverage: ("Введите плечо (например 10)", TradeForm.leverage, back_kb),
    }

    if prev in steps:
        text, st, kb = steps[prev]
        await show_step(call.message, state, text, kb)
        await state.set_state(st)

    await call.answer()


@dp.callback_query(lambda c: c.data.startswith("exchange_"))
async def exchange_selected(call: CallbackQuery, state: FSMContext):
    await state.update_data(
        exchange=call.data.split("_")[1],
        prev_state=TradeForm.exchange,
    )
    await show_step(call.message, state, "Введи монету (например BTCUSDT)")
    await state.set_state(TradeForm.symbol)
    await call.answer()


@dp.message(TradeForm.symbol)
async def get_symbol(message: Message, state: FSMContext):
    symbol = message.text.upper()
    data = await state.get_data()
    exchange = data.get("exchange")
    precision = get_price_precision(exchange, symbol)

    await state.update_data(
        symbol=symbol,
        price_precision=precision,
        prev_state=TradeForm.symbol,
    )
    await safe_delete_message(message)
    await show_step(message, state, "Выбери направление 👇", side_kb)
    await state.set_state(TradeForm.side)


@dp.callback_query(TradeForm.side, lambda c: c.data in ("side_long", "side_short"))
async def side_selected(call: CallbackQuery, state: FSMContext):
    side = "long" if call.data == "side_long" else "short"
    await state.update_data(side=side, prev_state=TradeForm.side)
    await show_step(call.message, state, "Введите цену входа:", back_kb)
    await state.set_state(TradeForm.entry)
    await call.answer()


@dp.message(TradeForm.entry)
async def get_entry(message: Message, state: FSMContext):
    value = await parse_float(message)
    if value is None:
        return
    await state.update_data(entry=value, prev_state=TradeForm.entry)
    await safe_delete_message(message)
    await show_step(message, state, "Введите цену маркировки:", mark_price_kb)
    await state.set_state(TradeForm.mark)


@dp.message(TradeForm.mark)
async def get_mark(message: Message, state: FSMContext):
    value = await parse_float(message)
    if value is None:
        return
    await state.update_data(mark=value, prev_state=TradeForm.mark)
    await safe_delete_message(message)
    await show_step(message, state, "На какую сумму заходишь? (USDT)", back_kb)
    await state.set_state(TradeForm.amount)


@dp.message(TradeForm.amount)
async def get_amount(message: Message, state: FSMContext):
    value = await parse_float(message)
    if value is None:
        return
    await state.update_data(amount=value, prev_state=TradeForm.amount)
    await safe_delete_message(message)
    await show_step(message, state, "Какой депозит? (USDT)", back_kb)
    await state.set_state(TradeForm.deposit)


@dp.message(TradeForm.deposit)
async def get_deposit(message: Message, state: FSMContext):
    value = await parse_float(message)
    if value is None:
        return
    await state.update_data(deposit=value, prev_state=TradeForm.deposit)
    await safe_delete_message(message)
    await show_step(message, state, "Введите плечо (например 10)", back_kb)
    await state.set_state(TradeForm.leverage)


@dp.message(TradeForm.leverage)
async def get_leverage(message: Message, state: FSMContext):
    try:
        leverage = int(message.text)
        if leverage <= 0 or leverage > 125:
            raise ValueError
    except ValueError:
        await message.answer("Введите число от 1 до 125")
        return

    await safe_delete_message(message)
    data = await state.get_data()

    qty = calculate_qty(
        data["exchange"],
        data["amount"],
        data["entry"],
        leverage,
    )
    cost = calculate_cost(
        data["exchange"],
        data["amount"],
        leverage,
    )
    pnl_usdt, margin_pos, percent = calculate_pnl_linear(
        data["entry"],
        data["mark"],
        qty,
        data["side"],
        leverage,
    )
    pnl = percent

    liquidation = calculate_liquidation(data["entry"], leverage, data["side"])

    data.update(
        {
            "leverage": leverage,
            "qty": qty,
            "liquidation": liquidation,
            "cost": cost,
        }
    )

    path = generate_trade_image(data, percent, pnl, pnl_usdt)
    await message.answer_photo(FSInputFile(path), reply_markup=restart_kb)
    await state.clear()


# =====================================================
# API: цены и точность
# =====================================================

def get_mark_price(exchange: str, symbol: str) -> float | None:
    try:
        if exchange == "bybit":
            url = "https://api.bybit.com/v5/market/tickers"
            params = {"category": "linear", "symbol": symbol}
            r = requests.get(url, params=params, timeout=5).json()
            return float(r["result"]["list"][0]["markPrice"])

        if exchange == "bingx":
            if "-" not in symbol:
                symbol = symbol.replace("USDT", "-USDT")
            url = "https://open-api.bingx.com/openApi/swap/v2/quote/price"
            params = {"symbol": symbol}
            r = requests.get(url, params=params, timeout=5).json()
            return float(r["data"]["price"])
    except Exception as e:
        print("MARK PRICE ERROR:", e)
    return None


def get_bybit_precision(symbol: str) -> int:
    url = "https://api.bybit.com/v5/market/instruments-info"
    params = {"category": "linear", "symbol": symbol}
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    info = data["result"]["list"][0]
    tick = info["priceFilter"]["tickSize"]
    if "." in tick:
        return len(tick.split(".")[1].rstrip("0"))
    return 0


def get_bingx_precision(symbol: str) -> int:
    url = "https://open-api.bingx.com/openApi/swap/v2/quote/contracts"
    r = requests.get(url, timeout=5).json()
    for item in r["data"]:
        if item["symbol"] == symbol:
            return int(item["pricePrecision"])
    return 2


def get_price_precision(exchange: str, symbol: str) -> int | None:
    try:
        if exchange == "bybit":
            return get_bybit_precision(symbol)
        if exchange == "bingx":
            return get_bingx_precision(symbol)
    except Exception as e:
        print("PRECISION ERROR:", e)
    return None


# =====================================================
# КНОПКА: взять цену с биржи
# =====================================================

@dp.callback_query(lambda c: c.data == "get_mark_price")
async def get_mark_from_exchange(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    exchange = data.get("exchange")
    symbol = data.get("symbol")

    if not exchange or not symbol:
        await call.answer("Нет данных", show_alert=True)
        return

    price = get_mark_price(exchange, symbol)
    if price is None:
        await call.answer("Не удалось получить цену", show_alert=True)
        return

    await state.update_data(mark=price, prev_state=TradeForm.mark)

    try:
        await call.message.delete()
    except Exception:
        pass

    await show_step(
        call.message,
        state,
        "На какую сумму заходишь? (USDT)",
        back_kb,
    )
    await state.set_state(TradeForm.amount)
    await call.answer("Цена получена ✅")


# =====================================================
# РАСЧЁТЫ
# =====================================================

def calculate_qty(exchange: str, amount: float, entry: float, leverage: int | float) -> float:
    return round((amount * leverage) / entry, 4)


def calculate_liquidation(entry: float, leverage: int | float, side: str, mm: float = 0.005) -> float:
    if side == "long":
        return entry * (1 - 1 / leverage + mm)
    else:
        return entry * (1 + 1 / leverage - mm)


def calculate_cost(exchange: str, amount: float, leverage: int | float) -> float:
    return round(amount * leverage, 2)


def calculate_pnl_linear(
    entry: float,
    mark: float,
    qty: float,
    side: str,
    leverage: float,
) -> tuple[float, float, float]:
    if side not in ("long", "short"):
        raise ValueError("side must be 'long' or 'short'")

    if side == "long":
        pnl_usd = qty * (mark - entry)
    else:
        pnl_usd = qty * (entry - mark)

    margin = entry * qty / leverage if leverage else 0.0
    pnl_percent = (pnl_usd / margin * 100) if margin > 0 else 0.0

    return round(pnl_usd, 4), round(margin, 4), round(pnl_percent, 2)


def calculate_pnl(entry: float, mark: float, side: str, leverage: float) -> tuple[float, float]:
    pnl_usd, margin, pnl_percent = calculate_pnl_linear(entry, mark, 1.0, side, leverage)
    return pnl_percent, pnl_usd


# =====================================================
# SUMMARY / show_step
# =====================================================

def build_summary( dict) -> str:
    text = "📊 Уже введено:\n"
    if "exchange" in 
        text += f"🏦 Биржа: {data['exchange'].title()}\n"
    if "symbol" in 
        text += f"🪙 Монета: {data['symbol']}\n"
    if "side" in 
        text += f"📈 Направление: {'Лонг' if data['side'] == 'long' else 'Шорт'}\n"
    if "entry" in 
        text += f"🎯 Вход: {data['entry']}\n"
    if "mark" in 
        text += f"📍 Марк: {data['mark']}\n"
    if "amount" in 
        text += f"💰 Сумма: {data['amount']} USDT\n"
    if "deposit" in 
        text += f"🏦 Депозит: {data['deposit']} USDT\n"
    return text


def build_custom_summary( dict) -> str:
    exchange = (data or {}).get("exchange", "bybit").title()
    text = f"📊 КАСТОМ {exchange}\n\n"
    if not 
        return text

    if "username" in 
        text += f"👤 {data['username']}\n"
    if "symbol" in 
        text += f"🪙 {data['symbol']}\n"
    if "side" in 
        side_emoji = "📈" if data["side"] == "long" else "📉"
        text += f"{side_emoji} {'Лонг' if data['side'] == 'long' else 'Шорт'}\n"
    if "entry" in 
        text += f"💰 Вход: {data['entry']}\n"
    if "exit" in 
        text += f"🚪 Выход: {data['exit']}\n"
    if "leverage" in 
        text += f"⚙️ {data['leverage']}\n"
    if "referral" in 
        text += f"👥 Рефкод: {data['referral']}\n"
    if "datetime_str" in 
        text += f"🕒 {data['datetime_str']}\n"
    return text


async def show_step(
    message: Message,
    state: FSMContext,
    question: str,
    keyboard: InlineKeyboardMarkup | None = None,
):
    data = await state.get_data()

    if "username" in data and data.get("exchange") in ("bybit", "bingx"):
        summary = build_custom_summary(data)
    else:
        summary = build_summary(data)

    pretty_questions = {
        "Введи монету (например BTCUSDT)": "🪙 Введите монету:",
        "Выбери направление 👇": "📈 Направление сделки:",
        "Введите цену входа:": "💰 Цена входа:",
        "Введите цену маркировки:": "📍 Цена сейчас:",
        "На какую сумму заходишь? (USDT)": "💵 Сумма (USDT):",
        "Какой депозит? (USDT)": "🏦 Депозит (USDT):",
        "Введите плечо (например 10)": "⚙️ Плечо:",
    }

    question_text = pretty_questions.get(question, f"❓ {question}")

    last_msg_id = data.get("last_bot_msg_id") or data.get("custom_last_msg_id")
    if last_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, last_msg_id)
        except Exception:
            pass

    msg = await message.answer(
        f"{summary}\n{question_text}",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    await state.update_data(last_bot_msg_id=msg.message_id, custom_last_msg_id=msg.message_id)


# =====================================================
# РЕНДЕР ОБЫЧНОЙ КАРТИНКИ
# =====================================================

def draw_gray_box(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    cfg: dict,
):
    padding_x = cfg.get("pad_x", 16)
    padding_y = cfg.get("pad_y", 10)
    radius = cfg.get("radius", 14)

    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    x1 = x - w // 2 - padding_x
    y1 = y - h // 2 - padding_y
    x2 = x + w // 2 + padding_x
    y2 = y + h // 2 + padding_y

    draw.rounded_rectangle(
        (x1, y1, x2, y2),
        radius=radius,
        fill=(80, 80, 80),
    )
    draw.text((x, y), text, fill=(255, 255, 255), font=font, anchor="mm")


def draw_side_badge(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    color: tuple[int, int, int],
    exchange: str,
    fonts_cfg: dict,
    cfg: dict | None = None,
):
    img_h = draw.im.size[1]
    badge_size = fonts_cfg["sizes"]["badge"]
    badge_style = fonts_cfg.get("badge_style", "outline")

    font = ImageFont.truetype(
        os.path.join(BASE_DIR, fonts_cfg["files"]["regular"]),
        scale_font(badge_size, img_h),
    )

    if exchange == "bingx" and cfg is not None:
        box_w = cfg.get("w", 140)
        box_h = cfg.get("h", 48)
        radius = cfg.get("radius", 18)
        text_offset_y = fonts_cfg["sizes"].get("badge_text_offset_y", 0)
    else:
        padding_x = 16
        padding_y = 18
        radius = 20
        text_offset_y = 0

        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        box_w = text_w + padding_x * 2
        box_h = text_h + padding_y * 1.5

    x1 = x - box_w // 2
    y1 = y - box_h // 2
    x2 = x1 + box_w
    y2 = y1 + box_h

    if badge_style == "filled":
        fill_color = color
        text_color = (255, 255, 255)
    else:
        fill_color = (30, 30, 30)
        text_color = color

    draw.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=fill_color)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    text_x = x1 + (box_w - text_w) / 2
    text_y = y1 + (box_h - text_h) / 15 + text_offset_y
    draw.text((text_x, text_y), text, fill=text_color, font=font)


def clear_by_layout(img: Image.Image, draw: ImageDraw.ImageDraw, layout: dict, key: str):
    cfg = layout.get(key)
    if cfg is None:
        return

    w, h = img.size
    x = px(cfg["x"], w)
    y = px(cfg["y"], h)
    cw = px(cfg["w"], w)
    ch = px(cfg["h"], h)

    if "bg_x" in cfg and "bg_y" in cfg:
        bgx = px(cfg["bg_x"], w)
        bgy = px(cfg["bg_y"], h)
        bg = img.getpixel((bgx, bgy))
    else:
        bg = img.getpixel((x + 2, y + 2))

    draw.rectangle((x, y, x + cw, y + ch), fill=bg)


def draw_bingx_icon(
    img: Image.Image,
    symbol: str,
    layout: dict,
    font: ImageFont.FreeTypeFont,
    w: int,
    h: int,
):
    cfg = layout.get("symbol_icon")
    if not cfg:
        return

    icon_path = os.path.join(BASE_DIR, "assets", "bingx", "icon.png")
    if not os.path.exists(icon_path):
        return

    icon = Image.open(icon_path).convert("RGBA")
    size = int(cfg.get("size", 24))
    icon = icon.resize((size, size), Image.LANCZOS)

    x = int(cfg["x"] * w) + cfg.get("dx", 0)
    y = int(cfg["y"] * h) + cfg.get("dy", 0)

    dummy = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(dummy)
    bbox = d.textbbox((0, 0), symbol, font=font)
    text_width = bbox[2] - bbox[0]

    gap = cfg.get("gap", 8)
    x += text_width + gap

    img.paste(icon, (x, y), icon)


def generate_trade_image( dict, percent: float, pnl: float, pnl_usdt: float) -> str:
    template_path = os.path.join(BASE_DIR, "assets", data["exchange"], "template.png")
    output_path = os.path.join(BASE_DIR, "output", "result.png")

    cfg = FONTS[data["exchange"]]
    layout = LAYOUT[data["exchange"]]
    font_regular = os.path.join(BASE_DIR, cfg["files"]["regular"])
    font_bold = os.path.join(BASE_DIR, cfg["files"]["bold"])
    sizes = cfg["sizes"]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    img = Image.open(template_path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    clear_keys = [
        "clear_symbol",
        "clear_leverage",
        "clear_side_badge",
        "clear_entry",
        "clear_mark",
        "clear_pnl",
        "clear_qty",
        "clear_liq",
        "clear_margin",
        "clear_risk",
    ]

    for key in clear_keys:
        if data["exchange"] == "bybit" and key == "clear_margin":
            continue
        clear_by_layout(img, draw, layout, key)

    WHITE = (255, 255, 255)
    GREEN = (0, 200, 120)
    RED = (230, 60, 60)
    ORANGE = (245, 166, 89)

    side_color = GREEN if data["side"] == "long" else RED
    pnl_color = GREEN if pnl >= 0 else RED

    symbol_font = ImageFont.truetype(font_bold, sizes["symbol"])
    pnl_font = ImageFont.truetype(font_bold, sizes["pnl"])
    lev_font = ImageFont.truetype(font_regular, sizes["leverage"])

    w, h = img.size

    if data["exchange"] == "bingx":
        draw_bingx_icon(img, data["symbol"], layout, symbol_font, w, h)

    def pos(c: dict) -> tuple[int, int]:
        return (
            int(c["x"] * w) + c.get("dx", 0),
            int(c["y"] * h) + c.get("dy", 0),
        )

    symbol_text = data["symbol"]
    badge_text = "Лонг" if data["side"] == "long" else "Шорт"
    pnl_text = f"{pnl_usdt:+.2f}$ ({pnl:+.2f}%)"
    if data["exchange"] == "bybit":
        lev_text = f"Кросс {data['leverage']}x"
    else:
        lev_text = ""

    symbol_x, symbol_y = pos(layout["symbol"])
    pnl_x, pnl_y = pos(layout["pnl"])
    lev_x, lev_y = pos(layout["leverage"])
    badge_x, badge_y = pos(layout["side_badge"])

    draw.text(
        (symbol_x, symbol_y),
        symbol_text,
        fill=WHITE,
        font=symbol_font,
        anchor=layout["symbol"]["anchor"],
    )

    if data["exchange"] == "bybit":
        sym_bbox = draw.textbbox((0, 0), symbol_text, font=symbol_font)
        sym_width = sym_bbox[2] - sym_bbox[0]

        gap = 75
        layout_dx = layout["side_badge"].get("dx", 0)

        badge_x_final = symbol_x + sym_width + gap + layout_dx
        badge_y_final = badge_y
    else:
        badge_x_final = badge_x
        badge_y_final = badge_y

    draw_side_badge(
        draw,
        badge_x_final,
        badge_y_final,
        badge_text,
        side_color,
        data["exchange"],
        cfg,
    )

    draw.text(
        (pnl_x, pnl_y),
        pnl_text,
        fill=pnl_color,
        font=pnl_font,
        anchor=layout["pnl"]["anchor"],
    )

    draw.text(
        (lev_x, lev_y),
        lev_text,
        fill=WHITE,
        font=lev_font,
        anchor=layout["leverage"]["anchor"],
    )

    if data["exchange"] == "bingx":
        badge_font = ImageFont.truetype(font_regular, sizes["leverage"])

        mx, my = pos(layout["margin_mode"])
        lx, ly = pos(layout["leverage_bingx"])

        draw_gray_box(draw, mx, my, "Кросс", badge_font, layout["margin_mode"])
        draw_gray_box(
            draw,
            lx,
            ly,
            f"{data['leverage']}x",
            badge_font,
            layout["leverage_bingx"],
        )

    if data["exchange"] == "bybit":
        qty_text = f"{data['qty']:.4f}"
    else:
        qty_text = f"{data['qty']:.2f}"

    if data["exchange"] == "bingx":
        margin_text = f"{data['amount']:.2f}"
        draw_text(
            draw,
            layout,
            "margin",
            margin_text,
            font_regular,
            sizes["qty"],
            WHITE,
            w,
            h,
        )

    draw_text(
        draw,
        layout,
        "qty",
        qty_text,
        font_regular,
        sizes["qty"],
        WHITE,
        w,
        h,
    )
    draw_text(
        draw,
        layout,
        "entry",
        f"{data['entry']:,.2f}",
        font_regular,
        sizes["entry"],
        WHITE,
        w,
        h,
    )
    draw_text(
        draw,
        layout,
        "mark",
        f"{data['mark']:,.2f}",
        font_regular,
        sizes["mark"],
        WHITE,
        w,
        h,
    )
    draw_text(
        draw,
        layout,
        "liq",
        f"{data['liquidation']:,.2f}",
        font_regular,
        sizes["liq"],
        ORANGE,
        w,
        h,
    )

    if data["exchange"] == "bingx" and "risk" in layout:
        entry = float(data.get("entry") or 0)
        qty = float(data.get("qty") or 0)
        margin = float(data.get("amount") or 0)

        position_margin = entry * qty
        if position_margin == 0 or margin == 0:
            risk_text = "--"
            risk_value = None
        else:
            risk = margin / position_margin * 100.0
            if round(risk, 2) == 0:
                risk_text = "--"
                risk_value = None
            else:
                risk_text = f"{risk:.2f}%"
                risk_value = risk

        rx, ry = pos(layout["risk"])
        risk_font = ImageFont.truetype(font_regular, sizes["leverage"])

        if risk_value is None:
            risk_color = ORANGE
        elif risk_value <= 40:
            risk_color = GREEN
        elif risk_value <= 70:
            risk_color = ORANGE
        else:
            risk_color = RED

        draw.text(
            (rx, ry),
            risk_text,
            fill=risk_color,
            font=risk_font,
            anchor=layout["risk"]["anchor"],
        )

    img.save(output_path)
    return output_path


def draw_custom_bingx_lines(
    img: Image.Image,
     dict,
    layout: dict,
    font_side: ImageFont.FreeTypeFont,
    font_symbol: ImageFont.FreeTypeFont,
    w: int,
    h: int,
) -> None:
    symbol = data["symbol"]
    cfg = layout.get("lines")
    if not cfg:
        return

    line_path = os.path.join(BASE_DIR, "assets", "bingx", "line.png")
    if not os.path.exists(line_path):
        return

    line = Image.open(line_path).convert("RGBA")
    size = int(cfg.get("size", 80))
    line = line.resize((size, size), Image.LANCZOS)

    base_x = int(cfg["x"] * w + cfg.get("dx", 0))
    base_y = int(cfg["y"] * h + cfg.get("dy", 0))

    dummy = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(dummy)
    bbox_sym = d.textbbox((0, 0), symbol, font=font_symbol)
    sym_width = bbox_sym[2] - bbox_sym[0]
    gap = cfg.get("gap", 10)
    spacing = cfg.get("spacing", 221)

    x1 = base_x + sym_width + gap
    y1 = base_y
    x2 = x1 + size + spacing
    y2 = base_y

    img.paste(line, (x1, y1), line)
    img.paste(line, (x2, y2), line)

    draw = ImageDraw.Draw(img)

    side_cfg = layout.get("side_position", {})
    side_x = int(side_cfg.get("x", 0.5) * w)
    side_y = int(side_cfg.get("y", 0.335) * h)

    side_text = "Long" if data.get("side") == "long" else "Short"
    side_color = (0, 200, 120) if data.get("side") == "long" else (230, 60, 60)

    draw.text(
        (side_x, side_y),
        side_text,
        fill=side_color,
        font=font_side,
        anchor=side_cfg.get("anchor", "lm"),
    )

    lev_cfg = layout.get("leverage_position", {})
    lev_x = int(lev_cfg.get("x", 0.15) * w)
    lev_y = int(lev_cfg.get("y", 0.335) * h)

    lev_raw = str(data.get("leverage", ""))
    lev_num = lev_raw.replace("x", "").upper()
    lev_text = f"{lev_num}X" if lev_num else ""

    if lev_text:
        draw.text(
            (lev_x, lev_y),
            lev_text,
            fill=(255, 255, 255),
            font=font_side,
            anchor=lev_cfg.get("anchor", "lm"),
        )


# =====================================================
# КАСТОМ BYBIT
# =====================================================

def generate_custom_bybit_image( dict) -> str:
    pnl_raw = data["pnl"]
    try:
        pnl = float(str(pnl_raw).replace("%", "").replace(",", "."))
    except ValueError:
        pnl = 0.0

    template_side = "long" if pnl >= 0 else "short"
    template_path = os.path.join(BASE_DIR, "assets", "bybit", f"screenshot_{template_side}.png")
    output_path = os.path.join(BASE_DIR, "images", "custom_bybit.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    img = Image.open(template_path).convert("RGBA")
    w, h = img.size
    draw = ImageDraw.Draw(img)

    cfg = FONTS["custom_bybit"]
    layout = BYBIT_CUSTOM_LAYOUT["bybit"]

    font_regular = os.path.join(BASE_DIR, cfg["files"]["regular"])
    font_bold = os.path.join(BASE_DIR, cfg["files"]["bold"])

    symbol_font = ImageFont.truetype(font_bold, cfg["sizes"]["symbol"])

    icon_path = os.path.join(BASE_DIR, "assets", "bybit", "icon.png")
    cfg_icon = layout.get("symbol_icon")
    if os.path.exists(icon_path) and cfg_icon:
        icon = Image.open(icon_path).convert("RGBA")
        size = cfg_icon.get("size", 60)
        icon = icon.resize((size, size), Image.LANCZOS)
        x = int(cfg_icon["x"] * w) + cfg_icon.get("dx", 0)
        y = int(cfg_icon["y"] * h) + cfg_icon.get("dy", 0)
        img.paste(icon, (x, y), icon)
        draw = ImageDraw.Draw(img)

    username_font = ImageFont.truetype(font_regular, cfg["sizes"]["username"])

    pnl_value = float(str(data["pnl"]).replace("%", ""))
    if abs(pnl_value) > 99:
        pnl_font = ImageFont.truetype(font_bold, 80)
    else:
        pnl_font = ImageFont.truetype(font_bold, cfg["sizes"]["pnl"])

    # далее твоя логика отрисовки (если нужно, можешь дописать её по аналогии)

    img.save(output_path)
    return output_path

