from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot.config import settings
from bot.db import init_db
from bot.handlers import food, meds, reminders, settings_ as settings_handlers
from bot.handlers import start, stats, symptoms
from bot.middlewares import ThrottleMiddleware, UserUpsertMiddleware
from bot.scheduler import ReminderScheduler


async def set_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="log", description="Записать симптомы"),
        BotCommand(command="med", description="Отметить приём лекарства"),
        BotCommand(command="meds", description="Список препаратов"),
        BotCommand(command="food", description="Записать еду"),
        BotCommand(command="remind", description="Напоминания"),
        BotCommand(command="stats", description="Статистика и график"),
        BotCommand(command="export", description="Выгрузка в файл"),
        BotCommand(command="settings", description="Часовой пояс и время"),
        BotCommand(command="privacy", description="Политика хранения"),
        BotCommand(command="delete", description="Удалить мои данные"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="cancel", description="Отменить анкету"),
    ])


async def main() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    await init_db()

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.outer_middleware(UserUpsertMiddleware())
    dp.update.middleware(ThrottleMiddleware(interval=0.4))

    dp.include_router(start.router)
    dp.include_router(symptoms.router)
    dp.include_router(meds.router)
    dp.include_router(food.router)
    dp.include_router(reminders.router)
    dp.include_router(stats.router)
    dp.include_router(settings_handlers.router)

    scheduler = ReminderScheduler(bot)
    await scheduler.start()

    await set_bot_commands(bot)

    try:
        await dp.start_polling(
            bot,
            scheduler=scheduler,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        await scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
