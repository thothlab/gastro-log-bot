from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.keyboards import consent_keyboard
from bot.repositories import (
    add_reminder,
    get_user,
    list_reminders,
    set_consent,
)

router = Router(name="start")


_DEFAULT_REMINDERS = [
    ("morning", "07:30"),
    ("afternoon", "15:00"),
    ("evening", "21:00"),
]


def _hhmm_to_cron(hhmm: str) -> str:
    h, m = hhmm.split(":")
    return f"{int(h)} {int(m)}"


async def _ensure_default_reminders(tg_id: int, scheduler) -> None:
    existing = {r["kind"] for r in await list_reminders(tg_id, only_active=False)}
    for kind, hhmm in _DEFAULT_REMINDERS:
        if kind in existing:
            continue
        rid = await add_reminder(tg_id, kind, _hhmm_to_cron(hhmm), None)
        if scheduler is not None:
            await scheduler.add_reminder(rid)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, scheduler=None) -> None:
    await state.clear()
    user = await get_user(message.from_user.id)
    if user and user["consent_at"]:
        await _ensure_default_reminders(message.from_user.id, scheduler)
        await message.answer(texts.CONSENT_OK)
    else:
        await message.answer(texts.START, reply_markup=consent_keyboard())


@router.callback_query(F.data == "consent:ok")
async def on_consent(cb: CallbackQuery, scheduler=None) -> None:
    await set_consent(cb.from_user.id)
    await _ensure_default_reminders(cb.from_user.id, scheduler)
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer(texts.CONSENT_OK)
    await cb.answer("Готово")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(texts.HELP)


@router.message(Command("privacy"))
async def cmd_privacy(message: Message) -> None:
    await message.answer(texts.PRIVACY)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        await state.clear()
        await message.answer(texts.CANCEL)
    else:
        await message.answer(texts.NOTHING_TO_CANCEL)
