"""
FastAPI routes for CHM GOLD EXCHANGE.
"""

import hashlib
import hmac
import logging
import os
import time
import uuid
from collections import defaultdict
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.commission import DIRECTION_META, apply_buy_rate, apply_sell_rate, calculate_client_amount
from api.cryptoxchange import get_rates
from database.engine import get_db
from database.models import Order, OrderStatus

logger = logging.getLogger(__name__)

router = APIRouter()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# --------------------------------------------------------------------------
# Rate limiting (in-memory, per user_id)
# --------------------------------------------------------------------------
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW = 60  # seconds


def _check_rate_limit(user_id: str) -> None:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    requests = _rate_limit_store[user_id]
    _rate_limit_store[user_id] = [t for t in requests if t > window_start]
    if len(_rate_limit_store[user_id]) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(status_code=429, detail="Превышен лимит запросов. Попробуйте через минуту.")
    _rate_limit_store[user_id].append(now)


# --------------------------------------------------------------------------
# Telegram initData validation
# --------------------------------------------------------------------------
def validate_telegram_data(init_data: str, bot_token: str) -> dict:
    if not init_data or not bot_token:
        raise HTTPException(status_code=403, detail="Неверные данные Telegram")

    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        raise HTTPException(status_code=403, detail="Неверные данные Telegram")

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=403, detail="Неверные данные Telegram")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if calculated != received_hash:
        raise HTTPException(status_code=403, detail="Неверные данные Telegram")

    return parsed


def get_telegram_user(request: Request) -> dict:
    """Extract and validate Telegram user from initData header."""
    init_data = request.headers.get("X-Telegram-Init-Data", "")

    # Allow dev mode without initData if BOT_TOKEN is not set
    if not BOT_TOKEN and not init_data:
        return {"id": 0, "username": "dev"}

    if not init_data:
        raise HTTPException(status_code=403, detail="Требуется авторизация Telegram")

    return validate_telegram_data(init_data, BOT_TOKEN)


# --------------------------------------------------------------------------
# Pydantic schemas
# --------------------------------------------------------------------------
class OrderCreate(BaseModel):
    direction: str = Field(..., pattern="^(USD_RUB|EUR_RUB|USDT_RUB|RUB_USDT|CASH_RUB)$")
    amount_from: float = Field(..., gt=0)
    requisites: str = Field(..., min_length=5, max_length=500)
    city: str | None = Field(None, max_length=100)


class OrderResponse(BaseModel):
    id: str
    user_id: int
    username: str | None
    direction: str
    amount_from: float
    amount_to: float
    base_rate: float
    our_rate: float
    commission: float
    requisites: str
    city: str | None
    status: str
    cxc_order_id: str | None
    admin_note: str | None
    created_at: str
    updated_at: str


def _order_to_dict(order: Order) -> dict:
    return {
        "id": str(order.id),
        "user_id": order.user_id,
        "username": order.username,
        "direction": order.direction,
        "amount_from": float(order.amount_from),
        "amount_to": float(order.amount_to),
        "base_rate": float(order.base_rate),
        "our_rate": float(order.our_rate),
        "commission": float(order.commission),
        "requisites": order.requisites,
        "city": order.city,
        "status": order.status.value,
        "cxc_order_id": order.cxc_order_id,
        "admin_note": order.admin_note,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
    }


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "CHM GOLD EXCHANGE"}


