import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.routes import router as api_router
from app.config import settings
from app.services.userbot import UserbotClient
from app.version import __version__

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("agata")


@asynccontextmanager
async def lifespan(app: FastAPI):
    userbot: UserbotClient | None = None
    if settings.telethon_session:
        try:
            userbot = UserbotClient()
            await userbot.start()
        except Exception as e:
            logger.warning("Userbot disabled: %s", e)
            userbot = None
    else:
        logger.info("Userbot: TELETHON_SESSION не задан — userbot выключен")

    app.state.userbot = userbot
    logger.info("agata %s ready (target=%s)", __version__, settings.target_bot)

    yield

    if userbot:
        await userbot.stop()
    logger.info("Shutdown complete")


TAGS_METADATA = [
    {
        "name": "userbot",
        "description": (
            "Работа через Telethon-userbot: сообщения уходят целевому боту "
            "**от личного аккаунта** (того, чья `TELETHON_SESSION`), не от бота."
        ),
    },
    {"name": "system", "description": "Служебные ручки: проверка состояния."},
]

DESCRIPTION = """\
HTTP-мост к Telegram-боту через **userbot**.

```
клиент → POST /api/ask {text} → agata → Telethon(личный акк) → @zeta963cy3c_bot
client ← {ok, replies[], reply} ← собранный ответ бота ←─────────────────────┘
```

**Аутентификация.** Если на сервере задан `API_TOKEN`, каждый запрос к `/api/ask`
и `/api/send` должен слать заголовок `X-API-Token` с этим значением.
Нажми **Authorize** 🔒 справа вверху и введи токен.
"""

app = FastAPI(
    title="agata",
    description=DESCRIPTION,
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
)
app.include_router(api_router, prefix="/api")


@app.get("/", include_in_schema=False)
async def root():
    """Корень → редирект на Swagger UI."""
    return RedirectResponse(url="/docs")
