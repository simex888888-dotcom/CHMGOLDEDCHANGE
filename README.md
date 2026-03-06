# CHM GOLD EXCHANGE

Telegram Mini App для обмена криптовалюты и фиатных валют.
Посреднический сервис с комиссией 7% поверх курсов cryptoxchange.cc.

## Функциональность

- Просмотр курсов USD/EUR/USDT → RUB с комиссией 7%
- Создание заявок на обмен через Telegram Mini App
- Автоматические посты с курсами в Telegram-канал (10:00 и 20:00 МСК)
- Панель управления заявками для администратора в боте
- Уведомления клиентам при изменении статуса заявки

## Структура проекта

```
chm-gold-exchange/
├── api/                    # FastAPI бэкенд
│   ├── main.py             # Точка входа FastAPI
│   ├── routes.py           # API маршруты
│   ├── cryptoxchange.py    # Клиент cryptoxchange.cc
│   └── commission.py       # Логика комиссии 7%
├── bot/                    # Telegram бот (aiogram 3)
│   ├── main.py             # Точка входа бота
│   ├── scheduler.py        # Автопосты курсов
│   └── handlers/
│       ├── admin.py        # Команды администратора
│       └── client.py       # Уведомления клиентам
├── database/               # SQLAlchemy + Alembic
│   ├── models.py           # Модели Order, RateCache
│   └── engine.py           # Подключение к БД
├── frontend/               # Telegram Mini App
│   ├── index.html
│   ├── style.css
│   └── app.js
├── alembic/                # Миграции БД
├── render.yaml             # Конфиг деплоя Render.com
└── requirements.txt
```

## Локальный запуск

### Требования

- Python 3.11+
- SQLite (для разработки) или PostgreSQL

### Установка

```bash
# Клонировать репозиторий
git clone <repo-url>
cd chm-gold-exchange

# Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или: venv\Scripts\activate  # Windows

# Установить зависимости
pip install -r requirements.txt

# Скопировать переменные окружения
cp .env.example .env
# Заполнить .env своими значениями
```

### Настройка .env

```env
BOT_TOKEN=ваш_токен_бота
ADMIN_CHAT_ID=ваш_telegram_id
CHANNEL_ID=@ваш_канал  # или числовой ID
MINI_APP_URL=https://ваш-домен.render.com
DATABASE_URL=sqlite+aiosqlite:///./chmgold.db  # для локальной разработки
CXC_API_LOGIN=72Gr3iZwbIxSPqU1smmZIN8YUsJ48Q59
CXC_API_KEY=H6szJSeHnjGzPTlRILqfXB6QXo3k2Fkc
```

### Миграции БД

```bash
# SQLite (разработка) — таблицы создаются автоматически при запуске
# PostgreSQL (production):
alembic upgrade head
```

### Запуск API

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

API будет доступен на `http://localhost:8000`.
Фронтенд Mini App: `http://localhost:8000/`
Документация API: `http://localhost:8000/docs`

### Запуск бота

```bash
python -m bot.main
```

## Деплой на Render.com

1. Создайте аккаунт на [render.com](https://render.com)
2. Подключите репозиторий GitHub
3. Render автоматически обнаружит `render.yaml` и создаст сервисы:
   - `chm-gold-exchange-api` — FastAPI веб-сервис
   - `chm-gold-exchange-bot` — Telegram бот (worker)
   - `chmgold-db` — PostgreSQL база данных

4. Добавьте секретные переменные окружения в Render Dashboard:
   - `BOT_TOKEN`
   - `ADMIN_CHAT_ID`
   - `CHANNEL_ID`
   - `MINI_APP_URL` (URL вашего веб-сервиса на Render)
   - `CXC_API_LOGIN`
   - `CXC_API_KEY`

5. После деплоя зарегистрируйте Mini App у @BotFather:
   - `/newapp` → выберите бота → укажите URL веб-сервиса

## Telegram Mini App

Для работы Mini App необходимо:
1. У @BotFather выполнить `/newapp` для вашего бота
2. Указать URL задеплоенного сервиса
3. Обновить `MINI_APP_URL` в переменных окружения

## Admin-команды бота

Доступны только для `ADMIN_CHAT_ID`:

| Команда | Описание |
|---------|----------|
| `/start` | Список команд |
| `/orders` | Список заявок с пагинацией |
| `/order <id>` | Детали заявки |
| `/approve <id>` | Принять заявку |
| `/complete <id>` | Выполнить заявку |
| `/cancel <id> [причина]` | Отменить заявку |
| `/rates` | Текущие курсы |
| `/setrate <пара> <значение>` | Установить курс вручную |
| `/stats` | Статистика за день/неделю |

## API Endpoints

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/health` | Health check |
| GET | `/api/rates` | Курсы с комиссией 7% |
| POST | `/api/orders` | Создать заявку |
| GET | `/api/orders/{id}` | Статус заявки |
| GET | `/api/orders/user/{tg_id}` | Заявки пользователя |

Все запросы к `/api/*` требуют заголовок `X-Telegram-Init-Data` с данными Telegram WebApp.

## Направления обмена

| Код | Описание | Мин. сумма |
|-----|----------|------------|
| `USD_RUB` | USD → RUB (SWIFT) | 1 000 USD |
| `EUR_RUB` | EUR → RUB (SWIFT) | 1 000 EUR |
| `USDT_RUB` | USDT → RUB | 100 USDT |
| `RUB_USDT` | RUB → USDT | 10 000 RUB |
| `CASH_RUB` | Наличные RUB | 10 000 RUB |

## Комиссия

Все курсы cryptoxchange.cc увеличиваются на 7%:
- При покупке: `rate × 1.07`
- При продаже: `rate × 0.93`
