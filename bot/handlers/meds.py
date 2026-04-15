from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot import texts
from bot.keyboards import (
    add_more_meds_keyboard,
    intake_dose_keyboard,
    intake_time_keyboard,
    meds_dose_keyboard,
)
from bot.repositories import (
    add_intake,
    add_med,
    deactivate_med,
    get_med,
    get_user,
    has_consent,
    list_meds,
)

router = Router(name="meds")

TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


class AddMedFSM(StatesGroup):
    name = State()
    dose = State()


class IntakeFSM(StatesGroup):
    pick = State()
    custom_name = State()
    dose = State()
    time = State()


# ---------- /meds: manage list ----------

def _meds_list_kb(meds) -> InlineKeyboardMarkup:
    rows = []
    for m in meds:
        label = m["name"] + (f" — {m['dose']}" if m["dose"] else "")
        rows.append([
            InlineKeyboardButton(text=f"🗑 {label}", callback_data=f"meddel:{m['id']}")
        ])
    rows.append([InlineKeyboardButton(text="➕ Добавить", callback_data="medadd")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_meds_list(target: Message | CallbackQuery) -> None:
    message = target.message if isinstance(target, CallbackQuery) else target
    tg_id = target.from_user.id
    meds = await list_meds(tg_id)
    if not meds:
        await message.answer(
            "Список пуст.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="➕ Добавить", callback_data="medadd"),
            ]]),
        )
        return
    await message.answer(
        "💊 <b>Ваши препараты</b>\nНажмите 🗑, чтобы удалить из списка.",
        reply_markup=_meds_list_kb(meds),
    )


@router.message(Command("meds"))
async def cmd_meds(message: Message, state: FSMContext) -> None:
    if not await has_consent(message.from_user.id):
        await message.answer(texts.NEED_CONSENT); return
    await state.clear()
    meds = await list_meds(message.from_user.id)
    if not meds:
        await message.answer(
            "У вас пока нет препаратов в списке. Добавим?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="➕ Добавить", callback_data="medadd"),
            ]]),
        )
        return
    await message.answer(
        "💊 <b>Ваши препараты</b>\nНажмите 🗑, чтобы удалить из списка.",
        reply_markup=_meds_list_kb(meds),
    )


@router.callback_query(F.data == "medadd")
async def on_med_add(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddMedFSM.name)
    await cb.message.answer("Название препарата? (например: Омепразол)")
    await cb.answer()


@router.message(AddMedFSM.name)
async def add_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Пустое название. Введите ещё раз:"); return
    await state.update_data(name=name)
    await state.set_state(AddMedFSM.dose)
    await message.answer(
        f"<b>{name}</b>\nДозировка? Введите текстом (например, <code>20 мг</code>) "
        "или нажмите кнопку.",
        reply_markup=meds_dose_keyboard(),
    )


async def _finish_add_med(tg_id: int, state: FSMContext, message: Message,
                          dose: str | None) -> None:
    data = await state.get_data()
    name = data["name"]
    await add_med(tg_id, name, dose)
    await state.clear()
    summary = f"✅ Добавлено: <b>{name}</b>" + (f" — {dose}" if dose else "")
    await message.answer(
        f"{summary}\n\nДобавить ещё один препарат?",
        reply_markup=add_more_meds_keyboard(),
    )


@router.callback_query(AddMedFSM.dose, F.data == "mdose:none")
async def add_dose_none(cb: CallbackQuery, state: FSMContext) -> None:
    await _finish_add_med(cb.from_user.id, state, cb.message, dose=None)
    await cb.answer()


@router.message(AddMedFSM.dose)
async def add_dose_text(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    dose = None if raw in ("-", "—", "") else raw
    await _finish_add_med(message.from_user.id, state, message, dose=dose)


@router.callback_query(F.data == "meds:done")
async def on_meds_done(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _show_meds_list(cb)
    await cb.answer()


@router.callback_query(F.data.startswith("meddel:"))
async def on_med_del(cb: CallbackQuery) -> None:
    med_id = int(cb.data.split(":")[1])
    await deactivate_med(med_id, cb.from_user.id)
    meds = await list_meds(cb.from_user.id)
    if meds:
        await cb.message.edit_reply_markup(reply_markup=_meds_list_kb(meds))
    else:
        await cb.message.edit_text(
            "Список пуст.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="➕ Добавить", callback_data="medadd"),
            ]]),
        )
    await cb.answer("Удалено")


# ---------- /med: log intake ----------

