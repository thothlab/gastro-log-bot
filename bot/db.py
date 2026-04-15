from pathlib import Path

import aiosqlite

from bot.config import settings

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


async def init_db() -> None:
    settings.db_file.parent.mkdir(parents=True, exist_ok=True)
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    async with aiosqlite.connect(settings.db_file) as conn:
        await conn.executescript(sql)
        await conn.commit()


def connect() -> aiosqlite.Connection:
    return aiosqlite.connect(settings.db_file)
