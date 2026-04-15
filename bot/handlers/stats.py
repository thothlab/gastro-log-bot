from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot import texts
from bot.keyboards import stats_period_keyboard
from bot.repositories import has_consent
from bot.reports import build_chart, build_csv_zip, build_text_summary

router = Router(name="stats")


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not await has_consent(message.from_user.id):
        await message.answer(texts.NEED_CONSENT); return
    await message.answer("За какой период?", reply_markup=stats_period_keyboard())


@router.callback_query(F.data.startswith("stats:"))
async def on_stats_period(cb: CallbackQuery) -> None:
    days = int(cb.data.split(":")[1])
    await cb.answer("Готовлю сводку…")
    summary = await build_text_summary(cb.from_user.id, days)
    chart = await build_chart(cb.from_user.id, days)
    if chart is not None:
        await cb.message.answer_photo(
            BufferedInputFile(chart, filename=f"stats_{days}d.png"),
            caption=summary,
        )
    else:
        await cb.message.answer(summary)


@router.message(Command("export"))
async def cmd_export(message: Message) -> None:
    if not await has_consent(message.from_user.id):
        await message.answer(texts.NEED_CONSENT); return
    data = await build_csv_zip(message.from_user.id, 365)
    await message.answer_document(
        BufferedInputFile(data, filename="gastrobot_export.zip"),
        caption="📦 CSV-архив за последние 365 дней.",
    )
