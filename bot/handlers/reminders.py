from __future__ import annotations

import re

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
from bot.repositories import (
    add_reminder,
    deactivate_reminder,
    get_user,
    has_consent,
    list_meds,
    list_reminders,
    update_settings,
)

router = Router(name="reminders")

TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


class RemFSM(StatesGroup):
    morning_time = State()
    evening_time = State()
    med_pick = State()
    med_time = State()


def _main_kb(has_morning: bool, has_evening: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=("✅ " if has_morning else "➕ ") + "Утреннее напоминание",
            callback_data="rem:morning",
        )],
        [InlineKeyboardButton(
            text=("✅ " if has_evening else "➕ ") + "Вечернее напоминание",
            callback_data="rem:evening",
        )],
        [InlineKeyboardButton(text="💊 Напоминание про лекарство", callback_data="rem:med")],
        [InlineKeyboardButton(text="📋 Список / удалить", callback_data="rem:list")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _hhmm_to_cron(t: str) -> str:
    h, m = t.split(":")
    return f"{int(h)} {int(m)}"


@router.message(Command("remind"))
async def cmd_remind(message: Message, state: FSMContext) -> None:
    if not await has_consent(message.from_user.id):
        await message.answer(texts.NEED_CONSENT); return
    await state.clear()
    reminders = await list_reminders(message.from_user.id)
    has_m = any(r["kind"] == "morning" for r in reminders)
    has_e = any(r["kind"] == "evening" for r in reminders)
    await message.answer("🔔 <b>Напоминания</b>\nВыберите действие:",
                         reply_markup=_main_kb(has_m, has_e))


@router.callback_query(F.data == "rem:morning")
async def on_rem_morning(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(RemFSM.morning_time)
    u = await get_user(cb.from_user.id)
    cur = u["morning_time"] if u else "09:00"
    await cb.message.answer(f"Время утреннего напоминания (HH:MM). Текущее: {cur}")
    await cb.answer()


@router.message(RemFSM.morning_time)
async def set_morning(message: Message, state: FSMContext, scheduler=None) -> None:
    t = (message.text or "").strip()
    if not TIME_RE.match(t):
        await message.answer("Формат HH:MM. Попробуйте ещё раз:"); return
    await update_settings(message.from_user.id, morning=t)
    # убираем старое morning-напоминание (если было) и добавляем новое
    for r in await list_reminders(message.from_user.id):
        if r["kind"] == "morning":
            await deactivate_reminder(r["id"], message.from_user.id)
            if scheduler is not None:
                scheduler.remove_reminder(r["id"])
    rid = await add_reminder(message.from_user.id, "morning", _hhmm_to_cron(t), None)
    if scheduler is not None:
        await scheduler.add_reminder(rid)
    await state.clear()
    await message.answer(f"✅ Утреннее напоминание настроено на {t}.")


@router.callback_query(F.data == "rem:evening")
async def on_rem_evening(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(RemFSM.evening_time)
    u = await get_user(cb.from_user.id)
    cur = u["evening_time"] if u else "21:00"
    await cb.message.answer(f"Время вечернего напоминания (HH:MM). Текущее: {cur}")
    await cb.answer()


@router.message(RemFSM.evening_time)
async def set_evening(message: Message, state: FSMContext, scheduler=None) -> None:
    t = (message.text or "").strip()
    if not TIME_RE.match(t):
        await message.answer("Формат HH:MM. Попробуйте ещё раз:"); return
    await update_settings(message.from_user.id, evening=t)
    for r in await list_reminders(message.from_user.id):
        if r["kind"] == "evening":
            await deactivate_reminder(r["id"], message.from_user.id)
            if scheduler is not None:
                scheduler.remove_reminder(r["id"])
    rid = await add_reminder(message.from_user.id, "evening", _hhmm_to_cron(t), None)
    if scheduler is not None:
        await scheduler.add_reminder(rid)
    await state.clear()
    await message.answer(f"✅ Вечернее напоминание настроено на {t}.")


# ---------- med reminders ----------

@router.callback_query(F.data == "rem:med")
async def on_rem_med(cb: CallbackQuery, state: FSMContext) -> None:
    meds = await list_meds(cb.from_user.id)
    if not meds:
        await cb.message.answer("Сначала добавьте препараты через /meds.")
        await cb.answer(); return
    rows = [[InlineKeyboardButton(
        text=m["name"] + (f" {m['dose']}" if m["dose"] else ""),
        callback_data=f"remmed:{m['id']}:{m['name']}",
    )] for m in meds]
    await state.set_state(RemFSM.med_pick)
    await cb.message.answer("Для какого препарата?",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@router.callback_query(RemFSM.med_pick, F.data.startswith("remmed:"))
async def on_remmed_pick(cb: CallbackQuery, state: FSMContext) -> None:
    _, _med_id, name = cb.data.split(":", 2)
    await state.update_data(med_name=name)
    await state.set_state(RemFSM.med_time)
    await cb.message.answer(f"Во сколько напоминать про «{name}»? HH:MM")
    await cb.answer()


@router.message(RemFSM.med_time)
async def set_med_time(message: Message, state: FSMContext, scheduler=None) -> None:
    t = (message.text or "").strip()
    if not TIME_RE.match(t):
        await message.answer("Формат HH:MM. Попробуйте ещё раз:"); return
    data = await state.get_data()
    name = data["med_name"]
    rid = await add_reminder(message.from_user.id, "med", _hhmm_to_cron(t), name)
    if scheduler is not None:
        await scheduler.add_reminder(rid)
    await state.clear()
    await message.answer(f"✅ Буду напоминать про «{name}» в {t}.")


# ---------- list / delete ----------

@router.callback_query(F.data == "rem:list")
async def on_rem_list(cb: CallbackQuery) -> None:
    reminders = await list_reminders(cb.from_user.id)
    if not reminders:
        await cb.message.answer("Напоминаний нет."); await cb.answer(); return
    lines = ["🔔 <b>Активные напоминания</b>:"]
    rows = []
    for r in reminders:
        h, m = r["cron"].split()
        time_str = f"{int(h):02d}:{int(m):02d}"
        if r["kind"] == "morning":
            lines.append(f"• Утро — {time_str}")
        elif r["kind"] == "evening":
            lines.append(f"• Вечер — {time_str}")
        else:
            lines.append(f"• 💊 {r['payload']} — {time_str}")
        rows.append([InlineKeyboardButton(
            text=f"🗑 #{r['id']}", callback_data=f"remdel:{r['id']}"
        )])
    await cb.message.answer("\n".join(lines),
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@router.callback_query(F.data.startswith("remdel:"))
async def on_remdel(cb: CallbackQuery, scheduler=None) -> None:
    rid = int(cb.data.split(":")[1])
    await deactivate_reminder(rid, cb.from_user.id)
    if scheduler is not None:
        scheduler.remove_reminder(rid)
    await cb.message.edit_text(cb.message.text + "\n\n🗑 Удалено.")
    await cb.answer()
