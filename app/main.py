import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

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


app = FastAPI(
    title="agata",
    description="API → Telethon userbot → целевой Telegram-бот → ответ",
    version=__version__,
    docs_url="/docs",
    lifespan=lifespan,
)
app.include_router(api_router, prefix="/api")
