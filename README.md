# CookWithAI 🍳

AI-powered recipe & pantry assistant — proof of concept.

Enter the ingredients you have and CookWithAI suggests **3 recipes**: 1–2 that use only what you
have, and 1–2 that need a few extra ingredients. Pick one and it expands into a full recipe with
quantities, numbered steps and tips. Logged-in users get every search stored in SQLite and listed
in the sidebar. Guests can use the app too, but their searches are never written to the database.

**Stack:** Python 3.14 · Streamlit (Material Design 3 theme) · SQLite · OpenRouter · Docker

## Quick start

### Local (no Docker)

Requires Python 3.14.

```bash
cp .env.example .env          # optional — defaults to mock AI responses
python -m venv .venv          # one-time; skip if .venv already exists, then activate it
python -m pip install -e ".[dev]"
python -m streamlit run src/cookwithai/main.py
```

Run `python -m venv .venv` only once, from a shell where the venv is not active. Re-running it from
inside the venv fails with "Unable to copy ... venvlauncher.exe", because the running
`.venv\Scripts\python.exe` can't be overwritten.

To get real AI responses instead of the mock ones, set `LLM_PROVIDER=openrouter` and your
OpenRouter API key, either in `.env` or in the shell before starting:

```bash
# bash
export LLM_PROVIDER=openrouter
export OPENROUTER_API_KEY=sk-or-...
python -m streamlit run src/cookwithai/main.py
```

```powershell
# PowerShell
$env:LLM_PROVIDER = "openrouter"
$env:OPENROUTER_API_KEY = "sk-or-..."
python -m streamlit run src/cookwithai/main.py
```

The app is served at http://localhost:8501 and creates the SQLite database at
`./data/cookwithai.db` on first run.

### Docker

```bash
cp .env.example .env          # optional — defaults to mock AI responses
docker run --rm -v "${PWD}:/project" -w /project python:3.14-slim python scripts/vendor_deps.py
docker compose up --build -d
```

`-d` runs the containers in the background; follow the logs with `docker compose logs -f` and stop
them with `docker compose down`.

The `docker run` line fills `vendor/` with the Linux packages the image needs. It's a one-time step
that takes a few minutes, and only needs repeating when the dependencies in `pyproject.toml` change.
`vendor/` is gitignored, so a fresh clone has to run it too.

`docker compose build` installs nothing: it only copies `vendor/` and the source into the image, so
it needs no network for packages. The first build takes about 2 minutes to read `vendor/`, and later
ones take a couple of seconds, including after code changes.

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

## Accounts

Users register and log in with an email (the username) and a password of at least 8 characters.
Passwords are stored as salted scrypt hashes.

A login lasts a fixed **2 hours** and activity does not extend it. The browser holds only the
session ID, a random UUID, in a cookie set from JavaScript, because Streamlit has no server-side way
to set cookies. The start time and length are kept on the server, in the `users` row. Each script
run checks the session, so reopening the app logs the user back in while the session is active, and
an open tab logs out within a minute of it ending.

Limits of this proof of concept:

- A user has one session, so logging in on a second device logs out the first.
- Session IDs are stored in plain text, so anyone who can read the database (including `db-admin`)
  could use a live session.
- The cookie can't be `HttpOnly`, because JavaScript sets it.
- There is no email verification or login rate limiting.
- The forgotten password page collects an email but doesn't send anything yet.

## Tests

```bash
docker compose run --rm app pytest
```

Or locally with Python 3.14:

```bash
python -m venv .venv             # then activate it
python -m pip install -e ".[dev]"
python -m pytest
python -m streamlit run src/cookwithai/main.py
```

`pytest` reports coverage as well. To run only the unit tests, leaving out the tests that drive the
whole Streamlit app:

```bash
python -m pytest -m "not integration"
```

Code checks (settings are in `pyproject.toml`):

```bash
python -m ruff check src tests scripts
python -m black --check src tests scripts
python -m mypy
```

## Project layout

```
pyproject.toml         Metadata, pinned dependencies and tool settings
src/cookwithai/
  main.py              Streamlit page: login session, search → suggestion cards → recipe detail
  config.py            Settings from environment variables
  db/                  schema.sql, connection/init/migration, repository (stdlib sqlite3)
  llm/                 Pydantic schemas, prompts, mock + OpenRouter clients, factory
  services/            AuthService (accounts, sessions), RecipeService (LLM + persistence)
  ui/                  Login pages, Material-style components and CSS
.streamlit/config.toml Material Design 3 theme (purple baseline, Roboto)
scripts/vendor_deps.py Fills vendor/ with the Linux packages the Docker image copies in
tests/                 pytest suite (mock LLM, schemas, repository, services, login pages, OpenRouter)
```
