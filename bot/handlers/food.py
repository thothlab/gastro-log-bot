from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot import texts
from bot.repositories import add_food, has_consent

router = Router(name="food")


class FoodFSM(StatesGroup):
    description = State()


@router.message(Command("food"))
async def cmd_food(message: Message, state: FSMContext) -> None:
    if not await has_consent(message.from_user.id):
        await message.answer(texts.NEED_CONSENT); return
    await state.clear()
    await state.set_state(FoodFSM.description)
    await message.answer(
        "🍽 Что вы съели / выпили? Напишите одним сообщением.\n"
        "Можно добавить самочувствие после еды в скобках."
    )


@router.message(FoodFSM.description)
async def on_food_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пустое сообщение. Опишите приём пищи:"); return
    await add_food(message.from_user.id, text, None)
    await state.clear()
    await message.answer("✅ Записано.")
