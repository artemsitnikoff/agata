# agata API — гайд для интеграции

Сервис принимает текст по HTTP, пишет его Telegram-боту от имени userbot и
возвращает ответ бота. Один основной метод — `POST /api/ask`.

## Доступ

| | |
|---|---|
| **Base URL** | `http://<HOST>:8042` (точный адрес даст владелец сервиса) |
| **Аутентификация** | заголовок `X-API-Token: <TOKEN>` во всех запросах |
| **Формат** | JSON (`Content-Type: application/json`) |
| **Swagger UI** | `<Base URL>/docs` — интерактивный пробник (кнопка Authorize 🔒) |
| **ReDoc** | `<Base URL>/redoc` |

> `<HOST>` и `<TOKEN>` передаются отдельно (не в этом файле / не в репозитории).

## Эндпоинты

### `POST /api/ask` — написать боту и дождаться ответа

Тело запроса:

| поле | тип | обяз. | описание |
|---|---|---|---|
| `text` | string | да | текст, который уйдёт боту |
| `target` | string | нет | переопределить бота (`@username`/id); по умолчанию — настроенный бот |
| `timeout` | number | нет | сколько ждать первый ответ, сек (по умолчанию 60) |
| `collect_seconds` | number | нет | окно сбора доп. сообщений после первого ответа, сек (по умолчанию 3) |

Ответ:

| поле | тип | описание |
|---|---|---|
| `ok` | bool | успех |
| `replies` | string[] | сообщения бота (бот может ответить несколькими) |
| `reply` | string | те же сообщения, склеенные через `\n\n` |
| `elapsed` | number | время ответа, сек |
| `error` | string\|null | текст ошибки, если `ok=false` |

### `POST /api/send` — написать без ожидания ответа
Тело: `{ "text": "...", "target": "..."? }` → `{ "ok": true, "message_id": 123 }`.

### `GET /api/health` — статус (без токена)
`{ "status": "ok", "userbot": "connected", "target_bot": "@..." }`

## Примеры

### curl
```bash
curl -X POST http://<HOST>:8042/api/ask \
  -H 'Content-Type: application/json' \
  -H 'X-API-Token: <TOKEN>' \
  -d '{"text": "привет"}'
```

### JavaScript (fetch)
```js
const res = await fetch("http://<HOST>:8042/api/ask", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Token": "<TOKEN>",
  },
  body: JSON.stringify({ text: "привет" }),
});
const data = await res.json();
console.log(data.reply); // ответ бота
```

### Python (httpx)
```python
import httpx

r = httpx.post(
    "http://<HOST>:8042/api/ask",
    headers={"X-API-Token": "<TOKEN>"},
    json={"text": "привет"},
    timeout=70,
)
print(r.json()["reply"])
```

## Коды ответов / ошибки

| код | значение |
|---|---|
| `200` + `ok:true` | бот ответил, см. `replies`/`reply` |
| `200` + `ok:false` | бот не ответил в срок (`error`) или ошибка отправки |
| `403` | неверный/отсутствует `X-API-Token` |
| `503` | userbot не подключён на сервере |

## Замечания

- Запросы к боту выполняются **по очереди** (сериализация диалога) — при
  параллельных вызовах ответ просто придёт чуть позже, данные не перемешаются.
- Если бот долго думает — увеличь `timeout` в теле запроса.
- HTTP-таймаут на клиенте ставь больше, чем `timeout` запроса (например, +10 с).