def _pick_med_kb(meds) -> InlineKeyboardMarkup:
    rows = []
    for m in meds:
        label = m["name"] + (f" {m['dose']}" if m["dose"] else "")
        rows.append([InlineKeyboardButton(text=label, callback_data=f"intake:{m['id']}")])
    rows.append([InlineKeyboardButton(
        text="✏️ Другое (ввести вручную)", callback_data="intake:custom"
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("med"))
async def cmd_med(message: Message, state: FSMContext) -> None:
    if not await has_consent(message.from_user.id):
        await message.answer(texts.NEED_CONSENT); return
    await state.clear()
    meds = await list_meds(message.from_user.id)
    if not meds:
        await state.set_state(IntakeFSM.custom_name)
        await message.answer(
            "У вас нет сохранённых препаратов. Введите название препарата вручную "
            "(позже добавьте их через /meds):"
        )
        return
    await state.set_state(IntakeFSM.pick)
    await message.answer("Какой препарат приняли?", reply_markup=_pick_med_kb(meds))


async def _ask_dose(message: Message, state: FSMContext, med_name: str,
                    default_dose: str | None) -> None:
    await state.set_state(IntakeFSM.dose)
    await message.answer(
        f"Препарат: <b>{med_name}</b>\nДозировка?",
        reply_markup=intake_dose_keyboard(default_dose),
    )


@router.callback_query(IntakeFSM.pick, F.data.startswith("intake:"))
async def on_intake_pick(cb: CallbackQuery, state: FSMContext) -> None:
    raw = cb.data.split(":")[1]
    if raw == "custom":
        await state.set_state(IntakeFSM.custom_name)
        await cb.message.edit_text("Введите название препарата:")
        await cb.answer(); return
    med_id = int(raw)
    med = await get_med(med_id, cb.from_user.id)
    if not med:
        await cb.answer("Не найдено", show_alert=True); return
    await state.update_data(med_id=med["id"], med_name=med["name"],
                            default_dose=med["dose"])
    await _ask_dose(cb.message, state, med["name"], med["dose"])
    await cb.answer()


@router.message(IntakeFSM.custom_name)
async def on_intake_custom_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Пустое название. Введите ещё раз:"); return
    await state.update_data(med_id=None, med_name=name, default_dose=None)
    await _ask_dose(message, state, name, None)


# ---- dose step ----

async def _ask_time(message: Message, state: FSMContext) -> None:
    await state.set_state(IntakeFSM.time)
    data = await state.get_data()
    dose = data.get("dose")
    dose_line = f" — {dose}" if dose else ""
    await message.answer(
        f"Дозировка: <b>{dose or 'без дозы'}</b>{dose_line and ''}\n\nКогда приняли?",
        reply_markup=intake_time_keyboard(),
    )


@router.callback_query(IntakeFSM.dose, F.data == "dose:default")
async def on_dose_default(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.update_data(dose=data.get("default_dose"))
    await _ask_time(cb.message, state)
    await cb.answer()


@router.callback_query(IntakeFSM.dose, F.data == "dose:none")
async def on_dose_none(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(dose=None)
    await _ask_time(cb.message, state)
    await cb.answer()


@router.callback_query(IntakeFSM.dose, F.data == "dose:prompt")
async def on_dose_prompt(cb: CallbackQuery) -> None:
    await cb.message.answer("Введите дозировку текстом (например, <code>20 мг</code>):")
    await cb.answer()


@router.message(IntakeFSM.dose)
async def on_dose_text(message: Message, state: FSMContext) -> None:
    dose = (message.text or "").strip()
    if not dose:
        await message.answer("Пустая строка. Введите дозировку или воспользуйтесь кнопками.")
        return
    await state.update_data(dose=dose)
    await _ask_time(message, state)


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
    if local_dt > now_local:  # время ещё не наступило сегодня → считаем вчера
        local_dt -= timedelta(days=1)
    return local_dt.astimezone(timezone.utc).isoformat(timespec="seconds")


async def _save_intake_and_reply(cb_or_msg, tg_id: int, state: FSMContext,
                                 ts_iso: str) -> None:
    data = await state.get_data()
    dose = data.get("dose")
    med_name = data["med_name"]
    await add_intake(
        tg_id,
        med_id=data.get("med_id"),
        med_name=med_name,
        dose=dose,
        notes=None,
        ts=ts_iso,
    )
    user = await get_user(tg_id)
    tz_name = (user and user["tz"]) or "Europe/Moscow"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Europe/Moscow")
    local_time = datetime.fromisoformat(ts_iso).astimezone(tz).strftime("%H:%M")
    await state.clear()
    summary = f"✅ Записано: <b>{med_name}</b>"
    if dose:
        summary += f" — {dose}"
    summary += f"\n🕐 Время: {local_time}"
    target = cb_or_msg.message if isinstance(cb_or_msg, CallbackQuery) else cb_or_msg
    await target.answer(summary)


@router.callback_query(IntakeFSM.time, F.data.startswith("itime:"))
async def on_time_pick(cb: CallbackQuery, state: FSMContext) -> None:
    raw = cb.data.split(":", 1)[1]
    if raw == "custom":
        await cb.message.answer(
            "Во сколько сегодня вы приняли препарат? Формат <code>HH:MM</code>\n"
            "(если время ещё не наступило сегодня — посчитаю вчерашним)"
        )
        await cb.answer(); return
    minutes = int(raw)
    ts_iso = _compute_ts_offset(minutes)
    await _save_intake_and_reply(cb, cb.from_user.id, state, ts_iso)
    await cb.answer()


@router.message(IntakeFSM.time)
async def on_time_text(message: Message, state: FSMContext) -> None:
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
    await _save_intake_and_reply(message, message.from_user.id, state, ts_iso)
