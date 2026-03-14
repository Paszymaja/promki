# lidl-recipe

CLI tool that fetches your Lidl Plus coupons, auto-activates them, and uses Google Gemini to suggest recipes based on your discounted items.

## How it works

1. Fetches all available coupons from the Lidl Plus API
2. Activates any inactive coupons that haven't expired yet
3. Extracts food item names from coupon titles
4. Sends the list to Gemini and gets 3 recipe suggestions in Polish

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env
```

Fill in `.env`:

- **`LIDL_ACCESS_TOKEN`** — Bearer token from the Lidl Plus API. Get it from https://www.lidl.pl/prm/promotions-list using browser dev tools (Network tab, look for the `Authorization` header).
- **`GEMINI_API_KEY`** — Free API key from https://aistudio.google.com/apikey
- `LIDL_LANGUAGE` — Language code (default: `pl`)
- `LIDL_COUNTRY` — Country code (default: `PL`)

## Usage

```bash
# Activate all coupons (default)
uv run lidl-recipe

# Activate coupons + get recipe suggestions via Gemini
uv run lidl-recipe --recipes
```

## Notes

- The Lidl access token expires frequently — you'll need to refresh it from the browser when it stops working.
- Coupons that return 409/412 on activation are silently skipped (already activated or not eligible).
- Non-food items (titles starting with `*` or percentage-off promos) are filtered out before sending to Gemini.
