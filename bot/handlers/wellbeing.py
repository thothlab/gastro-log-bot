from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot import texts
from bot.repositories import add_wellbeing, has_consent

router = Router(name="wellbeing")


class WellFSM(StatesGroup):
    text = State()


@router.message(Command("well"))
async def cmd_well(message: Message, state: FSMContext) -> None:
    if not await has_consent(message.from_user.id):
        await message.answer(texts.NEED_CONSENT)
        return
    await state.clear()
    await state.set_state(WellFSM.text)
    await message.answer(
        "📝 Опишите самочувствие одним сообщением — любым текстом, "
        "как вам сейчас. Чтобы отменить — /cancel."
    )


@router.message(WellFSM.text)
async def on_well_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пустое сообщение. Опишите самочувствие:")
        return
    await add_wellbeing(message.from_user.id, text)
    await state.clear()
    await message.answer("✅ Записано.")
