-- CookWithAI schema. Plain SQLite DDL, kept portable for a future Android (Room) port.
-- JSON payloads are stored as TEXT (maps to Room TypeConverters).

CREATE TABLE IF NOT EXISTS users (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    email            TEXT UNIQUE,                        -- login name, stored lowercase; NULL for Guest
    display_name     TEXT NOT NULL,
    password_hash    TEXT,                               -- scrypt hash; NULL for Guest
    session_id       TEXT,                               -- random UUID, NULL when logged out
    login_timestamp  TEXT,                               -- UTC, set at each login
    session_time     INTEGER,                            -- session length in seconds
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One row per search: suggestions first, chosen recipe + steps once the user picks one.
CREATE TABLE IF NOT EXISTS recipes (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    suggested_recipes  TEXT NOT NULL,                    -- JSON array of suggestions
    chosen_recipe      TEXT,                             -- title of the selected suggestion
    steps              TEXT,                             -- JSON: full details (ingredients, steps, tips)
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ingredients (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id              INTEGER NOT NULL UNIQUE REFERENCES recipes(id) ON DELETE CASCADE,
    available_ingredients  TEXT NOT NULL,                -- JSON array entered by the user
    missing_ingredients    TEXT NOT NULL DEFAULT '[]'    -- JSON array for the chosen recipe
);

CREATE INDEX IF NOT EXISTS idx_recipes_user ON recipes(user_id, created_at);
