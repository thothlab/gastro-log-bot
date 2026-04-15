PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    tg_id        INTEGER PRIMARY KEY,
    username     TEXT,
    first_name   TEXT,
    tz           TEXT NOT NULL DEFAULT 'Europe/Moscow',
    morning_time TEXT DEFAULT '09:00',
    evening_time TEXT DEFAULT '21:00',
    consent_at   TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS symptom_entries (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id      INTEGER NOT NULL REFERENCES users(tg_id) ON DELETE CASCADE,
    ts         TEXT NOT NULL,
    pain       INTEGER,
    nausea     INTEGER,
    heartburn  INTEGER,
    bloating   INTEGER,
    stool      INTEGER,
    notes      TEXT
);
CREATE INDEX IF NOT EXISTS idx_symptoms_user_ts ON symptom_entries(tg_id, ts);

CREATE TABLE IF NOT EXISTS medications (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id    INTEGER NOT NULL REFERENCES users(tg_id) ON DELETE CASCADE,
    name     TEXT NOT NULL,
    dose     TEXT,
    active   INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_meds_user_active ON medications(tg_id, active);

CREATE TABLE IF NOT EXISTS med_intakes (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id    INTEGER NOT NULL REFERENCES users(tg_id) ON DELETE CASCADE,
    med_id   INTEGER REFERENCES medications(id) ON DELETE SET NULL,
    med_name TEXT NOT NULL,
    dose     TEXT,
    ts       TEXT NOT NULL,
    notes    TEXT
);
CREATE INDEX IF NOT EXISTS idx_intakes_user_ts ON med_intakes(tg_id, ts);

CREATE TABLE IF NOT EXISTS food_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id       INTEGER NOT NULL REFERENCES users(tg_id) ON DELETE CASCADE,
    ts          TEXT NOT NULL,
    description TEXT NOT NULL,
    notes       TEXT
);
CREATE INDEX IF NOT EXISTS idx_food_user_ts ON food_entries(tg_id, ts);

CREATE TABLE IF NOT EXISTS reminders (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id    INTEGER NOT NULL REFERENCES users(tg_id) ON DELETE CASCADE,
    kind     TEXT NOT NULL,
    cron     TEXT NOT NULL,
    payload  TEXT,
    active   INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders(tg_id, active);
