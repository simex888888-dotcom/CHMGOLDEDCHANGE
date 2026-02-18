FONTS = {
    "bybit": {
        "files": {
            "regular": "fonts/SF_Pro_Display_Regular.otf",
            "bold": "fonts/SF_Pro_Display_Semibold.otf",
        },
        "sizes": {
            "symbol": 54,
            "pnl": 42,
            "leverage": 22,
            "qty": 37,
            "entry": 37,
            "mark": 37,
            "liq": 37,
            "badge": 42,
        },
        "badge_style": "outline",
    },
    "bingx": {
        "files": {
            "regular": "fonts/SF_Pro_Display_Regular.otf",
            "bold": "fonts/SF_Pro_Display_Semibold.otf",
        },
        "sizes": {
            "symbol": 54,
            "pnl": 54,
            "leverage": 54,
            "qty": 52,
            "entry": 52,
            "mark": 52,
            "liq": 52,
            "badge": 26,
            "badge_text_offset_y": -2,  # вертикальное смещение текста внутри бейджа

            # отдельные настройки рамок для Long (зелёная) и Short (красная)
            "badge_pad_green_x": 16,
            "badge_pad_green_y": 30,
            "badge_min_green_w": 110,
            "badge_min_green_h": 46,

            "badge_pad_red_x": 16,
            "badge_pad_red_y": 16,
            "badge_min_red_w": 110,
            "badge_min_red_h": 25,
           

        },
        "badge_style": "filled",
    },
    "custom_bybit": {
        "files": {
            "regular": "fonts/SF_Pro_Display_Regular.otf",
            "bold": "fonts/SF_Pro_Display_Semibold.otf",
        },
        "sizes": {
            "username": 36,
            "symbol": 58,
            "pnl": 120,
            "entry": 48,
            "exit": 48,
            "leverage_text": 40,

        },
        "badge_style": "outline",
    },
    "custom_bingx": {
        "files": {
            "regular": "fonts/SF_Pro_Display_Regular.otf",
            "bold": "fonts/SF_Pro_Display_Semibold.otf",
        },
        "sizes": {
            "username": 50,
            "symbol": 66,
            "pnl": 200,
            "entry": 54,
            "exit": 54,
            "leverage_text": 66,
            "side_text": 66,
        },
        "badge_style": "filled",
    },
}
