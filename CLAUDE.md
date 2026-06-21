# agata

HTTP-мост к Telegram-боту через **userbot**: API принимает параметры → Telethon
от ЛИЧНОГО аккаунта пишет целевому боту `@zeta963cy3c_bot` → ждёт его ответ →
возвращает в JSON. Поверх этого API планируется фронт.

Userbot-часть скопирована из соседнего проекта ArkadyJarvis
(`../Arkady/ArkadyJarvis/app/services/userbot.py`), включая пасхалку: на слово
«ситников» во входящих личный аккаунт салютует «Аве, Цезарь!» + цитата Сенеки.

## Tech Stack

- **Python 3.11+**, FastAPI + Uvicorn
- **Userbot**: Telethon (StringSession) — сообщения уходят от личного аккаунта, не от бота
- **pydantic-settings** — конфиг из `.env`
- **Docker** — деплой; на проде обновление через `git pull && docker compose up -d --build`
- Порт **8042** (нестандартный: на сервере много проектов, заняты 8000–8004, 8765, 5432, 6379)

## Project Structure

```
app/
  main.py            # FastAPI app + lifespan (поднимает/гасит userbot, кладёт в app.state.userbot)
  config.py          # pydantic-settings Settings — все ENV (см. .env.example)
  utils.py           # SENECA_QUOTES + strip_numbered_item (пасхалка)
  services/
    userbot.py       # UserbotClient: start/stop, ask(), send(), пасхалка «ситников»
  api/
    routes.py        # /api/ask, /api/send, /api/health + проверка X-API-Token
gen_session.py       # one-time: генерация TELETHON_SESSION
Dockerfile           # python:3.11-slim, EXPOSE/CMD на 8042
docker-compose.yml   # сервис agata, порт 8042, env_file=.env
.env.example         # шаблон конфига
DEPLOY.md            # пошаговый запуск
```

## Поток данных

```
клиент/фронт --POST /api/ask {text}--> FastAPI --Telethon(личный акк)--> @zeta963cy3c_bot
                                                                              |
клиент <-- JSON {ok, replies[], reply} <-- собранный ответ бота <-------------+
```

## API

Все ручки под префиксом `/api`. Аутентификация — заголовок `X-API-Token`
(включается, только если `API_TOKEN` задан в `.env`).

- `POST /api/ask` — `{text, target?, timeout?, collect_seconds?}` → `{ok, replies[], reply, elapsed, error?}`.
  Главный сценарий: пишет боту и ждёт ответ. `replies` — список (бот может дробить
  ответ на несколько сообщений), `reply` — они же через `\n\n`.
- `POST /api/send` — `{text, target?}` → `{ok, message_id}`. Без ожидания ответа.
- `GET /api/health` — `{status, userbot, target_bot}`.

Интерактивный пробник: `/docs`.

## Ключевые решения / нюансы

- **ask() сериализован**: telethon `conversation(exclusive=True)` + `asyncio.Lock`
  на целевого бота — параллельные диалоги в одном чате telethon не терпит.
- **Сбор дробного ответа**: после первого ответа добираем сообщения, пока бот
  молчит дольше `ASK_COLLECT_SECONDS` (по умолчанию 3 с).
- **Целевой бот резолвится на старте** (один сетевой запрос), кэшируется; можно
  переопределить на запрос полем `target`.
- **Нет сессии → userbot не падает**: при пустом `TELETHON_SESSION` приложение
  поднимается, но `/api/ask` отдаёт 503 (см. `_get_userbot`).
- **Секреты**: `TELETHON_SESSION` = полный доступ к аккаунту; `.env` и `*.session`
  в `.gitignore`, в git НЕ коммитим.

## Локальный запуск

```bash
pip install -e .
python gen_session.py          # один раз → TELETHON_SESSION
cp .env.example .env           # вписать TELETHON_SESSION, API_TOKEN
uvicorn app.main:app --port 8042 --reload
```

## Деплой

См. [DEPLOY.md](DEPLOY.md). Прод: `git pull && docker compose up -d --build`.

## Конвенции

- Логгер один: `logging.getLogger("agata")`.
- Новые ENV — добавлять в `app/config.py` (Settings) И в `.env.example`.
- При смене порта править Dockerfile (EXPOSE + CMD `--port`) и docker-compose.yml;
  внутренний и внешний порт держим одинаковыми.
