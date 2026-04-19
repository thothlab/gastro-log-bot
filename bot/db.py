from pathlib import Path

import aiosqlite

from bot.config import settings

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


async def init_db() -> None:
    settings.db_file.parent.mkdir(parents=True, exist_ok=True)
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    async with aiosqlite.connect(settings.db_file) as conn:
        await conn.executescript(sql)
        await _migrate(conn)
        await conn.commit()


async def _migrate(conn: aiosqlite.Connection) -> None:
    """Инкрементальные миграции для существующих БД.

    `CREATE TABLE IF NOT EXISTS` из schema.sql не добавляет колонки в уже
    созданные таблицы — поэтому дополняем руками.
    """
    cur = await conn.execute("PRAGMA table_info(reminders)")
    cols = {row[1] for row in await cur.fetchall()}
    if "created_at" not in cols:
        # SQLite не принимает CURRENT_TIMESTAMP как default в ALTER TABLE —
        # добавляем nullable-колонку и засыпаем существующие строки «сейчас».
        await conn.execute("ALTER TABLE reminders ADD COLUMN created_at TEXT")
        await conn.execute(
            "UPDATE reminders SET created_at = CURRENT_TIMESTAMP "
            "WHERE created_at IS NULL"
        )

    cur = await conn.execute("PRAGMA table_info(users)")
    user_cols = {row[1] for row in await cur.fetchall()}
    if "afternoon_time" not in user_cols:
        await conn.execute(
            "ALTER TABLE users ADD COLUMN afternoon_time TEXT DEFAULT '15:00'"
        )

    await conn.execute(
        "CREATE TABLE IF NOT EXISTS wellbeing_entries ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "tg_id INTEGER NOT NULL REFERENCES users(tg_id) ON DELETE CASCADE, "
        "ts TEXT NOT NULL, "
        "text TEXT NOT NULL)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_wellbeing_user_ts "
        "ON wellbeing_entries(tg_id, ts)"
    )


def connect() -> aiosqlite.Connection:
    return aiosqlite.connect(settings.db_file)
