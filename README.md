# Wot Seller Bot

Telegram-бот для продажи аккаунтов **World of Tanks / WoT Blitz**.
Стек: Python 3.11+, [aiogram 3.x](https://docs.aiogram.dev), SQLite (aiosqlite), Telegram Stars.

UI оформлен в стиле **Deep Dark** с эмодзи. Все сообщения — на русском.

## Возможности

- 📖 Каталог товаров с инлайн-кнопками и описанием.
- ⭐ Оплата через **Telegram Stars** (готова заявка через менеджера @BUMZILKA как фоллбэк).
- 👤 Личный профиль: ID, ник, баланс, реферальная ссылка.
- 💎 Реферальная система: 5% от каждой покупки реферала идёт пригласившему.
- 🛠 Админ-панель (только для ID из `ADMIN_IDS`):
  - CRUD товаров (название, описание, цена ₽, цена ⭐, сток, фото, вкл/выкл, удаление);
  - редактирование текстов «Инфо» и «Поддержка»;
  - просмотр последних пользователей и заказов;
  - команда `/balance <user_id> <delta>` для корректировки баланса.
- 🛡 Безопасность: throttling (token bucket), валидация callback и текста, проверка админа на каждом действии, параметризованные SQL-запросы, идемпотентная обработка платежей.
- 📜 Логирование с ротацией.
- 🔌 Поддержка прокси для исходящего трафика.
- 🐧 systemd unit и скрипт деплоя для Ubuntu.

## Структура

```
app/
  main.py             # точка входа
  config.py           # загрузка .env
  db.py               # SQLite, миграции, сидинг
  keyboards.py        # клавиатуры и callback-фабрики
  handlers/
    start.py          # /start, deep-link рефералки
    menu.py           # главное reply-меню
    products.py       # каталог + покупка
    profile.py        # профиль и реф. ссылка
    info.py           # блок «Инфо»
    support.py        # блок «Поддержка»
    admin.py          # админ-панель (FSM)
    payments.py       # PreCheckout + SuccessfulPayment
  middlewares/
    throttling.py     # анти-флуд (token bucket)
    security.py       # валидация ввода, проверка бана/админа
  services/
    products.py       # бизнес-логика товаров
    referrals.py      # рефералы и выплаты
    payments/
      base.py             # абстрактный провайдер
      telegram_stars.py   # реализация для Stars
deploy/
  bot.service         # systemd unit
  deploy_ubuntu.sh    # установка на Ubuntu
```

## Установка локально

```bash
git clone https://github.com/stalxboro-pixel/denisburkalcev.git
cd denisburkalcev
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# отредактируйте .env: BOT_TOKEN, ADMIN_IDS, BOT_USERNAME
```

### Инициализация БД

```bash
python -c "import asyncio; from app import db; asyncio.run(db.init_db())"
```

При первом запуске схема создаётся автоматически и в неё засеиваются стартовые товары.

### Запуск

Linux/macOS:
```bash
python -m app
# или
python main.py
```

Windows:
```powershell
python -m app
```

## Деплой на Ubuntu (production)

```bash
sudo ./deploy/deploy_ubuntu.sh
sudo nano /opt/wot-seller-bot/.env       # BOT_TOKEN и т.д.
sudo systemctl restart wot-seller-bot
sudo journalctl -u wot-seller-bot -f
```

Скрипт устанавливает зависимости, создаёт системного пользователя `botuser`, разворачивает venv в `/opt/wot-seller-bot/.venv`, ставит systemd-сервис с базовым хардингом, включает `ufw` и `fail2ban`.

### Заметки по защите от DDoS / спама

- Включён `ufw` (deny incoming, allow OpenSSH). Откройте дополнительные порты только если используете webhook.
- Включён `fail2ban` для SSH.
- В `bot.service` заданы `Restart=on-failure`, `StartLimitBurst=10`, `NoNewPrivileges`, `ProtectSystem=full`, `MemoryDenyWriteExecute`.
- Для webhook-режима поставьте перед ботом nginx + Cloudflare (proxy + rate limiting).
- В коде включён token-bucket throttling и валидация ввода.

## Платежи

`app/services/payments/base.py` определяет интерфейс `PaymentProvider`. `TelegramStarsProvider` реализует Stars (валюта `XTR`, `provider_token=""`).

Чтобы добавить **CryptoBot** или **карты**:

1. Создайте `app/services/payments/cryptobot.py` с подклассом `PaymentProvider`.
2. Зарегистрируйте кнопку `BuyCB(provider="crypto", ...)` в `keyboards.py`.
3. Добавьте обработчик в `handlers/products.py`, вызывающий `provider.create_invoice(...)`.
4. Подключите webhook/верификацию платежа аналогично `handlers/payments.py`.

## Реферальная система

- Ссылка приглашения: `https://t.me/<BOT_USERNAME>?start=r_<user_id>`.
- При первом `/start r_<id>` сохраняется `referrer_id`, если это не сам пользователь.
- На каждый успешный платёж пригласившему начисляется `REFERRAL_PERCENT` % (по умолчанию 5%) от суммы в ₽ на внутренний баланс. Идемпотентность гарантируется `UNIQUE(order_id)` в `referral_rewards`.

## Команды

- `/start` — приветствие и главное меню.
- `/start r_<id>` — регистрация по рефералке.
- `/menu` — повторный показ меню.
- `/admin` — админ-панель (только для `ADMIN_IDS`).
- `/balance <user_id> <delta>` — изменить баланс пользователя (только админ).

## Лицензия

Внутренний проект. Использование вне магазина — с разрешения владельца.
