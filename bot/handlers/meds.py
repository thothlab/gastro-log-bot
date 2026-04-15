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
    add_intake,
    add_med,
    deactivate_med,
    get_med,
    has_consent,
    list_meds,
)

router = Router(name="meds")


class AddMedFSM(StatesGroup):
    name = State()
    dose = State()


class IntakeFSM(StatesGroup):
    pick = State()
    custom_name = State()
    dose = State()


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
    await message.answer("💊 <b>Ваши препараты</b>\nНажмите 🗑, чтобы удалить из списка.",
                         reply_markup=_meds_list_kb(meds))


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
        "Дозировка? (например: 20 мг) Или отправьте «-» чтобы пропустить."
    )


@router.message(AddMedFSM.dose)
async def add_dose(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    dose = None if raw in ("-", "—", "") else raw
    data = await state.get_data()
    await add_med(message.from_user.id, data["name"], dose)
    await state.clear()
    await message.answer(f"✅ Добавлено: <b>{data['name']}</b>" + (f" — {dose}" if dose else ""))


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
    rows.append([InlineKeyboardButton(text="✏️ Другое (ввести вручную)", callback_data="intake:custom")])
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
    await state.update_data(med_id=med["id"], med_name=med["name"], default_dose=med["dose"])
    await state.set_state(IntakeFSM.dose)
    dose_hint = f" (Enter — оставить {med['dose']})" if med["dose"] else ""
    await cb.message.edit_text(
        f"Препарат: <b>{med['name']}</b>\nДозировка?{dose_hint}\n"
        f"Отправьте «-» если без дозы, или «=» чтобы использовать сохранённую."
    )
    await cb.answer()


@router.message(IntakeFSM.custom_name)
async def on_intake_custom_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Пустое название. Введите ещё раз:"); return
    await state.update_data(med_id=None, med_name=name, default_dose=None)
    await state.set_state(IntakeFSM.dose)
    await message.answer("Дозировка? («-» чтобы пропустить)")


@router.message(IntakeFSM.dose)
async def on_intake_dose(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    data = await state.get_data()
    if raw == "=":
        dose = data.get("default_dose")
    elif raw in ("-", "—", ""):
        dose = None
    else:
        dose = raw
    await add_intake(
        message.from_user.id,
        med_id=data.get("med_id"),
        med_name=data["med_name"],
        dose=dose,
        notes=None,
    )
    await state.clear()
    await message.answer(f"✅ Записано: {data['med_name']}" + (f" — {dose}" if dose else ""))
