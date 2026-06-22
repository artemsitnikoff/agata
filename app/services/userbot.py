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

# Маркеры «сообщения-заглушки»: бот прислал плейсхолдер и ещё думает. Пока ответ
# состоит только из таких сообщений — ждём правку/финал (см. ask_edit_timeout).
# Сравнение по подстроке в lower(), поэтому маркеры — характерные фразы загрузки,
# а не эмодзи (эмодзи может оказаться и в реальном ответе → лишнее ожидание).
PLACEHOLDER_MARKERS = (
    "подожд",            # «пожалуйста, подождите»
    "идёт поиск", "идет поиск",
    "идёт обработ", "идет обработ",
    "выполняется", "обрабатыва",
    "загруж",            # «загружаю / загрузка»
    "ищу", "минуточк", "один момент", "одну секунд", "секундочк",
    "please wait", "loading", "searching", "processing", "one moment",
)


def _looks_like_placeholder(text: str) -> bool:
    """True, если текст похож на временную заглушку «идёт поиск… подождите»."""
    low = text.lower()
    return any(marker in low for marker in PLACEHOLDER_MARKERS)


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
        edit_timeout: float | None = None,
    ) -> list[str]:
        """Отправить `text` целевому боту и вернуть его ответ(ы).

        target          — переопределить целевого бота (@username/id); по умолчанию settings.target_bot
        timeout         — ожидание ПЕРВОГО ответа, сек (settings.ask_timeout)
        collect_seconds — окно сбора последующих сообщений, сек (settings.ask_collect_seconds)
        edit_timeout    — пока ответ = только плейсхолдер «идёт поиск…», ждём его
                          правку/финал до этого лимита, сек (settings.ask_edit_timeout)

        Возвращает список текстов ответов (бот может дробить ответ на несколько
        сообщений; плейсхолдеры «идёт поиск…» из финального списка убираются, если
        есть содержательный ответ). Бросает asyncio.TimeoutError если бот не ответил.
        """
        timeout = settings.ask_timeout if timeout is None else timeout
        collect_seconds = (
            settings.ask_collect_seconds if collect_seconds is None else collect_seconds
        )
        edit_timeout = (
            settings.ask_edit_timeout if edit_timeout is None else edit_timeout
        )
        # Внутренний таймаут отдельных get_response/get_edit: с запасом больше любого
        # нашего окна, чтобы их собственный wait_for не срабатывал раньше нашей логики.
        inner = max(timeout, edit_timeout, collect_seconds) + 5.0
        entity = await self._resolve_target(target)

        async with self._ask_lock:
            by_id: dict[int, str] = {}
            order: list[int] = []

            def _record(msg) -> None:
                if msg.id not in by_id:
                    order.append(msg.id)
                by_id[msg.id] = msg.raw_text or ""

            resp = edit = None
            try:
                async with self._client.conversation(
                    entity, timeout=timeout, exclusive=True,
                ) as conv:
                    await conv.send_message(text)
                    logger.info("Userbot: → %s: %r", target or settings.target_bot, text[:120])

                    _record(await conv.get_response())

                    # Долгоживущие ожидания: новое сообщение И правка. Перевзводим
                    # ТОЛЬКО сработавшее (проигравшее остаётся pending) — внутри цикла
                    # ничего не отменяем, иначе можно словить set_result на отменённом
                    # future Telethon. Финальную отмену делает __aexit__ диалога.
                    resp = asyncio.ensure_future(conv.get_response(timeout=inner))
                    edit = asyncio.ensure_future(conv.get_edit(timeout=inner))

                    edit_deadline = time.monotonic() + edit_timeout
                    while True:
                        only_placeholder = bool(by_id) and all(
                            _looks_like_placeholder(t) for t in by_id.values()
                        )
                        if only_placeholder:
                            budget = edit_deadline - time.monotonic()
                        else:
                            budget = collect_seconds
                        if budget <= 0:
                            break

                        done, _pending = await asyncio.wait(
                            {resp, edit}, timeout=budget,
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        if not done:  # тишина дольше окна — бот «договорил»
                            break

                        progressed = False
                        for task in (resp, edit):  # приоритет: новое сообщение
                            if task not in done:
                                continue
                            try:
                                msg = task.result()
                            except (asyncio.TimeoutError, asyncio.CancelledError):
                                msg = None
                            if msg is not None:
                                _record(msg)
                                progressed = True
                            if task is resp:
                                resp = asyncio.ensure_future(conv.get_response(timeout=inner))
                            else:
                                edit = asyncio.ensure_future(conv.get_edit(timeout=inner))
                        if not progressed:  # обе задачи истекли по внутреннему таймауту
                            break
            except (PeerFloodError, FloodWaitError):
                logger.error("Userbot: Telegram rate-limit/flood при ask")
                raise
            finally:
                # Диалог уже вышел из контекста (__aexit__ снял футуры с диспатча и
                # отменил их) — здесь лишь подбираем отменённые задачи, чтобы asyncio
                # не ругался на «никто не забрал результат».
                for task in (resp, edit):
                    if task is None:
                        continue
                    task.cancel()
                    try:
                        await task
                    except BaseException:
                        pass

            texts = [by_id[i] for i in order if by_id[i]]
            meaningful = [t for t in texts if not _looks_like_placeholder(t)]
            replies = meaningful or texts
            logger.info(
                "Userbot: ← %s: %d сообщ. (%d после фильтра заглушек)",
                target or settings.target_bot, len(texts), len(replies),
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
