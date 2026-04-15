from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.keyboards import bristol_keyboard, scale_0_10, skip_keyboard
from bot.repositories import add_symptoms, has_consent

router = Router(name="symptoms")


class LogSymptomFSM(StatesGroup):
    pain = State()
    nausea = State()
    heartburn = State()
    bloating = State()
    stool = State()
    notes = State()


BRISTOL_HINT = (
    "🚽 <b>Стул (шкала Бристоля):</b>\n"
    "1 — отдельные твёрдые комки (запор)\n"
    "2 — комковатый «сосиской»\n"
    "3 — «сосиска» с трещинами\n"
    "4 — гладкая мягкая «сосиска» (норма)\n"
    "5 — мягкие кусочки с чёткими краями\n"
    "6 — рыхлые кусочки, кашицеобразный\n"
    "7 — водянистый (диарея)"
)


@router.message(Command("log"))
async def cmd_log(message: Message, state: FSMContext) -> None:
    if not await has_consent(message.from_user.id):
        await message.answer(texts.NEED_CONSENT)
        return
    await state.clear()
    await state.set_state(LogSymptomFSM.pain)
    await message.answer(
        "🤕 <b>Боль в животе</b> (0 — нет, 10 — невыносимая):",
        reply_markup=scale_0_10("pain"),
    )


@router.callback_query(LogSymptomFSM.pain, F.data.startswith("pain:"))
async def on_pain(cb: CallbackQuery, state: FSMContext) -> None:
    value = int(cb.data.split(":")[1])
    await state.update_data(pain=value)
    await state.set_state(LogSymptomFSM.nausea)
    await cb.message.edit_text(
        f"🤕 Боль: <b>{value}</b>\n\n🤢 <b>Тошнота</b> (0–10):",
        reply_markup=scale_0_10("nausea"),
    )
    await cb.answer()


@router.callback_query(LogSymptomFSM.nausea, F.data.startswith("nausea:"))
async def on_nausea(cb: CallbackQuery, state: FSMContext) -> None:
    value = int(cb.data.split(":")[1])
    await state.update_data(nausea=value)
    await state.set_state(LogSymptomFSM.heartburn)
    await cb.message.edit_text(
        f"🤢 Тошнота: <b>{value}</b>\n\n🔥 <b>Изжога</b> (0–10):",
        reply_markup=scale_0_10("heartburn"),
    )
    await cb.answer()


@router.callback_query(LogSymptomFSM.heartburn, F.data.startswith("heartburn:"))
async def on_heartburn(cb: CallbackQuery, state: FSMContext) -> None:
    value = int(cb.data.split(":")[1])
    await state.update_data(heartburn=value)
    await state.set_state(LogSymptomFSM.bloating)
    await cb.message.edit_text(
        f"🔥 Изжога: <b>{value}</b>\n\n💨 <b>Вздутие / газы</b> (0–10):",
        reply_markup=scale_0_10("bloating"),
    )
    await cb.answer()


@router.callback_query(LogSymptomFSM.bloating, F.data.startswith("bloating:"))
async def on_bloating(cb: CallbackQuery, state: FSMContext) -> None:
    value = int(cb.data.split(":")[1])
    await state.update_data(bloating=value)
    await state.set_state(LogSymptomFSM.stool)
    await cb.message.edit_text(
        f"💨 Вздутие: <b>{value}</b>\n\n{BRISTOL_HINT}",
        reply_markup=bristol_keyboard("stool"),
    )
    await cb.answer()


@router.callback_query(LogSymptomFSM.stool, F.data.startswith("stool:"))
async def on_stool(cb: CallbackQuery, state: FSMContext) -> None:
    raw = cb.data.split(":")[1]
    value = None if raw == "none" else int(raw)
    await state.update_data(stool=value)
    await state.set_state(LogSymptomFSM.notes)
    shown = "не было" if value is None else str(value)
    await cb.message.edit_text(
        f"🚽 Стул: <b>{shown}</b>\n\n📝 <b>Заметка</b> — напишите одним сообщением или пропустите.",
        reply_markup=skip_keyboard("notes"),
    )
    await cb.answer()


@router.callback_query(LogSymptomFSM.notes, F.data == "notes:skip")
async def on_notes_skip(cb: CallbackQuery, state: FSMContext) -> None:
    await _save(cb.from_user.id, state, notes=None)
    await cb.message.edit_text("✅ Запись сохранена.")
    await state.clear()
    await cb.answer()


@router.message(LogSymptomFSM.notes)
async def on_notes_text(message: Message, state: FSMContext) -> None:
    notes = (message.text or "").strip() or None
    await _save(message.from_user.id, state, notes=notes)
    await message.answer("✅ Запись сохранена.")
    await state.clear()


async def _save(tg_id: int, state: FSMContext, *, notes: str | None) -> None:
    data = await state.get_data()
    await add_symptoms(
        tg_id,
        pain=data.get("pain"),
        nausea=data.get("nausea"),
        heartburn=data.get("heartburn"),
        bloating=data.get("bloating"),
        stool=data.get("stool"),
        notes=notes,
    )