@router.get("/api/rates")
async def get_exchange_rates(request: Request):
    """Get exchange rates with 7% commission applied."""
    try:
        base_rates = await get_rates()
    except Exception as e:
        logger.error("Failed to get rates: %s", e)
        raise HTTPException(status_code=503, detail="Сервис временно недоступен")

    result = {}
    for direction, meta in DIRECTION_META.items():
        from_curr = meta["from_currency"]
        to_curr = meta["to_currency"]

        # Try to find the rate
        rate_key = f"{from_curr}_{to_curr}"
        alt_key = f"{to_curr}_{from_curr}"

        base = base_rates.get(rate_key) or base_rates.get(alt_key)

        if direction == "CASH_RUB":
            base = base_rates.get("USD_RUB", 90.0)

        if base is None:
            base = 90.0  # fallback

        if meta["direction"] == "buy":
            our_rate = apply_buy_rate(base)
        else:
            our_rate = apply_sell_rate(base)

        result[direction] = {
            "direction": direction,
            "label": meta["label"],
            "description": meta["description"],
            "from_currency": from_curr,
            "to_currency": to_curr,
            "base_rate": base,
            "our_rate": our_rate,
            "commission_pct": "7%",
            "min_amount": meta["min_amount"],
        }

    return result


@router.post("/api/orders")
async def create_order(
    order_data: OrderCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a new exchange order."""
    tg_user = get_telegram_user(request)
    user_id = tg_user.get("id", 0)
    _check_rate_limit(str(user_id))

    # Get current rates
    base_rates = await get_rates()
    meta = DIRECTION_META.get(order_data.direction)
    if not meta:
        raise HTTPException(status_code=400, detail="Неверное направление обмена")

    from_curr = meta["from_currency"]
    to_curr = meta["to_currency"]
    rate_key = f"{from_curr}_{to_curr}"
    alt_key = f"{to_curr}_{from_curr}"

    base_rate = base_rates.get(rate_key) or base_rates.get(alt_key)
    if order_data.direction == "CASH_RUB":
        base_rate = base_rates.get("USD_RUB", 90.0)
    if base_rate is None:
        base_rate = 90.0

    # Calculate amounts
    calc = calculate_client_amount(base_rate, order_data.amount_from, meta["direction"])

    # Extract user info
    import json
    user_obj = tg_user.get("user", "{}")
    if isinstance(user_obj, str):
        try:
            user_obj = json.loads(user_obj)
        except Exception:
            user_obj = {}
    username = user_obj.get("username") if isinstance(user_obj, dict) else None

    order = Order(
        id=uuid.uuid4(),
        user_id=user_id,
        username=username,
        direction=order_data.direction,
        amount_from=order_data.amount_from,
        amount_to=calc["total"],
        base_rate=calc["base_rate"],
        our_rate=calc["our_rate"],
        commission=calc["commission"],
        requisites=order_data.requisites,
        city=order_data.city,
        status=OrderStatus.pending,
    )

    db.add(order)
    await db.flush()
    await db.refresh(order)

    logger.info("Order created: id=%s user_id=%s direction=%s", order.id, user_id, order.direction)

    # Notify client via bot (fire and forget)
    try:
        from bot.handlers.client import notify_order_created
        import asyncio
        asyncio.create_task(notify_order_created(order))
    except Exception as e:
        logger.warning("Could not send client notification: %s", e)

    return _order_to_dict(order)


@router.get("/api/orders/user/{tg_id}")
async def get_user_orders(
    tg_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get all orders for a specific Telegram user."""
    tg_user = get_telegram_user(request)
    requester_id = tg_user.get("id", 0)

    # Users can only see their own orders (admins can see all via bot)
    if str(requester_id) != str(tg_id) and requester_id != 0:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    result = await db.execute(
        select(Order)
        .where(Order.user_id == tg_id)
        .order_by(Order.created_at.desc())
        .limit(50)
    )
    orders = result.scalars().all()
    return [_order_to_dict(o) for o in orders]


@router.get("/api/orders/{order_id}")
async def get_order(
    order_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific order by ID."""
    tg_user = get_telegram_user(request)
    user_id = tg_user.get("id", 0)

    try:
        order_uuid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный ID заявки")

    result = await db.execute(select(Order).where(Order.id == order_uuid))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    # Only allow owner or admin
    if order.user_id != user_id and user_id != 0:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    return _order_to_dict(order)
