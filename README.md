# lidl-recipe

CLI tool that fetches your Lidl Plus coupons, auto-activates them, and optionally creates a Google Tasks shopping list or suggests recipes via Gemini.

## How it works

1. Fetches all available coupons from the Lidl Plus API
2. Activates any inactive coupons that haven't expired yet
3. Saves a snapshot of the fetched coupons to `coupons.db` (SQLite) so changes can be diffed across runs
4. Extracts food item names from coupon titles
5. Optionally: shows what changed since the previous run (`--diff`)
6. Optionally: creates a Google Tasks shopping list with consumables only (`--tasks`)
7. Optionally: sends the list to Gemini for recipe suggestions in Polish (`--recipes`)

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env
```

### Login (recommended)

The easiest way to get a token is the built-in browser login:

```bash
uv sync --extra login          # install playwright
playwright install chromium    # download browser (first time only)
uv run lidl-recipe --login     # opens Chromium, log in manually, token saved to .env
```

The browser session is saved to `lidl_session.json` after the first login. On subsequent token refreshes the saved session is replayed silently in headless Chromium — no manual interaction needed. If the access token is rejected (HTTP 401), the CLI auto-refreshes it before retrying, so you typically only need `--login` once until the underlying session itself expires.

### Manual setup

Alternatively, fill in `.env` manually:

- **`LIDL_ACCESS_TOKEN`** — Bearer token from the Lidl Plus API. Get it from https://www.lidl.pl/prm/promotions-list using browser dev tools (Network tab, look for the `Authorization` header).
- **`GEMINI_API_KEY`** — Free API key from https://aistudio.google.com/apikey (only needed with `--recipes`)

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
# Log in via browser (saves token to .env)
uv run lidl-recipe --login

# Activate all coupons (default)
uv run lidl-recipe

# Activate coupons + create shopping list in Google Tasks (consumables only)
uv run lidl-recipe --tasks

# Activate coupons + get recipe suggestions via Gemini
uv run lidl-recipe --recipes

# Show what changed since the previous run
uv run lidl-recipe --diff

# Both
uv run lidl-recipe --tasks --recipes

# Debug: dump raw coupon JSON
uv run lidl-recipe --debug
```

## Development

```bash
uv sync
uv run pytest
```

## Notes

- The Lidl access token expires frequently, but is refreshed automatically using the saved `lidl_session.json`. Re-run `--login` only when the session itself expires.
- Coupons that return 409/412 on activation are silently skipped (already activated or not eligible).
- Non-food items (titles starting with `*` or percentage-off promos) are filtered out from the item list.
- `--tasks` further filters to consumables only (food, drinks, cleaning supplies) using a keyword blocklist, excluding electronics, clothing, tools, furniture, etc.
- Every run records a snapshot in `coupons.db` (one row per fetch in `runs`, one row per coupon in `coupon_observations`). `--diff` compares the two most recent runs and reports added/removed coupons plus changes to title, discount, expiry, or activation state. The DB is gitignored.
