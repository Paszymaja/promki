# promki

CLI tool that fetches and activates coupons from **Lidl Plus** and **Kaufland Card XTRA**, then optionally creates a Google Tasks shopping list or suggests recipes via Gemini / Ollama.

## How it works

1. Logs into both Lidl Plus and Kaufland Card XTRA (via Playwright, saves sessions)
2. Fetches all available coupons from both stores
3. Activates inactive coupons that haven't expired yet (skips points-required Kaufland coupons)
4. Saves snapshots to `coupons.db` (SQLite) so changes can be diffed across runs
5. Extracts food item names from coupon titles
6. Optionally: shows Lidl and Kaufland changes since the previous run (`--diff`)
7. Optionally: creates a Google Tasks shopping list with consumables only (`--tasks`)
8. Optionally: sends the item list to AI for recipe suggestions in Polish (`--recipes`)

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env
```

### Login (recommended)

The easiest way is the built-in browser login for both stores:

```bash
uv sync --extra login          # install playwright
playwright install chromium    # download browser (first time only)
uv run promki --login          # opens Chromium, logs into both Lidl and Kaufland
```

Browser sessions are saved to `lidl_session.json` and `kaufland_session.json`. On subsequent runs, expired tokens are silently refreshed via saved sessions — no manual interaction needed. Re-run `--login` only when the underlying sessions expire.

### Manual setup

Alternatively, fill in `.env`:

- **`LIDL_ACCESS_TOKEN`** — Bearer token from the Lidl Plus API. Get it from https://www.lidl.pl/prm/promotions-list using browser dev tools (Network tab, look for the `Authorization` header).
- **`GEMINI_API_KEY`** — Free API key from https://aistudio.google.com/apikey (only needed with `--recipes`)
- **`RECIPE_PROVIDER`** — `gemini` (default) or `ollama` for local AI recipe suggestions
- **`OLLAMA_URL`** — Ollama server URL (default `http://localhost:11434`)

### Google Tasks setup (for `--tasks`)

1. Create a project at https://console.cloud.google.com
2. Enable the **Google Tasks API**
3. Configure the **OAuth consent screen** (External, add yourself as test user)
4. Create **OAuth 2.0 Client ID** credentials (Desktop app type)
5. Add `http://localhost:8085/` as an **Authorized redirect URI**
6. Download the JSON and save it as `credentials.json` in the project root
7. On first run with `--tasks`, a browser window opens for authorization. The token is cached in `tasks_token.json`.

## Usage

```bash
# Log into both Lidl Plus and Kaufland Card XTRA
uv run promki --login

# Fetch and activate all coupons from both stores
uv run promki

# Activate coupons + create shopping list in Google Tasks (consumables only)
uv run promki --tasks

# Activate coupons + get recipe suggestions via Gemini
uv run promki --recipes

# Show what changed since the previous run (per-store diffs)
uv run promki --diff

# Both tasks and recipes
uv run promki --tasks --recipes

# Debug: dump raw Lidl coupon JSON
uv run promki --debug
```

## Development

```bash
uv sync
uv run pytest
```
