# agata

Мост **API → Telethon userbot → целевой Telegram-бот → ответ**.

Через HTTP-API передаём параметры, userbot пишет от личного аккаунта боту
`@zeta963cy3c_bot`, ждёт его ответ и возвращает его вызывающему. Бэкенд на
FastAPI. Userbot-реализация взята из проекта ArkadyJarvis (включая пасхалку
«Аве, Цезарь!» + цитата Сенеки на слово «ситников»).

```
[ фронт / любой клиент ]
        │  POST /api/ask {text}
        ▼
   [ FastAPI (agata) ]
        │  Telethon (личный аккаунт)
        ▼
   [ @zeta963cy3c_bot ]
        │  ответ боту
        ▼
   reply → JSON-ответ API
```

## Запуск локально

```bash
pip install -e .
python gen_session.py           # один раз — получить TELETHON_SESSION
cp .env.example .env            # вставить TELETHON_SESSION и API_TOKEN
uvicorn app.main:app --port 8042 --reload
```

Документация и пробник: http://localhost:8042/docs

## API

Порт по умолчанию — **8042**. Аутентификация — заголовок `X-API-Token`
(если `API_TOKEN` задан в `.env`).

### `POST /api/ask` — написать боту и дождаться ответа

```bash
curl -X POST localhost:8042/api/ask \
  -H 'Content-Type: application/json' \
  -H 'X-API-Token: <ваш токен>' \
  -d '{"text": "/start"}'
```

```json
{
  "ok": true,
  "replies": ["Привет! ...", "Выберите действие ..."],
  "reply": "Привет! ...\n\nВыберите действие ...",
  "elapsed": 1.42
}
```

Параметры тела: `text` (обязателен), `target` (переопределить бота),
`timeout` (ждать первый ответ, сек), `collect_seconds` (окно сбора доп.
сообщений, сек).

### `POST /api/send` — написать без ожидания ответа

### `GET /api/health` — статус (подключён ли userbot)

## Деплой

См. [DEPLOY.md](DEPLOY.md). Коротко: `git pull && docker compose up -d --build`.
