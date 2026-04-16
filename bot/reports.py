from __future__ import annotations

import csv
import io
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bot.repositories import list_food, list_intakes, list_reminders, list_symptoms

WEEKDAYS_RU = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
MONTHS_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]
MISSED_WINDOW_HOURS = 3
MISSED_CAP = 30


# ---------- zip (csv + txt) ----------

async def build_export_zip(tg_id: int, since_iso: str, period_label: str,
                           tz_name: str) -> bytes:
    symptoms = await list_symptoms(tg_id, since_iso)
    intakes = await list_intakes(tg_id, since_iso)
    food = await list_food(tg_id, since_iso)
    reminders = await list_reminders(tg_id)

    text = _build_text_report(
        symptoms=symptoms, intakes=intakes, food=food, reminders=reminders,
        since_iso=since_iso, period_label=period_label, tz_name=tz_name,
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("diary.txt", text)
        zf.writestr("symptoms.csv", _csv(
            ["id", "ts_utc", "pain", "nausea", "heartburn", "bloating", "stool", "notes"],
            symptoms,
        ))
        zf.writestr("med_intakes.csv", _csv(
            ["id", "ts_utc", "med_name", "dose", "notes"],
            intakes,
            keys=["id", "ts", "med_name", "dose", "notes"],
        ))
        zf.writestr("food.csv", _csv(
            ["id", "ts_utc", "description", "notes"],
            food,
        ))
    return buf.getvalue()


def _csv(header: list[str], rows, keys: list[str] | None = None) -> str:
    keys = keys or header
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(header)
    effective_keys = ["ts" if k == "ts_utc" else k for k in keys]
    for r in rows:
        w.writerow([r[k] for k in effective_keys])
    return out.getvalue()


# ---------- text report ----------

def _build_text_report(*, symptoms, intakes, food, reminders,
                       since_iso: str, period_label: str, tz_name: str) -> str:
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Europe/Moscow")

    now_utc = datetime.now(tz=timezone.utc)
    gen_local = now_utc.astimezone(tz).strftime("%d.%m.%Y %H:%M")

    lines: list[str] = []
    lines.append(f"📊 Дневник GastroBot — {period_label}")
    lines.append(f"Часовой пояс: {tz_name}")
    lines.append(f"Сгенерирован: {gen_local}")
    lines.append("")
    lines.append(
        f"Итого: симптомов {len(symptoms)} · "
        f"лекарств {len(intakes)} · "
        f"еды {len(food)}"
    )
    lines.append("")

    active = [r for r in reminders if r["active"]]
    if active:
        lines.append("🔔 Активные напоминания:")
        for r in sorted(active, key=lambda x: x["cron"]):
            lines.append(f"   {_cron_to_hhmm(r['cron'])}  {_reminder_label(r)}")
        lines.append("")

    adherence_rows, missed = _adherence_and_missed(
        reminders=active, intakes=intakes,
        since_iso=since_iso, now_utc=now_utc, tz=tz,
    )
    if adherence_rows:
        lines.append("📈 Соблюдение режима:")
        maxlen = max(len(r[0]) for r in adherence_rows)
        for name_time, hit, total, pct in adherence_rows:
            lines.append(f"   {name_time:<{maxlen}}  →  {hit} из {total} дней ({pct}%)")
        lines.append("")

    if missed:
        lines.append(f"⚠ Пропущенные приёмы ({len(missed)}):")
        shown = missed[:MISSED_CAP]
        for day_str, time_str, name in shown:
            lines.append(f"   • {day_str}  {time_str}  {name}")
        if len(missed) > MISSED_CAP:
            lines.append(f"   … и ещё {len(missed) - MISSED_CAP}")
        lines.append("")

    events = _collect_events(symptoms, intakes, food, tz)
    if not events:
        lines.append("Записей за период нет.")
        return "\n".join(lines)

    events_by_day: dict[date, list[tuple[datetime, str]]] = defaultdict(list)
    for dt, text in events:
        events_by_day[dt.date()].append((dt, text))

    # Свежие дни — сверху, т.к. обычно интереснее последние события.
    for day in sorted(events_by_day.keys(), reverse=True):
        lines.append(f"━━━ {WEEKDAYS_RU[day.weekday()]}, "
                     f"{day.day} {MONTHS_RU[day.month - 1]} ━━━")
        for _, text in sorted(events_by_day[day], key=lambda x: x[0]):
            lines.append(text)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _cron_to_hhmm(cron: str) -> str:
    h, m = cron.split()
    return f"{int(h):02d}:{int(m):02d}"


def _reminder_label(r) -> str:
    if r["kind"] == "morning":
        return "утренний дневник"
    if r["kind"] == "evening":
        return "вечерний дневник"
    return r["payload"] or "лекарство"


def _parse_db_ts(raw: str) -> datetime:
    """Принимаем и ISO8601 ('...+00:00'), и sqlite-datetime ('YYYY-MM-DD HH:MM:SS').

    Все приложенные ts хранятся в UTC — возвращаем aware-UTC datetime.
    """
    s = raw.strip()
    if "T" not in s and " " in s:
        s = s.replace(" ", "T")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _collect_events(symptoms, intakes, food, tz: ZoneInfo) -> list[tuple[datetime, str]]:
    events: list[tuple[datetime, str]] = []

    for s in symptoms:
        dt = _parse_db_ts(s["ts"]).astimezone(tz)
        t = dt.strftime("%H:%M")
        parts = []
        for key, label in [("pain", "Боль"), ("nausea", "Тошнота"),
                           ("heartburn", "Изжога"), ("bloating", "Вздутие")]:
            v = s[key]
            if v is not None:
                parts.append(f"{label} {v}")
        head = f"🤕  {t}  " + (" · ".join(parts) if parts else "—")
        rows = [head]
        stool = s["stool"]
        rows.append(f"           Стул: {stool} (Bristol)" if stool is not None
                    else "           Стул: —")
        if s["notes"]:
            rows.append(f"           «{s['notes']}»")
        events.append((dt, "\n".join(rows)))

    for i in intakes:
        dt = _parse_db_ts(i["ts"]).astimezone(tz)
        t = dt.strftime("%H:%M")
        line = f"💊  {t}  {i['med_name']}"
        if i["dose"]:
            line += f" {i['dose']}"
        if i["notes"]:
            line += f"  «{i['notes']}»"
        events.append((dt, line))

    for f in food:
        dt = _parse_db_ts(f["ts"]).astimezone(tz)
        t = dt.strftime("%H:%M")
        line = f"🍽  {t}  {f['description']}"
        if f["notes"]:
            line += f"  «{f['notes']}»"
        events.append((dt, line))

    return events


def _adherence_and_missed(*, reminders, intakes, since_iso: str,
                          now_utc: datetime, tz: ZoneInfo):
    """Для med-напоминаний считаем (адхеренс, список пропущенных).

    Пропуск — отсутствие приёма препарата с тем же именем в пределах
    ±3 ч от времени напоминания в конкретный день. Дни до `created_at`
    напоминания не учитываются, чтобы не ловить ложные пропуски.
    """
    med_rems = [r for r in reminders if r["kind"] == "med" and r["payload"]]
    if not med_rems:
        return [], []

    since_local = _parse_db_ts(since_iso).astimezone(tz)
    now_local = now_utc.astimezone(tz)

    idx: dict[tuple[date, str], list[datetime]] = defaultdict(list)
    for i in intakes:
        dt = _parse_db_ts(i["ts"]).astimezone(tz)
        idx[(dt.date(), i["med_name"].strip().lower())].append(dt)

    adherence_rows: list[tuple[str, int, int, int]] = []
    missed: list[tuple[str, str, str]] = []

    for r in med_rems:
        h_str, m_str = r["cron"].split()
        h, m = int(h_str), int(m_str)
        name = r["payload"].strip()
        name_lower = name.lower()
        created = r["created_at"] if "created_at" in r.keys() else None
        start_local = since_local
        if created:
            try:
                start_local = max(start_local, _parse_db_ts(created).astimezone(tz))
            except Exception:
                pass

        day = start_local.date()
        total = 0
        hit_days = 0
        while day <= now_local.date():
            target = datetime(day.year, day.month, day.day, h, m, tzinfo=tz)
            if target > now_local:
                day += timedelta(days=1)
                continue
            total += 1
            candidates = idx.get((day, name_lower), [])
            hit = any(
                abs((c - target).total_seconds()) <= MISSED_WINDOW_HOURS * 3600
                for c in candidates
            )
            if hit:
                hit_days += 1
            else:
                missed.append((
                    f"{day.day:02d}.{day.month:02d}",
                    f"{h:02d}:{m:02d}",
                    name,
                ))
            day += timedelta(days=1)

        if total > 0:
            pct = round(hit_days * 100 / total)
            adherence_rows.append((f"{name} {h:02d}:{m:02d}", hit_days, total, pct))

    missed.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return adherence_rows, missed


# ---------- stats chart / summary ----------

async def build_chart(tg_id: int, since_iso: str, period_label: str) -> bytes | None:
    symptoms = await list_symptoms(tg_id, since_iso)
    if not symptoms:
        return None

    by_day: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for r in symptoms:
        day = r["ts"][:10]
        for k in ("pain", "nausea", "heartburn", "bloating"):
            v = r[k]
            if v is not None:
                by_day[day][k].append(v)

    if len(by_day) < 2:
        return None

    days_sorted = sorted(by_day.keys())
    xs = [datetime.fromisoformat(d) for d in days_sorted]

    fig, ax = plt.subplots(figsize=(10, 5))
    for metric, label in [
        ("pain", "Боль"),
        ("nausea", "Тошнота"),
        ("heartburn", "Изжога"),
        ("bloating", "Вздутие"),
    ]:
        ys = [mean(by_day[d][metric]) if by_day[d][metric] else None for d in days_sorted]
        xs_f = [x for x, y in zip(xs, ys) if y is not None]
        ys_f = [y for y in ys if y is not None]
        if ys_f:
            ax.plot(xs_f, ys_f, marker="o", label=label)

    ax.set_title(f"Симптомы {period_label} (среднее в день, шкала 0–10)")
    ax.set_ylim(0, 10)
    ax.set_ylabel("Интенсивность")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.autofmt_xdate()

    out = io.BytesIO()
    fig.tight_layout()
    fig.savefig(out, format="png", dpi=120)
    plt.close(fig)
    return out.getvalue()


async def build_text_summary(tg_id: int, since_iso: str, period_label: str,
                             tz_name: str = "Europe/Moscow") -> str:
    symptoms = await list_symptoms(tg_id, since_iso)
    intakes = await list_intakes(tg_id, since_iso)
    food = await list_food(tg_id, since_iso)

    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Europe/Moscow")

    lines = [f"📊 <b>Сводка {period_label}</b>", ""]

    if not symptoms:
        lines.append("Записей симптомов нет.")
    else:
        def avg(key):
            xs = [r[key] for r in symptoms if r[key] is not None]
            return round(mean(xs), 1) if xs else "—"

        lines.append(f"<b>Симптомы</b> (записей: {len(symptoms)})")
        lines.append(f"• Боль, ср: {avg('pain')}")
        lines.append(f"• Тошнота, ср: {avg('nausea')}")
        lines.append(f"• Изжога, ср: {avg('heartburn')}")
        lines.append(f"• Вздутие, ср: {avg('bloating')}")
        stool_vals = [r["stool"] for r in symptoms if r["stool"] is not None]
        if stool_vals:
            lines.append(f"• Bristol, ср: {round(mean(stool_vals), 1)} (n={len(stool_vals)})")

    lines.append("")
    lines.append(f"<b>Приёмов лекарств:</b> {len(intakes)}")
    if intakes:
        grouped: dict[str, list[str]] = defaultdict(list)
        for r in intakes:
            dt = _parse_db_ts(r["ts"]).astimezone(tz)
            t = dt.strftime("%d.%m %H:%M") if period_label != "за сегодня" else dt.strftime("%H:%M")
            label = t
            if r["dose"]:
                label += f" ({r['dose']})"
            grouped[r["med_name"]].append(label)
        for name, times in sorted(grouped.items(), key=lambda x: -len(x[1])):
            lines.append(f"  • {name} — {len(times)}")
            shown = times[:20]
            lines.append(f"    {', '.join(shown)}")
            if len(times) > 20:
                lines.append(f"    … и ещё {len(times) - 20}")

    lines.append("")
    lines.append(f"<b>Записей о еде:</b> {len(food)}")
    if food:
        shown_food = food[:20]
        for f in shown_food:
            dt = _parse_db_ts(f["ts"]).astimezone(tz)
            t = dt.strftime("%d.%m %H:%M") if period_label != "за сегодня" else dt.strftime("%H:%M")
            line = f"  • {t} — {f['description']}"
            if f["notes"]:
                line += f" ({f['notes']})"
            lines.append(line)
        if len(food) > 20:
            lines.append(f"  … и ещё {len(food) - 20}")

    return "\n".join(lines)
