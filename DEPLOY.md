# Запуск и деплой agata — по шагам

Бэкенд в Docker, порт **8042** (нестандартный — на сервере уже крутятся другие
проекты). Обновление на проде — через `git pull`.

- [Часть A. Получить сессию userbot (один раз, на своей машине)](#часть-a-получить-сессию-userbot-один-раз)
- [Часть B. Первый запуск на сервере](#часть-b-первый-запуск-на-сервере)
- [Часть C. Обновление новой версии](#часть-c-обновление-новой-версии)
- [Локальный запуск без Docker](#локальный-запуск-без-docker)
- [Шпаргалка команд](#шпаргалка-команд)
- [Если что-то не работает](#если-что-то-не-работает)

---

## Часть A. Получить сессию userbot (один раз)

Сообщения боту идут от **личного аккаунта Telegram**. Чтобы получить строку
сессии, нужен телефон этого аккаунта и доступ к коду входа. Делается на машине,
где можешь принять код (свой ноут).

**Шаг 1.** Поставить telethon:
```bash
pip install telethon
```

**Шаг 2.** Запустить генератор сессии:
```bash
python gen_session.py
```

**Шаг 3.** Ввести по запросу:
- номер телефона аккаунта в формате `+7...`
- код, пришедший в Telegram
- пароль (если включена 2FA)

**Шаг 4.** Скрипт напечатает строку вида:
```
TELETHON_SESSION=1ApWap...очень_длинная_строка...
```
Скопируй её — понадобится на сервере.

> ⚠️ Эта строка = полный доступ к аккаунту. Никому не показывай, в git не коммить
> (она хранится в `.env`, который в `.gitignore`).

---

## Часть B. Первый запуск на сервере

Нужны: Docker + Docker Compose + Git.

**Шаг 1.** Склонировать репозиторий и зайти в папку:
```bash
git clone <repo-url> agata
cd agata
```

**Шаг 2.** Создать `.env` из шаблона:
```bash
cp .env.example .env
nano .env
```

**Шаг 3.** Заполнить `.env`:
```ini
TELETHON_SESSION=<строка из Части A>
TARGET_BOT=@zeta963cy3c_bot          # целевой бот (уже стоит по умолчанию)
API_TOKEN=<придумай длинный секрет>  # его клиенты будут слать в заголовке X-API-Token
ASK_TIMEOUT=60                       # сколько ждать ответ бота, сек
ASK_COLLECT_SECONDS=3                # окно сбора «дробного» ответа, сек
ENABLE_SENECA=true                   # пасхалка «ситников»
```
Сохранить: `Ctrl+O`, `Enter`, `Ctrl+X`.

**Шаг 4.** Собрать и запустить:
```bash
docker compose up -d --build
```

**Шаг 5.** Проверить, что userbot подключился:
```bash
curl localhost:8042/api/health
# ожидаем: {"status":"ok","userbot":"connected","target_bot":"@zeta963cy3c_bot"}

docker compose logs --tail=30
# в логах должно быть: Userbot connected as @...
```

**Шаг 6.** Боту иногда нужно сначала `/start` (один раз):
```bash
curl -X POST localhost:8042/api/ask \
  -H 'Content-Type: application/json' \
  -H 'X-API-Token: <твой API_TOKEN>' \
  -d '{"text":"/start"}'
```

**Шаг 7.** Боевой запрос:
```bash
curl -X POST localhost:8042/api/ask \
  -H 'Content-Type: application/json' \
  -H 'X-API-Token: <твой API_TOKEN>' \
  -d '{"text":"привет"}'
# ответ: {"ok":true,"replies":["..."],"reply":"...","elapsed":1.2}
```

Готово. Swagger-пробник доступен на `http://<сервер>:8042/docs`.

---

## Часть C. Обновление новой версии

После `git push` в репозиторий — на сервере:
```bash
cd ~/agata
git pull
docker compose up -d --build
```

Одной строкой:
```bash
cd ~/agata && git pull && docker compose up -d --build
```

Проверка после обновления:
```bash
curl localhost:8042/api/health
docker compose logs --tail=50
docker compose ps
```

> `.env` при обновлении не трогается (он в `.gitignore`, на сервере остаётся свой).

---

## Локальный запуск без Docker

Для разработки:
```bash
pip install -e .
cp .env.example .env          # вписать TELETHON_SESSION и API_TOKEN
uvicorn app.main:app --port 8042 --reload
```
Открыть `http://localhost:8042/docs`.

---

## Шпаргалка команд

```bash
docker compose logs -f          # логи в реальном времени
docker compose restart          # перезапуск без пересборки
docker compose down             # остановить и удалить контейнер
docker compose up -d --build    # пересобрать и запустить
docker compose ps               # статус
docker compose exec agata bash  # шелл внутри контейнера
```

---

## Если что-то не работает

| Симптом | Причина / решение |
|---|---|
| `health` → `userbot:"disconnected"` | Пустой/битый `TELETHON_SESSION`. Пересоздай (Часть A), обнови `.env`, `docker compose up -d --force-recreate`. |
| `/api/ask` → `403 Invalid API token` | Заголовок `X-API-Token` не совпал с `API_TOKEN` из `.env`. |
| `/api/ask` → `503 Userbot не подключён` | Сессия не задана или не авторизована — смотри логи `docker compose logs`. |
| `ok:false, error:"Бот не ответил..."` | Бот молчит/не нажат `/start`, либо мал `ASK_TIMEOUT`. Отправь `/start`, увеличь таймаут. |
| `sessia недействительна` в логах | Сессия отозвана в Telegram. Пересоздай (Часть A). |
| Порт 8042 занят | Поменяй порт в `Dockerfile` (EXPOSE + CMD `--port`) и `docker-compose.yml` (`ports`), пересобери. |
| `PeerFloodError` / `FloodWait` в логах | Telegram режет за частые сообщения с личного аккаунта. Сбавь частоту запросов. |
