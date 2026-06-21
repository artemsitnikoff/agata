import asyncio
import logging
import time

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger("agata")
router = APIRouter()


# ── auth ──────────────────────────────────────────────────────────────────


def _check_token(token: str | None) -> None:
    """Проверка общего секрета. Пустой api_token = аутентификация выключена."""
    if not settings.api_token:
        return
    if token != settings.api_token:
        raise HTTPException(403, "Invalid API token")


def _get_userbot(request: Request):
    userbot = getattr(request.app.state, "userbot", None)
    if userbot is None or not userbot.connected:
        raise HTTPException(503, "Userbot не подключён (проверь TELETHON_SESSION)")
    return userbot


# ── health ──────────────────────────────────────────────────────────────────


@router.get("/health", tags=["system"])
async def health(request: Request):
    userbot = getattr(request.app.state, "userbot", None)
    ub_ok = bool(userbot and userbot.connected)
    return {
        "status": "ok" if ub_ok else "degraded",
        "userbot": "connected" if ub_ok else "disconnected",
        "target_bot": settings.target_bot,
    }


# ── ask: написать боту и получить ответ ──────────────────────────────────────


class AskRequest(BaseModel):
    """Параметры запроса к целевому боту."""

    text: str = Field(..., description="Текст сообщения боту", examples=["/start"])
    target: str | None = Field(
        None,
        description="Переопределить целевого бота (@username или id). По умолчанию из конфига.",
        examples=["@zeta963cy3c_bot"],
    )
    timeout: float | None = Field(
        None, description="Сколько ждать первый ответ, сек", examples=[60],
    )
    collect_seconds: float | None = Field(
        None, description="Окно сбора доп. сообщений после первого ответа, сек", examples=[3],
    )


class AskResponse(BaseModel):
    ok: bool
    replies: list[str] = Field(default_factory=list, description="Сообщения-ответы бота")
    reply: str = Field("", description="Все ответы, склеенные через \\n\\n")
    elapsed: float = Field(0.0, description="Время ответа, сек")
    error: str | None = None


@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Написать боту и дождаться ответа",
    tags=["userbot"],
)
async def ask(
    body: AskRequest,
    request: Request,
    x_api_token: str | None = Header(None, description="Токен авторизации"),
):
    _check_token(x_api_token)
    userbot = _get_userbot(request)

    started = time.monotonic()
    try:
        replies = await userbot.ask(
            body.text,
            target=body.target,
            timeout=body.timeout,
            collect_seconds=body.collect_seconds,
        )
    except asyncio.TimeoutError:
        return AskResponse(
            ok=False, elapsed=round(time.monotonic() - started, 2),
            error="Бот не ответил в отведённое время",
        )
    except Exception as e:
        logger.error("ask failed: %s", e, exc_info=True)
        return AskResponse(
            ok=False, elapsed=round(time.monotonic() - started, 2), error=str(e),
        )

    return AskResponse(
        ok=True,
        replies=replies,
        reply="\n\n".join(replies),
        elapsed=round(time.monotonic() - started, 2),
    )


# ── send: написать боту без ожидания ответа ──────────────────────────────────


class SendRequest(BaseModel):
    text: str = Field(..., description="Текст сообщения боту")
    target: str | None = Field(None, description="Переопределить целевого бота")


class SendResponse(BaseModel):
    ok: bool
    message_id: int | None = None
    error: str | None = None


@router.post(
    "/send",
    response_model=SendResponse,
    summary="Написать боту без ожидания ответа",
    tags=["userbot"],
)
async def send(
    body: SendRequest,
    request: Request,
    x_api_token: str | None = Header(None, description="Токен авторизации"),
):
    _check_token(x_api_token)
    userbot = _get_userbot(request)
    try:
        msg_id = await userbot.send(body.text, target=body.target)
        return SendResponse(ok=True, message_id=msg_id)
    except Exception as e:
        logger.error("send failed: %s", e, exc_info=True)
        return SendResponse(ok=False, error=str(e))
