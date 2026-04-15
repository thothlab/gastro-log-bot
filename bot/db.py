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


def connect() -> aiosqlite.Connection:
    return aiosqlite.connect(settings.db_file)
