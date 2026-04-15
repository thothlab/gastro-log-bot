from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from bot.repositories import upsert_user


class UserUpsertMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is not None and not user.is_bot:
            await upsert_user(user.id, user.username, user.first_name)
        return await handler(event, data)


class ThrottleMiddleware(BaseMiddleware):
    """Простейший rate-limit: не чаще 1 апдейта в interval секунд на пользователя."""

    def __init__(self, interval: float = 0.5) -> None:
        self.interval = interval
        self._last: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is not None:
            now = time.monotonic()
            prev = self._last.get(user.id, 0.0)
            if now - prev < self.interval:
                return  # drop event
            self._last[user.id] = now
        return await handler(event, data)
