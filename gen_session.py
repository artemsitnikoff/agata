#!/usr/bin/env python3
"""Сгенерировать TELETHON_SESSION для userbot agata.

Запусти на машине, где можешь получить код входа на аккаунт userbot:

    pip install telethon
    python gen_session.py

Введи телефон (+7...), код из Telegram, при 2FA — пароль.
В конце скопируй строку TELETHON_SESSION=... в .env на сервере, затем:
    docker compose up -d --force-recreate
"""
import asyncio
import os

from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ.get("TELETHON_API_ID", "33988209"))
API_HASH = os.environ.get("TELETHON_API_HASH", "e88485f4f18cd2bee1f8552c655a9893")


async def main() -> None:
    print("Создаём сессию для userbot…")
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.start()  # спросит телефон, код, при 2FA — пароль
    me = await client.get_me()
    print(f"\n✅ Авторизован как @{me.username} (id={me.id})")
    print("\n=== Вставь эту строку в .env на сервере ===")
    print(f"TELETHON_SESSION={client.session.save()}")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
