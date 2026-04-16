from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.keyboards import food_time_keyboard, skip_keyboard
from bot.repositories import add_food, get_user, has_consent

router = Router(name="food")

TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


class FoodFSM(StatesGroup):
    description = State()
    time = State()
    notes = State()


@router.message(Command("food"))
async def cmd_food(message: Message, state: FSMContext) -> None:
    if not await has_consent(message.from_user.id):
        await message.answer(texts.NEED_CONSENT); return
    await state.clear()
    await state.set_state(FoodFSM.description)
    await message.answer("🍽 Что вы съели / выпили? Напишите одним сообщением.")


@router.message(FoodFSM.description)
async def on_food_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пустое сообщение. Опишите приём пищи:"); return
    await state.update_data(description=text)
    await state.set_state(FoodFSM.time)
    await message.answer("🕐 Когда был приём пищи?", reply_markup=food_time_keyboard())


# ---- time step ----

def _compute_ts_offset(minutes: int) -> str:
    dt = datetime.now(tz=timezone.utc) - timedelta(minutes=minutes)
    return dt.isoformat(timespec="seconds")


def _parse_custom_time(hhmm: str, user_tz: str) -> str | None:
    m = TIME_RE.match(hhmm)
    if not m:
        return None
    try:
        tz = ZoneInfo(user_tz)
    except Exception:
        tz = ZoneInfo("Europe/Moscow")
    now_local = datetime.now(tz=tz)
    h, minute = int(m.group(1)), int(m.group(2))
    local_dt = now_local.replace(hour=h, minute=minute, second=0, microsecond=0)
    if local_dt > now_local:
        local_dt -= timedelta(days=1)
    return local_dt.astimezone(timezone.utc).isoformat(timespec="seconds")


async def _ask_notes(target: Message, state: FSMContext, ts_iso: str) -> None:
    await state.update_data(ts=ts_iso)
    await state.set_state(FoodFSM.notes)
    await target.answer(
        "Как самочувствие после еды? Напишите текстом или нажмите «Пропустить».",
        reply_markup=skip_keyboard("fnotes"),
    )


@router.callback_query(FoodFSM.time, F.data.startswith("ftime:"))
async def on_food_time_pick(cb: CallbackQuery, state: FSMContext) -> None:
    raw = cb.data.split(":", 1)[1]
    if raw == "custom":
        await cb.message.answer(
            "Во сколько был приём пищи? Формат <code>HH:MM</code>\n"
            "(если время ещё не наступило сегодня — посчитаю вчерашним)"
        )
        await cb.answer(); return
    minutes = int(raw)
    ts_iso = _compute_ts_offset(minutes)
    await _ask_notes(cb.message, state, ts_iso)
    await cb.answer()


@router.message(FoodFSM.time)
async def on_food_time_text(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    user = await get_user(message.from_user.id)
    tz = (user and user["tz"]) or "Europe/Moscow"
    ts_iso = _parse_custom_time(raw, tz)
    if ts_iso is None:
        await message.answer(
            "Не распознал время. Формат <code>HH:MM</code>, например <code>14:30</code>. "
            "Или выберите кнопкой выше."
        )
        return
    await _ask_notes(message, state, ts_iso)


# ---- notes step ----

async def _save_food(tg_id: int, state: FSMContext, target: Message,
                     notes: str | None) -> None:
    data = await state.get_data()
    ts_iso = data["ts"]
    description = data["description"]
    await add_food(tg_id, description, notes, ts=ts_iso)

    user = await get_user(tg_id)
    tz_name = (user and user["tz"]) or "Europe/Moscow"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Europe/Moscow")
    local_time = datetime.fromisoformat(ts_iso).astimezone(tz).strftime("%H:%M")

    await state.clear()
    summary = f"✅ Записано: <b>{description}</b>\n🕐 Время: {local_time}"
    if notes:
        summary += f"\n📝 Самочувствие: {notes}"
    await target.answer(summary)


@router.callback_query(FoodFSM.notes, F.data == "fnotes:skip")
async def on_food_notes_skip(cb: CallbackQuery, state: FSMContext) -> None:
    await _save_food(cb.from_user.id, state, cb.message, notes=None)
    await cb.answer()


@router.message(FoodFSM.notes)
async def on_food_notes_text(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    notes = raw if raw else None
    await _save_food(message.from_user.id, state, message, notes)
