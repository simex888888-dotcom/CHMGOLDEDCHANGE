LAYOUT = {
    "bybit": {
        # --- Обычный скрин ---
        "symbol": {"x": 0.05, "y": 0.16, "anchor": "lm", "dx": 0, "dy": 0},
        "leverage": {"x": 0.05, "y": 0.24, "anchor": "lm"},
        "side_badge": {"x": 0.32, "y": 0.16, "anchor": "lm", "dx": 0, "dy": -2},
        "pnl": {"x": 0.95, "y": 0.24, "anchor": "rm", "dx": 0, "dy": 0},

        "qty": {"x": 0.052, "y": 0.56, "anchor": "lm"},
        "entry": {"x": 0.29, "y": 0.56, "anchor": "lm"},
        "mark": {"x": 0.47, "y": 0.56, "anchor": "lm"},
        "liq": {"x": 0.95, "y": 0.56, "anchor": "rm"},

        # зоны очистки
        "clear_symbol": {"x": 0.05, "y": 0.116, "w": 0.19, "h": 0.11},
        "clear_side_badge": {
            "x": 0.22,
            "y": 0.09,
            "w": 0.18,
            "h": 0.25,
            "bg_x": 0.10,
            "bg_y": 0.05,
        },
        "clear_leverage": {"x": 0.05, "y": 0.23, "w": 0.18, "h": 0.10},
        "clear_qty": {"x": 0.05, "y": 0.522, "w": 0.18, "h": 0.10},
        "clear_entry": {"x": 0.29, "y": 0.527, "w": 0.12, "h": 0.10},
        "clear_mark": {"x": 0.44, "y": 0.527, "w": 0.18, "h": 0.10},
        "clear_liq": {"x": 0.775, "y": 0.527, "w": 0.26, "h": 0.10},
        "clear_pnl": {"x": 0.55, "y": 0.22, "w": 0.42, "h": 0.18},
    },

    "bingx": {
        # --- Обычный скрин ---
        "symbol": {"x": 0.055, "y": 0.12, "anchor": "lm", "dx": 0, "dy": 0},
        "leverage": {"x": 0.30, "y": 0.20, "anchor": "lm"},
        "side_badge": {"x": 0.10, "y": 0.188, "anchor": "lm", "dx": 0, "dy": 8},
        "pnl": {"x": 0.98, "y": 0.20, "anchor": "rm", "dx": 0, "dy": 0},

        # иконка монеты
        "symbol_icon": {
            "x": 0.03,
            "y": 0.03,
            "size": 170,
            "gap": 1,
            "dx": 0,
            "dy": 0,
        },

        # подписи внизу
        "qty": {"x": 0.05, "y": 0.396, "anchor": "lm"},
        "margin": {"x": 0.40, "y": 0.396, "anchor": "lm"},
        "entry": {"x": 0.05, "y": 0.57, "anchor": "lm"},
        "mark": {"x": 0.40, "y": 0.57, "anchor": "lm"},
        "liq": {"x": 0.96, "y": 0.57, "anchor": "rm"},

        "risk": {
            "x": 0.96,   # подгони позже
            "y": 0.40,
            "dx": 0,
            "dy": 0,
            "anchor": "rm",
        },


        # серые боксы Кросс / 20x (размеры только для BingX)
        "margin_mode": {
            "x": 0.22,
            "y": 0.20,
            "pad_x": 16,
            "pad_y": 12,
            "radius": 14,
        },
        "leverage_bingx": {
            "x": 0.33,
            "y": 0.20,
            "pad_x": 16,
            "pad_y": 16,
            "radius": 14,
        },

        # очистка
        "clear_symbol": {"x": 0.05, "y": 0.09, "w": 0.32, "h": 0.05},
        "clear_side_badge": {
            "x": 0.02,
            "y": 0.15,
            "w": 0.50,
            "h": 0.10,
            "bg_x": 0.12,
            "bg_y": 0.05,
        },
        "clear_leverage": {"x": 0.27, "y": 0.13, "w": 0.13, "h": 0.14},
        "clear_margin": {"x": 0.40, "y": 0.34, "w": 0.20, "h": 0.10},
        "clear_qty": {"x": 0.05, "y": 0.37, "w": 0.20, "h": 0.10},
        "clear_entry": {"x": 0.05, "y": 0.54, "w": 0.15, "h": 0.10},
        "clear_mark": {"x": 0.39, "y": 0.54, "w": 0.20, "h": 0.10},
        "clear_liq": {"x": 0.78, "y": 0.55, "w": 0.22, "h": 0.10},
        "clear_pnl": {"x": 0.55, "y": 0.15, "w": 0.43, "h": 0.098},
        "clear_risk": {"x": 0.85, "y": 0.34,"w": 0.20, "h": 0.10, "bg_x": 0.79, "bg_y": 0.28,}, 
    }        

}

