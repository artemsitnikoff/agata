"""Telethon-userbot: пишет от ЛИЧНОГО аккаунта целевому боту и ждёт ответ.

Реализация скопирована и адаптирована из ArkadyJarvis (app/services/userbot.py):
сообщение приходит адресату как от твоего юзер-аккаунта (того, чья
TELETHON_SESSION), а не от бота.

Ключевой сценарий agata: API → ask() → userbot шлёт текст боту @zeta963cy3c_bot
→ ждём ответ(ы) бота → возвращаем их вызывающему.
"""
import asyncio
import logging
import random
import time

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, PeerFloodError
from telethon.sessions import StringSession

from app.config import settings
from app.utils import SENECA_QUOTES

logger = logging.getLogger("agata")

# Пасхалка «ситников»: личный аккаунт салютует «Аве, Цезарь!» + цитата Сенеки.
# Кулдаун на чат — чтобы личный аккаунт не улетел во флуд/бан Telegram.
SENECA_COOLDOWN_SECONDS = 60


class UserbotClient:
    def __init__(self) -> None:
        self._client = TelegramClient(
            StringSession(settings.telethon_session),
            settings.telethon_api_id,
            settings.telethon_api_hash,
        )
        # Сериализуем диалоги с целевым ботом: telethon.conversation не терпит
        # параллельных диалогов в одном чате, да и боту так спокойнее.
        self._ask_lock = asyncio.Lock()
        self._target_entity = None
        self._seneca_cooldown: dict[int, float] = {}

        @self._client.on(events.NewMessage(incoming=True))
        async def _on_incoming(event: "events.NewMessage.Event") -> None:
            text = event.raw_text or ""
            if settings.enable_seneca and "ситников" in text.lower():
                try:
                    await self._maybe_seneca(event)
                except Exception as e:
                    logger.error("Userbot: seneca error: %s", e, exc_info=True)

    # ── lifecycle ─────────────────────────────────────────────────────────

    async def start(self) -> None:
        await self._client.connect()
        if not await self._client.is_user_authorized():
            raise RuntimeError(
                "Userbot: сессия недействительна. Сгенерируй заново: python gen_session.py"
            )
        me = await self._client.get_me()
        logger.info("Userbot connected as @%s (id=%s)", me.username, me.id)
        # Заранее резолвим целевого бота (один сетевой запрос на старте).
        try:
            self._target_entity = await self._client.get_entity(settings.target_bot)
            logger.info("Userbot: target resolved → %s", settings.target_bot)
        except Exception as e:
            logger.warning(
                "Userbot: не удалось заранее зарезолвить %s: %s (резолв при первом ask)",
                settings.target_bot, e,
            )

    async def stop(self) -> None:
        await self._client.disconnect()

    @property
    def connected(self) -> bool:
        return self._client.is_connected()

    # ── основной сценарий: спросить бота ───────────────────────────────────

    async def ask(
        self,
        text: str,
        *,
        target: str | None = None,
        timeout: float | None = None,
        collect_seconds: float | None = None,
    ) -> list[str]:
        """Отправить `text` целевому боту и вернуть его ответ(ы).

        target          — переопределить целевого бота (@username/id); по умолчанию settings.target_bot
        timeout         — ожидание ПЕРВОГО ответа, сек (settings.ask_timeout)
        collect_seconds — окно сбора последующих сообщений, сек (settings.ask_collect_seconds)

        Возвращает список текстов ответов (бот может дробить ответ на несколько
        сообщений). Бросает asyncio.TimeoutError если бот не ответил вовремя.
        """
        timeout = settings.ask_timeout if timeout is None else timeout
        collect_seconds = (
            settings.ask_collect_seconds if collect_seconds is None else collect_seconds
        )
        entity = await self._resolve_target(target)

        async with self._ask_lock:
            replies: list[str] = []
            try:
                async with self._client.conversation(
                    entity, timeout=timeout, exclusive=True,
                ) as conv:
                    await conv.send_message(text)
                    logger.info("Userbot: → %s: %r", target or settings.target_bot, text[:120])

                    first = await conv.get_response()
                    if first.raw_text:
                        replies.append(first.raw_text)

                    # Добираем дополнительные сообщения, пока бот «договаривает».
                    while True:
                        try:
                            nxt = await conv.get_response(timeout=collect_seconds)
                        except asyncio.TimeoutError:
                            break
                        if nxt.raw_text:
                            replies.append(nxt.raw_text)
            except (PeerFloodError, FloodWaitError):
                logger.error("Userbot: Telegram rate-limit/flood при ask")
                raise

            logger.info(
                "Userbot: ← %s: %d сообщ.", target or settings.target_bot, len(replies),
            )
            return replies

    async def send(self, text: str, *, target: str | None = None) -> int:
        """Отправить сообщение боту без ожидания ответа. Возвращает message_id."""
        entity = await self._resolve_target(target)
        msg = await self._client.send_message(entity, text)
        logger.info("Userbot: sent (no-wait) to %s, msg_id=%s", target or settings.target_bot, msg.id)
        return msg.id

    async def _resolve_target(self, target: str | None):
        if target:
            ent: object = int(target) if target.lstrip("-").isdigit() else target
            return await self._client.get_entity(ent)
        if self._target_entity is None:
            self._target_entity = await self._client.get_entity(settings.target_bot)
        return self._target_entity

    # ── пасхалка ────────────────────────────────────────────────────────────

    async def _maybe_seneca(self, event: "events.NewMessage.Event") -> None:
        """«Аве, Цезарь!» + цитата Сенеки. Кулдаун на чат против флуда."""
        chat_id = event.chat_id
        now = time.monotonic()
        if now - self._seneca_cooldown.get(chat_id, 0.0) < SENECA_COOLDOWN_SECONDS:
            return
        self._seneca_cooldown[chat_id] = now
        logger.info("Userbot: seneca trigger 'ситников' in chat=%s", chat_id)
        await event.reply("Аве, Цезарь!")
        await event.respond(random.choice(SENECA_QUOTES))
