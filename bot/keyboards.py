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
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="7 дней", callback_data="stats:7"),
        InlineKeyboardButton(text="30 дней", callback_data="stats:30"),
        InlineKeyboardButton(text="90 дней", callback_data="stats:90"),
    ]])