BYBIT_CUSTOM_LAYOUT = {
    "bybit": {
        "username": {"x": 0.12, "y": 0.16, "anchor": "lm"},
        "symbol": {"x": 0.06, "y": 0.24, "anchor": "lm"},
        "symbol_icon": {
            "x": 0.045,
            "y": 0.14,
            "size": 60,
            "gap": 6,
            "dx": 0,
            "dy": 0,
        },
        "pnl": {"x": 0.06, "y": 0.39, "anchor": "lm"},
        "entry": {"x": 0.063, "y": 0.54, "anchor": "lm"},
        "exit": {"x": 0.063, "y": 0.65, "anchor": "lm"},
        "price": {"x": 0.23, "y": 0.72, "anchor": "lm"},

        # Кросс 20x (бокс отдельного размера для кастомного Bybit)
        "cross_leverage": {
            "x": 0.35,
            "y": 0.24,
            "w": 0.16,
            "h": 0.08,
            "pad_x": 12,
            "pad_y": 8,
            "radius": 65,
        },

        # очистка
        "clear_entry": {"x": 0.28, "y": 0.53, "w": 0.18, "h": 0.10},
        "clear_exit": {"x": 0.45, "y": 0.53, "w": 0.18, "h": 0.10},
        "clear_pnl": {"x": 0.55, "y": 0.22, "w": 0.40, "h": 0.18},
        "clear_leverage": {"x": 0.28, "y": 0.30, "w": 0.18, "h": 0.08},
    },

    "bingx": {
        # кастомный BingX
        "username": {"x": 0.15, "y": 0.87, "anchor": "lm"},
        "referral": {"x": 0.72, "y": 0.90, "anchor": "lm"},
        "datetime": {"x": 0.15, "y": 0.90, "anchor": "lm"},
        "symbol": {"x": 0.055, "y": 0.335, "anchor": "lm"},
        "pnl": {"x": 0.05, "y": 0.42, "anchor": "lm"},
        "entry": {"x": 0.36, "y": 0.592, "anchor": "lm"},
        "exit": {"x": 0.26, "y": 0.653, "anchor": "lm"},
        "price": {"x": 0.22, "y": 0.70, "anchor": "lm"},

        # позиция Лонг/Шорт и плечо/линии
        "side_position": {"x": 0.33, "y": 0.355, "anchor": "lm"},
        "leverage_position": {"x": 0.48, "y": 0.355, "anchor": "lm"},

        "cross_leverage": {
            "x": 0.25,
            "y": 0.22,
            "w": 0.16,
            "h": 0.08,
            "pad_x": 12,
            "pad_y": 8,
            "radius": 65,
        },

        "lines": {
            "x": 0.065,
            "y": 0.335,
            "size": 80,
            "gap": 10,
            "spacing": 221,
            "dx": 0,
            "dy": 0,
            "side_dx": 8,
            "side_dy": 0,
            "lev_dx": 5,
            "lev_dy": 0,
        },

        # очистка
        "clear_entry": {"x": 0.26, "y": 0.51, "w": 0.18, "h": 0.10},
        "clear_exit": {"x": 0.43, "y": 0.51, "w": 0.18, "h": 0.10},
        "clear_pnl": {"x": 0.53, "y": 0.20, "w": 0.40, "h": 0.18},
        "clear_leverage": {"x": 0.26, "y": 0.28, "w": 0.18, "h": 0.08},
    },
}
