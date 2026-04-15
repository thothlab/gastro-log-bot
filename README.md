[![en](https://img.shields.io/badge/lang-English-blue)](README_EN.md)

# GastroBot — дневник здоровья желудка в Telegram

Telegram-бот для ведения личного дневника **желудочно-кишечных симптомов** и **приёма лекарств**. По формату — аналог [@Migrebot](https://migrebot.ru) (дневник головной боли Университетской клиники головной боли), но для ЖКТ.

Бот помогает фиксировать боль, тошноту, изжогу, вздутие, характер стула, приёмы препаратов и еду, напоминает о таблетках и готовит сводку для визита к гастроэнтерологу.

> ⚠️ **Важно:** бот **не является медицинским изделием** и **не заменяет** консультацию врача. Это инструмент для ведения вашего личного дневника.

---

## Попробовать

Бот развёрнут автором: **[@gastro_log_bot](https://t.me/gastro_log_bot)** → отправьте `/start`.

Или разверните свой — см. [Запуск](#запуск).

## Возможности

| Команда | Что делает |
|---|---|
| `/start` | Согласие на обработку данных + приветствие |
| `/log` | Анкета симптомов: боль, тошнота, изжога, вздутие (шкала 0–10), стул по [Бристольской шкале](https://ru.wikipedia.org/wiki/%D0%91%D1%80%D0%B8%D1%81%D1%82%D0%BE%D0%BB%D1%8C%D1%81%D0%BA%D0%B0%D1%8F_%D1%88%D0%BA%D0%B0%D0%BB%D0%B0_%D1%84%D0%BE%D1%80%D0%BC_%D0%BA%D0%B0%D0%BB%D0%B0) (1–7), текстовая заметка |
| `/med`, `/meds` | Ведение списка препаратов и быстрая отметка приёма |
| `/food` | Дневник еды и триггеров |
| `/remind` | Напоминания утром/вечером и по расписанию конкретных лекарств — в часовом поясе пользователя |
| `/stats` | Текстовая сводка и PNG-график за 7 / 30 / 90 дней |
| `/export` | ZIP-архив с CSV (симптомы, приёмы лекарств, еда) — для показа врачу |
| `/settings` | Часовой пояс, время утреннего и вечернего напоминаний |
| `/privacy` | Политика хранения данных |
| `/delete` | Полное и безвозвратное удаление ваших данных |
| `/help` | Справка |
| `/cancel` | Прервать текущую анкету |

## Стек

- **Python 3.11** + [aiogram 3](https://docs.aiogram.dev/) (async, FSM)
- **SQLite** (aiosqlite, WAL) — данные локально, каскадное удаление по `tg_id`
- **APScheduler** — cron-напоминания в часовом поясе пользователя
- **matplotlib** — графики динамики симптомов
- **Docker + docker-compose** — воспроизводимый деплой
- Режим работы Telegram API: **long polling** (не требует внешнего IP)

## Структура проекта

```
gastrobot/
├── bot/
│   ├── main.py              # entrypoint, старт диспетчера + scheduler
│   ├── config.py            # pydantic-settings из .env
│   ├── db.py + schema.sql   # инициализация SQLite
│   ├── repositories.py      # CRUD-слой
│   ├── middlewares.py       # upsert пользователя + throttle
│   ├── keyboards.py         # inline-клавиатуры
│   ├── texts.py             # все русские строки
│   ├── scheduler.py         # обёртка над APScheduler
│   ├── reports.py           # CSV + PNG-графики + сводка
│   └── handlers/            # роутеры по фичам (symptoms, meds, food, …)
├── data/                    # volume для bot.db
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Запуск

### 1. Получите токен бота

У [@BotFather](https://t.me/BotFather) — команда `/newbot`. Сохраните токен.

### 2. Клонируйте репозиторий и задайте окружение

```bash
git clone https://github.com/thothlab/gastro-log-bot.git
cd gastro-log-bot
cp .env.example .env
# отредактируйте .env: впишите BOT_TOKEN=...
```

### 3. Запустите через Docker

```bash
docker compose up -d --build
docker compose logs -f gastrobot
```

В логах должно появиться:

```
INFO apscheduler.scheduler: Scheduler started
INFO aiogram.dispatcher: Run polling for bot @your_bot_name ...
```

### Обновление

```bash
git pull
docker compose up -d --build
```

### Бэкап БД

Весь дневник — в одном файле:

```bash
cp data/bot.db backups/bot.$(date +%F).db
```

## Запуск без Docker (для разработки)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export BOT_TOKEN=...
python -m bot.main
```

## Приватность и безопасность

- Все данные хранятся **локально** в файле SQLite на том хосте, где запущен бот. Наружу ничего не отправляется.
- Токен бота хранится только в `.env`, который исключён в `.gitignore`.
- До согласия в `/start` бот не принимает никаких команд кроме `/help` и `/privacy`.
- Команда `/delete` удаляет пользователя и все связанные записи **каскадом по foreign key** — необратимо.
- Rate-limit (throttle) 0.4 секунды между апдейтами одного пользователя.

## Дорожная карта

- [ ] PDF-отчёт для врача (сейчас — CSV + график PNG)
- [ ] Локальный анализ триггеров через Ollama (без отправки данных вовне)
- [ ] Автоматические ежедневные бэкапы БД
- [ ] Режим мультипрофиля (родитель ведёт дневник ребёнка)

## Лицензия

MIT — см. [LICENSE](LICENSE).

## Ссылки

- Идея-прототип: [Migrebot — Телеграм-бот для контроля головной боли](https://headache.ru/news/migrebot_telegram_bot_dlya_kontrolya_golovnoi_boli/)
- Бристольская шкала форм кала — [Wikipedia](https://ru.wikipedia.org/wiki/%D0%91%D1%80%D0%B8%D1%81%D1%82%D0%BE%D0%BB%D1%8C%D1%81%D0%BA%D0%B0%D1%8F_%D1%88%D0%BA%D0%B0%D0%BB%D0%B0_%D1%84%D0%BE%D1%80%D0%BC_%D0%BA%D0%B0%D0%BB%D0%B0)
