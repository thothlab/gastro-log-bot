[![ru](https://img.shields.io/badge/lang-Русский-green)](README.md)

# GastroBot — gut health diary in Telegram

A Telegram bot for keeping a personal diary of **gastrointestinal symptoms** and **medication intake**. Inspired by [@Migrebot](https://migrebot.ru) (a headache diary by the Moscow University Headache Clinic), but for the GI tract.

The bot helps to log pain, nausea, heartburn, bloating, stool consistency, medication doses and meals, sends reminders, and prepares a summary for your gastroenterologist visit.

> ⚠️ **Disclaimer:** this bot is **not a medical device** and **does not replace** a consultation with a doctor. It is a tool for keeping your personal diary.

---

## Try it

The author hosts a public instance: **[@gastro_log_bot](https://t.me/gastro_log_bot)** → send `/start`.

Or self-host — see [Run](#run).

## Features

| Command | What it does |
|---|---|
| `/start` | Consent to data processing + welcome screen |
| `/log` | Symptom questionnaire: pain, nausea, heartburn, bloating (0–10 scale), stool on the [Bristol scale](https://en.wikipedia.org/wiki/Bristol_stool_scale) (1–7), free-form note |
| `/med`, `/meds` | Manage medication list and quickly log an intake |
| `/food` | Food and trigger diary |
| `/remind` | Morning / evening reminders and per-medication schedules — in the user's timezone |
| `/stats` | Text summary and PNG chart over 7 / 30 / 90 days |
| `/export` | ZIP archive with CSV files (symptoms, intakes, food) — for sharing with your doctor |
| `/settings` | Timezone, morning / evening reminder times |
| `/privacy` | Data storage policy |
| `/delete` | Full and irreversible data deletion |
| `/help` | Commands help |
| `/cancel` | Cancel the current questionnaire |

## Stack

- **Python 3.11** + [aiogram 3](https://docs.aiogram.dev/) (async, FSM)
- **SQLite** (aiosqlite, WAL) — data stays local, cascade deletion by `tg_id`
- **APScheduler** — cron reminders in the user's timezone
- **matplotlib** — symptom dynamics charts
- **Docker + docker-compose** — reproducible deployment
- Telegram API mode: **long polling** (no public IP required)

## Project layout

```
gastrobot/
├── bot/
│   ├── main.py              # entrypoint, dispatcher + scheduler
│   ├── config.py            # pydantic-settings from .env
│   ├── db.py + schema.sql   # SQLite init
│   ├── repositories.py      # CRUD layer
│   ├── middlewares.py       # user upsert + throttle
│   ├── keyboards.py         # inline keyboards
│   ├── texts.py             # all user-facing strings (Russian)
│   ├── scheduler.py         # APScheduler wrapper
│   ├── reports.py           # CSV + PNG charts + summary
│   └── handlers/            # feature routers (symptoms, meds, food, …)
├── data/                    # volume for bot.db
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

> ℹ️ User-facing strings and the default locale are **Russian**. Localization into other languages is on the roadmap.

## Run

### 1. Get a bot token

From [@BotFather](https://t.me/BotFather) — `/newbot`. Save the token.

### 2. Clone and configure

```bash
git clone https://github.com/thothlab/gastro-log-bot.git
cd gastro-log-bot
cp .env.example .env
# edit .env: set BOT_TOKEN=...
```

### 3. Start with Docker

```bash
docker compose up -d --build
docker compose logs -f gastrobot
```

Expected logs:

```
INFO apscheduler.scheduler: Scheduler started
INFO aiogram.dispatcher: Run polling for bot @your_bot_name ...
```

### Update

```bash
git pull
docker compose up -d --build
```

### Backup

The whole diary is one file:

```bash
cp data/bot.db backups/bot.$(date +%F).db
```

## Run without Docker (development)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export BOT_TOKEN=...
python -m bot.main
```

## Privacy & security

- All data is stored **locally** in a SQLite file on the host running the bot. Nothing leaves the machine.
- The bot token is kept only in `.env`, which is in `.gitignore`.
- Before consent via `/start` the bot rejects all commands except `/help` and `/privacy`.
- `/delete` wipes the user and all related records **via foreign-key cascade** — irreversibly.
- Rate limit (throttle) of 0.4 s between updates from the same user.

## Roadmap

- [ ] PDF report for the doctor (currently CSV + PNG chart)
- [ ] Local trigger analysis via Ollama (no data leaves the host)
- [ ] Automatic daily DB backups
- [ ] Multi-profile mode (a parent keeping a child's diary)
- [ ] English UI

## License

MIT — see [LICENSE](LICENSE).

## Links

- Prototype idea: [Migrebot — Telegram headache diary](https://headache.ru/news/migrebot_telegram_bot_dlya_kontrolya_golovnoi_boli/)
- [Bristol stool scale — Wikipedia](https://en.wikipedia.org/wiki/Bristol_stool_scale)
