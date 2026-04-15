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
from bot.keyboards import confirm_keyboard
from bot.repositories import delete_user, get_user, has_consent, update_settings

router = Router(name="settings")

TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
POPULAR_TZ = [
    "Europe/Moscow", "Europe/Kaliningrad", "Europe/Samara",
    "Asia/Yekaterinburg", "Asia/Omsk", "Asia/Krasnoyarsk",
    "Asia/Irkutsk", "Asia/Yakutsk", "Asia/Vladivostok",
    "Asia/Almaty", "Asia/Tashkent", "Europe/Kiev", "Europe/Minsk",
]


class SettingsFSM(StatesGroup):
    tz_custom = State()
    morning = State()
    evening = State()


def _settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="set:tz")],
        [InlineKeyboardButton(text="🌅 Время утреннего напоминания", callback_data="set:morning")],
        [InlineKeyboardButton(text="🌙 Время вечернего напоминания", callback_data="set:evening")],
    ])


def _tz_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=tz, callback_data=f"tz:{tz}")] for tz in POPULAR_TZ]
    rows.append([InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="tz:custom")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext) -> None:
    if not await has_consent(message.from_user.id):
        await message.answer(texts.NEED_CONSENT); return
    await state.clear()
    u = await get_user(message.from_user.id)
    assert u is not None
    await message.answer(
        f"⚙️ <b>Текущие настройки</b>\n"
        f"• Часовой пояс: <code>{u['tz']}</code>\n"
        f"• Утро: <code>{u['morning_time']}</code>\n"
        f"• Вечер: <code>{u['evening_time']}</code>",
        reply_markup=_settings_kb(),
    )


@router.callback_query(F.data == "set:tz")
async def on_set_tz(cb: CallbackQuery) -> None:
    await cb.message.answer("Выберите часовой пояс:", reply_markup=_tz_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("tz:"))
async def on_tz_pick(cb: CallbackQuery, state: FSMContext, scheduler=None) -> None:
    value = cb.data.split(":", 1)[1]
    if value == "custom":
        await state.set_state(SettingsFSM.tz_custom)
        await cb.message.answer("Введите часовой пояс (напр. Europe/Moscow):")
        await cb.answer(); return
    await update_settings(cb.from_user.id, tz=value)
    if scheduler is not None:
        await scheduler.reload_user(cb.from_user.id)
    await cb.message.answer(f"✅ Часовой пояс: <code>{value}</code>")
    await cb.answer()


@router.message(SettingsFSM.tz_custom)
async def on_tz_custom(message: Message, state: FSMContext, scheduler=None) -> None:
    tz = (message.text or "").strip()
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(tz)
    except Exception:
        await message.answer("Неизвестный часовой пояс. Пример: Europe/Moscow"); return
    await update_settings(message.from_user.id, tz=tz)
    if scheduler is not None:
        await scheduler.reload_user(message.from_user.id)
    await state.clear()
    await message.answer(f"✅ Часовой пояс: <code>{tz}</code>")


@router.callback_query(F.data == "set:morning")
async def on_set_morning(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsFSM.morning)
    await cb.message.answer("Введите время утреннего напоминания (HH:MM), например 09:00:")
    await cb.answer()


@router.callback_query(F.data == "set:evening")
async def on_set_evening(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsFSM.evening)
    await cb.message.answer("Введите время вечернего напоминания (HH:MM), например 21:00:")
    await cb.answer()


@router.message(SettingsFSM.morning)
async def on_morning(message: Message, state: FSMContext, scheduler=None) -> None:
    t = (message.text or "").strip()
    if not TIME_RE.match(t):
        await message.answer("Формат HH:MM. Попробуйте снова:"); return
    await update_settings(message.from_user.id, morning=t)
    if scheduler is not None:
        await scheduler.reload_user(message.from_user.id)
    await state.clear()
    await message.answer(f"✅ Утро: {t}")


@router.message(SettingsFSM.evening)
async def on_evening(message: Message, state: FSMContext, scheduler=None) -> None:
    t = (message.text or "").strip()
    if not TIME_RE.match(t):
        await message.answer("Формат HH:MM. Попробуйте снова:"); return
    await update_settings(message.from_user.id, evening=t)
    if scheduler is not None:
        await scheduler.reload_user(message.from_user.id)
    await state.clear()
    await message.answer(f"✅ Вечер: {t}")


# ---------- /delete ----------

@router.message(Command("delete"))
async def cmd_delete(message: Message) -> None:
    await message.answer(
        "⚠️ Удалить <b>все</b> ваши записи (симптомы, лекарства, еда, напоминания)?\n"
        "Действие необратимо.",
        reply_markup=confirm_keyboard("del"),
    )


@router.callback_query(F.data == "del:no")
async def on_del_no(cb: CallbackQuery) -> None:
    await cb.message.edit_text("Отменено. Ваши данные сохранены.")
    await cb.answer()


@router.callback_query(F.data == "del:yes")
async def on_del_yes(cb: CallbackQuery, scheduler=None) -> None:
    if scheduler is not None:
        await scheduler.remove_user(cb.from_user.id)
    await delete_user(cb.from_user.id)
    await cb.message.edit_text("🗑 Все ваши данные удалены. Если захотите вернуться — /start.")
    await cb.answer()
