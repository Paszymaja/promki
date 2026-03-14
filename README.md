# lidl-recipe

CLI tool that fetches your Lidl Plus coupons, auto-activates them, and optionally creates a Google Tasks shopping list or suggests recipes via Gemini.

## How it works

1. Fetches all available coupons from the Lidl Plus API
2. Activates any inactive coupons that haven't expired yet
3. Extracts food item names from coupon titles
4. Optionally: creates a Google Tasks shopping list with consumables only (`--tasks`)
5. Optionally: sends the list to Gemini for recipe suggestions in Polish (`--recipes`)

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env
```

Fill in `.env`:

- **`LIDL_ACCESS_TOKEN`** — Bearer token from the Lidl Plus API. Get it from https://www.lidl.pl/prm/promotions-list using browser dev tools (Network tab, look for the `Authorization` header).
- **`GEMINI_API_KEY`** — Free API key from https://aistudio.google.com/apikey (only needed with `--recipes`)
- `LIDL_LANGUAGE` — Language code (default: `pl`)
- `LIDL_COUNTRY` — Country code (default: `PL`)

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
# Activate all coupons (default)
uv run lidl-recipe

# Activate coupons + create shopping list in Google Tasks (consumables only)
uv run lidl-recipe --tasks

# Activate coupons + get recipe suggestions via Gemini
uv run lidl-recipe --recipes

# Both
uv run lidl-recipe --tasks --recipes
```

## Notes

- The Lidl access token expires frequently — you'll need to refresh it from the browser when it stops working.
- Coupons that return 409/412 on activation are silently skipped (already activated or not eligible).
- Non-food items (titles starting with `*` or percentage-off promos) are filtered out from the item list.
- `--tasks` further filters to consumables only (food, drinks, cleaning supplies) using a keyword blocklist, excluding electronics, clothing, tools, furniture, etc.
