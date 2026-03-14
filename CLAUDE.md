# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLI tool that fetches Lidl Plus coupons, auto-activates inactive ones, and optionally creates a Google Tasks shopping list or suggests recipes via Gemini.

## Commands

```bash
# Run the tool
uv run lidl-recipe
uv run lidl-recipe --tasks     # create Google Tasks shopping list
uv run lidl-recipe --recipes   # get Gemini recipe suggestions
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

- **`api.py`** — `LidlApi` HTTP client wrapping the Lidl Plus coupons API (Bearer token auth)
- **`coupons.py`** — `normalize_coupons()` handles varying API response shapes; `fetch_and_activate_coupons()` activates inactive coupons with rate limiting; `extract_discount_items()` extracts title + discount info; `filter_consumables()` uses keyword blocklist to exclude non-consumables
- **`tasks.py`** — `create_shopping_list()` creates a dated Google Tasks list via OAuth2
- **`gemini.py`** — `suggest_recipes()` sends item list to Google Gemini free API, responses are in Polish
- **`login.py`** — `capture_token()` opens Chromium via Playwright, intercepts Bearer token from Lidl API requests after manual login; `save_token_to_env()` upserts token in `.env`
- **`cli.py`** — `main()` orchestrates the flow: load env → fetch coupons → activate → optionally create tasks/recipes
- **`__init__.py`** — re-exports `main` for the `lidl-recipe` entrypoint

## Configuration

All config via `.env` (see `.env.example`):
- `LIDL_ACCESS_TOKEN` — Bearer token from Lidl Plus (use `--login` to capture, or grab manually from browser dev tools)
- `GEMINI_API_KEY` — Free key from Google AI Studio (only needed with `--recipes`)
- `LIDL_LANGUAGE` / `LIDL_COUNTRY` — defaults to `pl` / `PL`
- `credentials.json` — Google OAuth client credentials for Tasks API (only needed with `--tasks`)
- Google Tasks OAuth uses fixed port 8085 — redirect URI `http://localhost:8085/` must be registered in Cloud Console
