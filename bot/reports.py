from __future__ import annotations

import csv
import io
import zipfile
from collections import defaultdict
from datetime import datetime
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bot.repositories import list_food, list_intakes, list_symptoms


async def build_csv_zip(tg_id: int, days: int) -> bytes:
    symptoms = await list_symptoms(tg_id, days)
    intakes = await list_intakes(tg_id, days)
    food = await list_food(tg_id, days)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
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
    # подменим заголовок 'ts_utc' на ключ 'ts'
    effective_keys = ["ts" if k == "ts_utc" else k for k in keys]
    for r in rows:
        w.writerow([r[k] for k in effective_keys])
    return out.getvalue()


async def build_chart(tg_id: int, days: int) -> bytes | None:
    symptoms = await list_symptoms(tg_id, days)
    if not symptoms:
        return None

    by_day: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for r in symptoms:
        day = r["ts"][:10]
        for k in ("pain", "nausea", "heartburn", "bloating"):
            v = r[k]
            if v is not None:
                by_day[day][k].append(v)

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
        # matplotlib умеет пропускать None при masked-подходе — фильтруем явно
        xs_f = [x for x, y in zip(xs, ys) if y is not None]
        ys_f = [y for y in ys if y is not None]
        if ys_f:
            ax.plot(xs_f, ys_f, marker="o", label=label)

    ax.set_title(f"Симптомы за {days} дн. (среднее в день, шкала 0–10)")
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


async def build_text_summary(tg_id: int, days: int) -> str:
    symptoms = await list_symptoms(tg_id, days)
    intakes = await list_intakes(tg_id, days)
    food = await list_food(tg_id, days)

    lines = [f"📊 <b>Сводка за {days} дн.</b>", ""]

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
        counts: dict[str, int] = defaultdict(int)
        for r in intakes:
            counts[r["med_name"]] += 1
        for name, n in sorted(counts.items(), key=lambda x: -x[1]):
            lines.append(f"  • {name} — {n}")

    lines.append("")
    lines.append(f"<b>Записей о еде:</b> {len(food)}")

    return "\n".join(lines)
