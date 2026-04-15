from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def scale_0_10(prefix: str) -> InlineKeyboardMarkup:
    row1 = [InlineKeyboardButton(text=str(i), callback_data=f"{prefix}:{i}") for i in range(0, 6)]
    row2 = [InlineKeyboardButton(text=str(i), callback_data=f"{prefix}:{i}") for i in range(6, 11)]
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2])


def bristol_keyboard(prefix: str) -> InlineKeyboardMarkup:
    row1 = [InlineKeyboardButton(text=str(i), callback_data=f"{prefix}:{i}") for i in range(1, 5)]
    row2 = [InlineKeyboardButton(text=str(i), callback_data=f"{prefix}:{i}") for i in range(5, 8)]
    row3 = [InlineKeyboardButton(text="Не было", callback_data=f"{prefix}:none")]
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2, row3])


def consent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Согласен, продолжить", callback_data="consent:ok"),
    ]])


def skip_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Пропустить", callback_data=f"{prefix}:skip"),
    ]])


def confirm_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да", callback_data=f"{prefix}:yes"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"{prefix}:no"),
    ]])


def stats_period_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Сегодня", callback_data="stats:today"),
            InlineKeyboardButton(text="7 дней", callback_data="stats:7"),
        ],
        [
            InlineKeyboardButton(text="30 дней", callback_data="stats:30"),
            InlineKeyboardButton(text="90 дней", callback_data="stats:90"),
        ],
    ])


def export_period_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="7 дней", callback_data="export:7"),
            InlineKeyboardButton(text="30 дней", callback_data="export:30"),
        ],
        [
            InlineKeyboardButton(text="90 дней", callback_data="export:90"),
            InlineKeyboardButton(text="1 год", callback_data="export:365"),
        ],
    ])


def add_more_meds_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➕ Ещё один", callback_data="medadd"),
        InlineKeyboardButton(text="✅ Готово", callback_data="meds:done"),
    ]])


def meds_dose_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Без дозы", callback_data="mdose:none"),
    ]])


def intake_dose_keyboard(default_dose: str | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if default_dose:
        rows.append([InlineKeyboardButton(
            text=f"✅ Как обычно: {default_dose}", callback_data="dose:default"
        )])
        rows.append([InlineKeyboardButton(
            text="✏️ Другая дозировка", callback_data="dose:prompt"
        )])
    else:
        rows.append([InlineKeyboardButton(
            text="✏️ Указать дозу", callback_data="dose:prompt"
        )])
    rows.append([InlineKeyboardButton(
        text="Без дозы", callback_data="dose:none"
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def intake_time_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕐 Сейчас", callback_data="itime:0")],
        [
            InlineKeyboardButton(text="15 мин назад", callback_data="itime:15"),
            InlineKeyboardButton(text="30 мин назад", callback_data="itime:30"),
        ],
        [
            InlineKeyboardButton(text="1 ч назад", callback_data="itime:60"),
            InlineKeyboardButton(text="2 ч назад", callback_data="itime:120"),
        ],
        [
            InlineKeyboardButton(text="4 ч назад", callback_data="itime:240"),
            InlineKeyboardButton(text="8 ч назад", callback_data="itime:480"),
        ],
        [InlineKeyboardButton(text="✏️ Другое время (HH:MM)", callback_data="itime:custom")],
    ])
