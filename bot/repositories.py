from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import aiosqlite

from bot.db import connect


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


# ---------- users ----------

async def upsert_user(tg_id: int, username: str | None, first_name: str | None) -> None:
    async with connect() as c:
        await c.execute(
            "INSERT INTO users(tg_id, username, first_name) VALUES(?,?,?) "
            "ON CONFLICT(tg_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name",
            (tg_id, username, first_name),
        )
        await c.commit()


async def set_consent(tg_id: int) -> None:
    async with connect() as c:
        await c.execute("UPDATE users SET consent_at=? WHERE tg_id=?", (_utcnow(), tg_id))
        await c.commit()


async def get_user(tg_id: int) -> aiosqlite.Row | None:
    async with connect() as c:
        c.row_factory = aiosqlite.Row
        cur = await c.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
        return await cur.fetchone()


async def has_consent(tg_id: int) -> bool:
    u = await get_user(tg_id)
    return bool(u and u["consent_at"])


async def update_settings(tg_id: int, *, tz: str | None = None,
                          morning: str | None = None, evening: str | None = None) -> None:
    fields, values = [], []
    if tz is not None:
        fields.append("tz=?"); values.append(tz)
    if morning is not None:
        fields.append("morning_time=?"); values.append(morning)
    if evening is not None:
        fields.append("evening_time=?"); values.append(evening)
    if not fields:
        return
    values.append(tg_id)
    async with connect() as c:
        await c.execute(f"UPDATE users SET {', '.join(fields)} WHERE tg_id=?", values)
        await c.commit()


async def delete_user(tg_id: int) -> None:
    async with connect() as c:
        await c.execute("PRAGMA foreign_keys = ON")
        await c.execute("DELETE FROM users WHERE tg_id=?", (tg_id,))
        await c.commit()


# ---------- symptoms ----------

async def add_symptoms(tg_id: int, *, pain: int | None, nausea: int | None,
                       heartburn: int | None, bloating: int | None,
                       stool: int | None, notes: str | None) -> int:
    async with connect() as c:
        cur = await c.execute(
            "INSERT INTO symptom_entries(tg_id, ts, pain, nausea, heartburn, bloating, stool, notes) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (tg_id, _utcnow(), pain, nausea, heartburn, bloating, stool, notes),
        )
        await c.commit()
        return cur.lastrowid or 0


async def list_symptoms(tg_id: int, since_iso: str) -> list[aiosqlite.Row]:
    async with connect() as c:
        c.row_factory = aiosqlite.Row
        cur = await c.execute(
            "SELECT * FROM symptom_entries WHERE tg_id=? AND ts >= ? "
            "ORDER BY ts ASC",
            (tg_id, since_iso),
        )
        return await cur.fetchall()


# ---------- medications ----------

async def add_med(tg_id: int, name: str, dose: str | None) -> int:
    async with connect() as c:
        cur = await c.execute(
            "INSERT INTO medications(tg_id, name, dose) VALUES(?,?,?)",
            (tg_id, name, dose),
        )
        await c.commit()
        return cur.lastrowid or 0


async def list_meds(tg_id: int, only_active: bool = True) -> list[aiosqlite.Row]:
    async with connect() as c:
        c.row_factory = aiosqlite.Row
        q = "SELECT * FROM medications WHERE tg_id=?"
        params: list[Any] = [tg_id]
        if only_active:
            q += " AND active=1"
        q += " ORDER BY name"
        cur = await c.execute(q, params)
        return await cur.fetchall()


async def deactivate_med(med_id: int, tg_id: int) -> None:
    async with connect() as c:
        await c.execute(
            "UPDATE medications SET active=0 WHERE id=? AND tg_id=?", (med_id, tg_id)
        )
        await c.commit()


async def get_med(med_id: int, tg_id: int) -> aiosqlite.Row | None:
    async with connect() as c:
        c.row_factory = aiosqlite.Row
        cur = await c.execute(
            "SELECT * FROM medications WHERE id=? AND tg_id=?", (med_id, tg_id)
        )
        return await cur.fetchone()


async def add_intake(tg_id: int, *, med_id: int | None, med_name: str,
                     dose: str | None, notes: str | None,
                     ts: str | None = None) -> int:
    async with connect() as c:
        cur = await c.execute(
            "INSERT INTO med_intakes(tg_id, med_id, med_name, dose, ts, notes) "
            "VALUES(?,?,?,?,?,?)",
            (tg_id, med_id, med_name, dose, ts or _utcnow(), notes),
        )
        await c.commit()
        return cur.lastrowid or 0


async def list_intakes(tg_id: int, since_iso: str) -> list[aiosqlite.Row]:
    async with connect() as c:
        c.row_factory = aiosqlite.Row
        cur = await c.execute(
            "SELECT * FROM med_intakes WHERE tg_id=? AND ts >= ? "
            "ORDER BY ts ASC",
            (tg_id, since_iso),
        )
        return await cur.fetchall()


# ---------- food ----------

async def add_food(tg_id: int, description: str, notes: str | None,
                   ts: str | None = None) -> int:
    async with connect() as c:
        cur = await c.execute(
            "INSERT INTO food_entries(tg_id, ts, description, notes) VALUES(?,?,?,?)",
            (tg_id, ts or _utcnow(), description, notes),
        )
        await c.commit()
        return cur.lastrowid or 0


async def list_food(tg_id: int, since_iso: str) -> list[aiosqlite.Row]:
    async with connect() as c:
        c.row_factory = aiosqlite.Row
        cur = await c.execute(
            "SELECT * FROM food_entries WHERE tg_id=? AND ts >= ? "
            "ORDER BY ts ASC",
            (tg_id, since_iso),
        )
        return await cur.fetchall()


# ---------- reminders ----------

async def add_reminder(tg_id: int, kind: str, cron: str, payload: str | None) -> int:
    async with connect() as c:
        cur = await c.execute(
            "INSERT INTO reminders(tg_id, kind, cron, payload, created_at) "
            "VALUES(?,?,?,?,?)",
            (tg_id, kind, cron, payload, _utcnow()),
        )
        await c.commit()
        return cur.lastrowid or 0


async def list_reminders(tg_id: int, only_active: bool = True) -> list[aiosqlite.Row]:
    async with connect() as c:
        c.row_factory = aiosqlite.Row
        q = "SELECT * FROM reminders WHERE tg_id=?"
        params: list[Any] = [tg_id]
        if only_active:
            q += " AND active=1"
        q += " ORDER BY id"
        cur = await c.execute(q, params)
        return await cur.fetchall()


async def list_all_active_reminders() -> list[aiosqlite.Row]:
    async with connect() as c:
        c.row_factory = aiosqlite.Row
        cur = await c.execute(
            "SELECT r.*, u.tz AS user_tz FROM reminders r "
            "JOIN users u ON u.tg_id = r.tg_id "
            "WHERE r.active=1"
        )
        return await cur.fetchall()


async def deactivate_reminder(reminder_id: int, tg_id: int) -> None:
    async with connect() as c:
        await c.execute(
            "UPDATE reminders SET active=0 WHERE id=? AND tg_id=?", (reminder_id, tg_id)
        )
        await c.commit()


async def get_reminder(reminder_id: int) -> aiosqlite.Row | None:
    async with connect() as c:
        c.row_factory = aiosqlite.Row
        cur = await c.execute("SELECT * FROM reminders WHERE id=?", (reminder_id,))
        return await cur.fetchone()
