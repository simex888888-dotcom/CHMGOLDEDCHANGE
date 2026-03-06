"""
Commission logic for CHM GOLD EXCHANGE.
Owner charges 7% on top of all cryptoxchange.cc rates.
"""

COMMISSION = 0.07


def apply_buy_rate(base_rate: float) -> float:
    """Client buys currency: rate is higher (they pay more)."""
    return round(base_rate * (1 + COMMISSION), 2)


def apply_sell_rate(base_rate: float) -> float:
    """Client sells currency: rate is lower (they receive less)."""
    return round(base_rate * (1 - COMMISSION), 2)


def calculate_client_amount(
    base_rate: float,
    amount: float,
    direction: str,
) -> dict:
    """
    Calculate the amount the client will receive/pay with commission applied.

    direction: "buy" — client buys foreign currency (pays RUB)
               "sell" — client sells foreign currency (receives RUB)
    """
    if direction == "buy":
        rate = apply_buy_rate(base_rate)
    else:
        rate = apply_sell_rate(base_rate)

    total = round(amount * rate, 2)
    commission_amount = round(abs(total - (amount * base_rate)), 2)

    return {
        "base_rate": base_rate,
        "our_rate": rate,
        "amount": amount,
        "total": total,
        "commission": commission_amount,
        "commission_pct": "7%",
    }


DIRECTION_META = {
    "USD_RUB": {
        "label": "USD → RUB",
        "from_currency": "USD",
        "to_currency": "RUB",
        "direction": "sell",
        "min_amount": 1000,
        "description": "SWIFT-перевод",
    },
    "EUR_RUB": {
        "label": "EUR → RUB",
        "from_currency": "EUR",
        "to_currency": "RUB",
        "direction": "sell",
        "min_amount": 1000,
        "description": "SWIFT-перевод",
    },
    "USDT_RUB": {
        "label": "USDT → RUB",
        "from_currency": "USDT",
        "to_currency": "RUB",
        "direction": "sell",
        "min_amount": 100,
        "description": "Продать USDT",
    },
    "RUB_USDT": {
        "label": "RUB → USDT",
        "from_currency": "RUB",
        "to_currency": "USDT",
        "direction": "buy",
        "min_amount": 10000,
        "description": "Купить USDT",
    },
    "CASH_RUB": {
        "label": "Наличные RUB",
        "from_currency": "ANY",
        "to_currency": "RUB",
        "direction": "sell",
        "min_amount": 10000,
        "description": "Получить наличные",
    },
}
