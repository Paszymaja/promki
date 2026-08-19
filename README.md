# promki

CLI tool that fetches and activates coupons from **Lidl Plus** and **Kaufland Card XTRA**.

## How it works

1. Logs into both Lidl Plus and Kaufland Card XTRA (via Playwright, saves sessions)
2. Fetches all available coupons from both stores
3. Activates inactive coupons that haven't expired yet (skips points-required Kaufland coupons)
4. Saves snapshots to `coupons.db` (SQLite) so changes can be diffed across runs
5. Extracts food item names from coupon titles
6. Optionally: shows Lidl and Kaufland changes since the previous run (`--diff`)

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

### Login

The built-in browser login captures auth sessions for both stores:

```bash
uv sync --extra login          # install playwright
playwright install chromium    # download browser (first time only)
uv run promki --login          # opens Chromium, logs into both Lidl and Kaufland
```

Browser sessions are saved to `lidl_session.json` and `kaufland_session.json`. Both tokens are read from these files on each run (Lidl's `authToken` cookie, Kaufland's `oidc.user` token). On subsequent runs, expired tokens are silently refreshed via saved sessions — no manual interaction needed. Re-run `--login` only when the underlying sessions expire.

## Usage

```bash
# Log into both Lidl Plus and Kaufland Card XTRA
uv run promki --login

# Fetch and activate all coupons from both stores
uv run promki

# Show what changed since the previous run (per-store diffs)
uv run promki --diff

# Debug: dump raw Lidl coupon JSON
uv run promki --debug
```

## Development

```bash
uv sync
uv run pytest
```
