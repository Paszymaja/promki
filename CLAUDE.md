# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLI tool that fetches Lidl Plus coupons, auto-activates inactive ones, and optionally creates a Google Tasks shopping list or suggests recipes via Gemini or a local Ollama model.

## Commands

```bash
# Run the tool
uv run lidl-recipe
uv run lidl-recipe --tasks     # create Google Tasks shopping list
uv run lidl-recipe --recipes   # get recipe suggestions (Gemini by default; set RECIPE_PROVIDER=ollama for local)
uv run lidl-recipe --diff      # show what changed vs the previous snapshot
uv run lidl-recipe --login     # open browser, log in, token saved automatically

# Install dependencies
uv sync
uv sync --extra login          # include playwright for --login
playwright install chromium    # download browser (first time only)
```

```bash
# Run tests
uv run pytest
```

## Architecture

Package `lidl_recipe/` with modules:

- **`config.py`** — `Config` dataclass centralizing all env loading, validation, and `.env` writing
- **`api.py`** — `LidlApi` HTTP client wrapping the Lidl Plus coupons API (Bearer token auth)
- **`coupons.py`** — `normalize_coupons()` handles varying API response shapes; `fetch_and_activate_coupons()` activates inactive coupons with rate limiting; `extract_discount_items()` extracts title + discount info; `filter_consumables()` uses keyword blocklist to exclude non-consumables
- **`tasks.py`** — `create_shopping_list()` creates a dated Google Tasks list via OAuth2
- **`recipes.py`** — `build_prompt(items)` constructs the shared Polish-language recipe prompt used by both backends
- **`gemini.py`** — `suggest_recipes(items, api_key)` sends prompt to Google Gemini free API
- **`ollama.py`** — `suggest_recipes(items, url)` sends prompt to a local Ollama server (`/api/generate`, non-streaming, 300s timeout). Model is hardcoded to `gemma4-fast` (`ollama.MODEL`).
- **`login.py`** — `capture_token(session_file, silent)` uses Playwright to capture the Lidl Plus Bearer token. Persists `storage_state` to `lidl_session.json` so subsequent calls can replay the session headlessly (`silent=True`); falls back to interactive Chromium when no saved session is available. CLI auto-invokes silent refresh on missing token or HTTP 401.
- **`db.py`** — SQLite snapshot store at `config.db_file` (`coupons.db`). Two-table schema (`runs` + `coupon_observations`) versioned via `PRAGMA user_version`; `save_snapshot()` always records a run (even when empty); `diff_latest()` compares the two most recent runs on `(title, discount_title, discount_description, valid_end, is_activated)`; `format_diff()` returns lines, `print_diff()` writes to stdout. Schema mismatches raise `SchemaVersionError`. All timestamps written via `_utc_now_iso()` so lex-sort matches chronological order.
- **`cli.py`** — `main()` orchestrates the flow: reconfigure stdio to UTF-8 (Windows cp1250 can't render some Polish/bidi chars) → load config → fetch coupons → activate → save snapshot → optionally show diff/tasks/recipes. DB failures (`sqlite3.Error`, `SchemaVersionError`) are caught and logged as warnings; they never abort the run.
- **`__init__.py`** — re-exports `main` for the `lidl-recipe` entrypoint

## Configuration

All config via `.env` (see `.env.example`), loaded centrally by `Config.from_env()`:
- `LIDL_ACCESS_TOKEN` — Bearer token from Lidl Plus (use `--login` to capture, or grab manually from browser dev tools). Auto-refreshed via saved Playwright session (`lidl_session.json`) when expired.
- `GEMINI_API_KEY` — Free key from Google AI Studio (only needed with `--recipes` when using the Gemini backend)
- `RECIPE_PROVIDER` — `gemini` (default) or `ollama`. Selects the recipe backend used by `--recipes`. Validated in `Config.from_env()`; invalid values exit with `sys.exit(1)`.
- `OLLAMA_URL` — Ollama server URL (default `http://localhost:11434`); only used when `RECIPE_PROVIDER=ollama`. The model is hardcoded to `gemma4-fast`; `ollama pull gemma4-fast` is required.
- `credentials.json` — Google OAuth client credentials for Tasks API (only needed with `--tasks`)
- Google Tasks OAuth uses fixed port 8085 — redirect URI `http://localhost:8085/` must be registered in Cloud Console
- `coupons.db` — SQLite snapshot history, created on first run at `config.db_file` (project root). Gitignored. To reset, delete the file; the schema is recreated automatically.
