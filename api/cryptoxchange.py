"""
Async client for cryptoxchange.cc API.
Caches rates for 5 minutes, falls back to cache on errors.
"""

import hashlib
import logging
import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

CXC_BASE_URL = "https://cryptoxchange.cc/api/v1"
CXC_API_LOGIN = os.getenv("CXC_API_LOGIN", "")
CXC_API_KEY = os.getenv("CXC_API_KEY", "")
CACHE_TTL = 300  # 5 minutes

_rates_cache: dict[str, Any] = {
    "data": None,
    "expires_at": 0.0,
}


def get_signature(params: dict, api_key: str) -> str:
    """Generate SHA256 signature from sorted params + api_key."""
    sorted_str = "".join(f"{k}{v}" for k, v in sorted(params.items()))
    return hashlib.sha256((sorted_str + api_key).encode()).hexdigest()


def _build_auth_params(extra: dict | None = None) -> dict:
    params: dict = {"api_login": CXC_API_LOGIN}
    if extra:
        params.update(extra)
    params["sign"] = get_signature(params, CXC_API_KEY)
    return params


async def get_rates() -> dict[str, float]:
    """
    Fetch exchange rates from cryptoxchange.cc.
    Returns cached data if fresh; falls back to stale cache on errors.
    """
    now = time.time()

    if _rates_cache["data"] is not None and now < _rates_cache["expires_at"]:
        logger.debug("Returning cached rates (TTL remaining: %.0fs)", _rates_cache["expires_at"] - now)
        return _rates_cache["data"]

    params = _build_auth_params()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info("Fetching rates from cryptoxchange.cc at %s", time.strftime("%Y-%m-%d %H:%M:%S"))
            response = await client.get(f"{CXC_BASE_URL}/rates", params=params)
            response.raise_for_status()
            data = response.json()

            if not data:
                raise ValueError("Empty response from cryptoxchange.cc /rates")

            rates = _parse_rates(data)
            _rates_cache["data"] = rates
            _rates_cache["expires_at"] = now + CACHE_TTL
            logger.info("Rates updated successfully: %s", rates)
            return rates

    except httpx.TimeoutException:
        logger.error("Timeout fetching rates from cryptoxchange.cc")
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error fetching rates: %s", e)
    except Exception as e:
        logger.error("Unexpected error fetching rates: %s", e)

    if _rates_cache["data"] is not None:
        logger.warning("Returning stale cached rates due to API error")
        return _rates_cache["data"]

    # Return fallback rates if no cache available
    logger.warning("No cached rates available, returning fallback rates")
    return _get_fallback_rates()


def _parse_rates(data: Any) -> dict[str, float]:
    """
    Parse rates response into standard format.
    Supports both list and dict response formats.
    """
    rates: dict[str, float] = {}

    # Handle list format: [{"from": "USD", "to": "RUB", "rate": 90.5}, ...]
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                from_curr = item.get("from", "").upper()
                to_curr = item.get("to", "").upper()
                rate = item.get("rate") or item.get("value") or item.get("price")
                if from_curr and to_curr and rate:
                    key = f"{from_curr}_{to_curr}"
                    rates[key] = float(rate)

    # Handle dict format: {"USD_RUB": 90.5, ...} or nested
    elif isinstance(data, dict):
        if "data" in data and isinstance(data["data"], (list, dict)):
            return _parse_rates(data["data"])
        for key, value in data.items():
            if isinstance(value, (int, float)):
                rates[key.upper()] = float(value)
            elif isinstance(value, dict):
                rate = value.get("rate") or value.get("value") or value.get("price")
                if rate:
                    rates[key.upper()] = float(rate)

    return rates if rates else _get_fallback_rates()


def _get_fallback_rates() -> dict[str, float]:
    """Fallback rates when API is completely unavailable."""
    return {
        "USD_RUB": 90.00,
        "EUR_RUB": 98.00,
        "USDT_RUB": 90.50,
        "RUB_USDT": 90.50,
    }


async def create_order(
    direction: str,
    amount: float,
    requisites: str,
    client_telegram_id: int,
) -> dict[str, Any]:
    """
    Create an order on cryptoxchange.cc.
    Returns order data dict with at least {"order_id": ..., "status": ...}.
    """
    params = _build_auth_params({
        "direction": direction,
        "amount": str(amount),
        "requisites": requisites,
        "client_id": str(client_telegram_id),
    })

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            logger.info(
                "Creating CXC order: direction=%s amount=%s tg_id=%s at %s",
                direction, amount, client_telegram_id, time.strftime("%Y-%m-%d %H:%M:%S"),
            )
            response = await client.post(f"{CXC_BASE_URL}/orders/create", json=params)
            response.raise_for_status()
            data = response.json()
            logger.info("CXC order created: %s", data)
            return data

    except httpx.TimeoutException:
        logger.error("Timeout creating CXC order for tg_id=%s", client_telegram_id)
        raise
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error creating CXC order: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error creating CXC order: %s", e)
        raise


async def get_order_status(order_id: str) -> dict[str, Any]:
    """
    Get order status from cryptoxchange.cc.
    """
    params = _build_auth_params({"order_id": order_id})

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info(
                "Fetching CXC order status: order_id=%s at %s",
                order_id, time.strftime("%Y-%m-%d %H:%M:%S"),
            )
            response = await client.get(f"{CXC_BASE_URL}/orders/status", params=params)
            response.raise_for_status()
            data = response.json()
            logger.info("CXC order status for %s: %s", order_id, data)
            return data

    except httpx.TimeoutException:
        logger.error("Timeout fetching CXC order status for order_id=%s", order_id)
        raise
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error fetching CXC order status: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error fetching CXC order status: %s", e)
        raise
