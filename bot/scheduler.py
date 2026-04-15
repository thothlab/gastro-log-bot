from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.repositories import get_reminder, get_user, list_reminders, list_all_active_reminders

log = logging.getLogger(__name__)

REMINDER_TEXTS = {
    "morning": "🌅 Доброе утро! Как самочувствие? Запишите симптомы: /log",
    "evening": "🌙 Вечерний дневник: отметьте симптомы за день — /log",
    "med": "💊 Пора принять {name}{dose}. Отметить приём: /med",
}


class ReminderScheduler:
    """Обёртка над APScheduler, хранящая id job'ов вида `rem_{reminder_id}`."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self._sched = AsyncIOScheduler(timezone="UTC")

    async def start(self) -> None:
        self._sched.start()
        await self._load_all()

    async def shutdown(self) -> None:
        self._sched.shutdown(wait=False)

    # ---------- loading ----------

    async def _load_all(self) -> None:
        reminders = await list_all_active_reminders()
        for r in reminders:
            self._add_job(
                reminder_id=r["id"],
                tg_id=r["tg_id"],
                kind=r["kind"],
                cron=r["cron"],
                payload=r["payload"],
                tz=r["user_tz"] or "Europe/Moscow",
            )
        log.info("Scheduler loaded %d reminders", len(reminders))

    async def reload_user(self, tg_id: int) -> None:
        """Пересоздать все джобы пользователя (напр. после смены TZ или времени)."""
        await self.remove_user(tg_id)
        u = await get_user(tg_id)
        if u is None:
            return
        tz = u["tz"] or "Europe/Moscow"
        for r in await list_reminders(tg_id):
            cron = r["cron"]
            # для morning/evening — берём актуальное время из users
            if r["kind"] == "morning":
                cron = _hhmm_to_cron(u["morning_time"] or "09:00")
            elif r["kind"] == "evening":
                cron = _hhmm_to_cron(u["evening_time"] or "21:00")
            self._add_job(
                reminder_id=r["id"],
                tg_id=tg_id,
                kind=r["kind"],
                cron=cron,
                payload=r["payload"],
                tz=tz,
            )

    async def remove_user(self, tg_id: int) -> None:
        for job in list(self._sched.get_jobs()):
            if job.kwargs.get("tg_id") == tg_id:
                job.remove()

    async def add_reminder(self, reminder_id: int) -> None:
        r = await get_reminder(reminder_id)
        if r is None:
            return
        u = await get_user(r["tg_id"])
        if u is None:
            return
        self._add_job(
            reminder_id=r["id"],
            tg_id=r["tg_id"],
            kind=r["kind"],
            cron=r["cron"],
            payload=r["payload"],
            tz=u["tz"] or "Europe/Moscow",
        )

    def remove_reminder(self, reminder_id: int) -> None:
        job_id = f"rem_{reminder_id}"
        try:
            self._sched.remove_job(job_id)
        except Exception:
            pass

    # ---------- job ----------

    def _add_job(self, *, reminder_id: int, tg_id: int, kind: str,
                 cron: str, payload: str | None, tz: str) -> None:
        hour, minute = cron.split()
        trigger = CronTrigger(hour=int(hour), minute=int(minute), timezone=tz)
        self._sched.add_job(
            self._fire,
            trigger=trigger,
            id=f"rem_{reminder_id}",
            replace_existing=True,
            kwargs={"tg_id": tg_id, "kind": kind, "payload": payload},
        )

    async def _fire(self, tg_id: int, kind: str, payload: str | None) -> None:
        template = REMINDER_TEXTS.get(kind, "🔔 Напоминание")
        text = template
        if kind == "med":
            name = payload or "лекарство"
            text = template.format(name=name, dose="")
        try:
            await self.bot.send_message(tg_id, text)
        except Exception as e:
            log.warning("Reminder send failed for %s: %s", tg_id, e)


def _hhmm_to_cron(hhmm: str) -> str:
    h, m = hhmm.split(":")
    return f"{int(h)} {int(m)}"
