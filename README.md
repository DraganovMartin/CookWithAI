# CookWithAI 🍳

AI-powered recipe & pantry assistant — proof of concept.

Enter the ingredients you have and CookWithAI suggests **3 recipes**: 1–2 that use only what you
have, and 1–2 that need a few extra ingredients. Pick one and it expands into a full recipe with
quantities, numbered steps and tips. Every search is stored in SQLite and listed in the sidebar.

**Stack:** Python 3.14 · Streamlit (Material Design 3 theme) · SQLite · OpenRouter · Docker

## Quick start (Docker)

```bash
cp .env.example .env          # optional — defaults to mock AI responses
docker compose up --build
```

| URL                     | What                                         |
|-------------------------|----------------------------------------------|
| http://localhost:8501   | CookWithAI app                               |
| http://localhost:8080   | sqlite-web — browse the `cookwithai.db` tables |

The database lives on the named volume `cookwithai-data`, so history survives
`docker compose down` / `up`. Use `docker compose down -v` to wipe it.

SQLite is an embedded database with no server process: the `app` container owns the database file,
and the `db-admin` container (sqlite-web) mounts the same volume to inspect it.

## Configuration

| Variable             | Default                        | Notes                                     |
|----------------------|--------------------------------|-------------------------------------------|
| `LLM_PROVIDER`       | `mock`                         | `mock` (offline) or `openrouter`          |
| `OPENROUTER_API_KEY` | —                              | Required when `LLM_PROVIDER=openrouter`   |
| `OPENROUTER_MODEL`   | `anthropic/claude-sonnet-5.5`  | Any slug from https://openrouter.ai/models |
| `DATABASE_PATH`      | `./data/cookwithai.db`         | Compose sets `/data/cookwithai.db`        |

The API key is only ever read from the environment (`.env` is gitignored).

## Tests

```bash
docker compose run --rm app pytest
```

Or locally with Python 3.14:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
python -m streamlit run app/main.py
```

## Project layout

```
app/
  main.py              Streamlit page: search → suggestion cards → recipe detail
  config.py            Settings from environment variables
  db/                  schema.sql, connection/init, repository (stdlib sqlite3)
  llm/                 Pydantic schemas, prompts, mock + OpenRouter clients, factory
  services/            RecipeService — orchestrates the LLM and persistence
  ui/                  Material-style components and CSS
.streamlit/config.toml Material Design 3 theme (purple baseline, Roboto)
tests/                 pytest suite (mock LLM, schemas, repository, service, OpenRouter client)
```

## Database

| Table         | Columns                                                                   |
|---------------|---------------------------------------------------------------------------|
| `users`       | `id`, `email` (for OAuth later), `display_name`, `created_at`             |
| `recipes`     | `id`, `user_id` → users, `suggested_recipes` (JSON), `chosen_recipe`, `steps` (JSON), `created_at` |
| `ingredients` | `id`, `recipe_id` → recipes (1:1), `available_ingredients` (JSON), `missing_ingredients` (JSON) |

One `recipes` row is created per search. `chosen_recipe`, `steps` and `missing_ingredients` are
filled in when the user picks a suggestion. JSON is stored as `TEXT`, which maps directly to Room
TypeConverters for the planned Android app. Until OAuth lands, everything belongs to a seeded
`Guest` user (id 1).

## Next iterations

- OAuth login (populate `users.email`, replace the guest user)
- Switch `LLM_PROVIDER` to `openrouter` and tune prompts/model
- Android app reusing `schema.sql`
