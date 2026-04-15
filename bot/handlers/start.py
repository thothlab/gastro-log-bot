from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.keyboards import consent_keyboard
from bot.repositories import get_user, set_consent

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await get_user(message.from_user.id)
    if user and user["consent_at"]:
        await message.answer(texts.CONSENT_OK)
    else:
        await message.answer(texts.START, reply_markup=consent_keyboard())


@router.callback_query(F.data == "consent:ok")
async def on_consent(cb: CallbackQuery) -> None:
    await set_consent(cb.from_user.id)
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
