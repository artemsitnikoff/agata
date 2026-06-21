from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Конфигурация agata.

    Все значения берутся из .env / переменных окружения. API_ID/API_HASH по
    умолчанию — личное приложение Telegram (те же, что в gen_session.py).
    """

    # ── Telethon userbot (личный аккаунт, от которого пишем боту) ──────────
    telethon_api_id: int = 33988209
    telethon_api_hash: str = "e88485f4f18cd2bee1f8552c655a9893"
    # StringSession — сгенерировать через `python gen_session.py`
    telethon_session: str = ""

    # ── Целевой бот, которому userbot пишет и от которого ждёт ответ ───────
    # @username, числовой id или t.me-ссылка.
    target_bot: str = "@zeta963cy3c_bot"

    # ── Поведение «спросить бота» ─────────────────────────────────────────
    # Сколько ждём ПЕРВЫЙ ответ бота (сек).
    ask_timeout: float = 60.0
    # После первого ответа собираем доп. сообщения, пока бот молчит дольше
    # этого окна (сек). Многие боты дробят ответ на несколько сообщений.
    ask_collect_seconds: float = 3.0

    # ── Безопасность API ──────────────────────────────────────────────────
    # Общий секрет: запросы должны слать заголовок X-API-Token с этим значением.
    # Пусто = аутентификация выключена (только для локальной разработки!).
    api_token: str = ""

    # ── Пасхалка «ситников» (как в ArkadyJarvis) ──────────────────────────
    # На входящее сообщение со словом «ситников» личный аккаунт салютует
    # «Аве, Цезарь!» + случайной цитатой Сенеки. 0 = выключено.
    enable_seneca: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
