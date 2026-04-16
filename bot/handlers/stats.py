from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot import texts
from bot.keyboards import export_period_keyboard, stats_period_keyboard
from bot.repositories import get_user, has_consent
from bot.reports import build_chart, build_export_zip, build_text_summary

router = Router(name="stats")


_PERIOD_LABELS = {
    "today": "за сегодня",
    "7": "за 7 дней",
    "30": "за 30 дней",
    "90": "за 90 дней",
}


def _period_since_utc(user_tz: str, spec: str) -> str:
    try:
        tz = ZoneInfo(user_tz)
    except Exception:
        tz = ZoneInfo("Europe/Moscow")
    now_local = datetime.now(tz=tz)
    if spec == "today":
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        days = int(spec)
        start_local = now_local - timedelta(days=days)
    return start_local.astimezone(timezone.utc).isoformat(timespec="seconds")


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not await has_consent(message.from_user.id):
        await message.answer(texts.NEED_CONSENT); return
    await message.answer("За какой период?", reply_markup=stats_period_keyboard())


@router.callback_query(F.data.startswith("stats:"))
async def on_stats_period(cb: CallbackQuery) -> None:
    spec = cb.data.split(":", 1)[1]
    label = _PERIOD_LABELS.get(spec)
    if label is None:
        await cb.answer("Неизвестный период", show_alert=True); return
    await cb.answer("Готовлю сводку…")
    user = await get_user(cb.from_user.id)
    tz = (user and user["tz"]) or "Europe/Moscow"
    since = _period_since_utc(tz, spec)
    summary = await build_text_summary(cb.from_user.id, since, label, tz_name=tz)
    chart = await build_chart(cb.from_user.id, since, label)
    if chart is not None:
        if len(summary) <= 1024:
            await cb.message.answer_photo(
                BufferedInputFile(chart, filename=f"stats_{spec}.png"),
                caption=summary,
            )
        else:
            await cb.message.answer_photo(
                BufferedInputFile(chart, filename=f"stats_{spec}.png"),
            )
            await cb.message.answer(summary)
    else:
        await cb.message.answer(summary)


_EXPORT_LABELS = {
    "7": ("7 дней", "7d"),
    "30": ("30 дней", "30d"),
    "90": ("90 дней", "90d"),
    "365": ("1 год", "365d"),
}


@router.message(Command("export"))
async def cmd_export(message: Message) -> None:
    if not await has_consent(message.from_user.id):
        await message.answer(texts.NEED_CONSENT); return
    await message.answer(
        "📦 Выгрузка в файл\nЗа какой период собрать данные?",
        reply_markup=export_period_keyboard(),
    )


@router.callback_query(F.data.startswith("export:"))
async def on_export_period(cb: CallbackQuery) -> None:
    spec = cb.data.split(":", 1)[1]
    label = _EXPORT_LABELS.get(spec)
    if label is None:
        await cb.answer("Неизвестный период", show_alert=True); return
    human, slug = label
    await cb.answer("Собираю файл…")
    user = await get_user(cb.from_user.id)
    tz = (user and user["tz"]) or "Europe/Moscow"
    since = _period_since_utc(tz, spec)
    data = await build_export_zip(cb.from_user.id, since, f"за {human}", tz)
    await cb.message.answer_document(
        BufferedInputFile(data, filename=f"gastrobot_{slug}.zip"),
        caption=(
            f"📦 Данные за {human}.\n"
            "• <b>diary.txt</b> — дневник в читаемом виде (удобно смотреть на телефоне)\n"
            "• <b>*.csv</b> — таблицы для Excel/выгрузки врачу\n\n"
            "💡 Нажмите и удерживайте файл → <b>Переслать</b>, "
            "чтобы отправить врачу."
        ),
    )
