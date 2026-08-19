# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLI tool that fetches Lidl Plus and Kaufland XTRA coupons and auto-activates inactive ones.

## Commands

```bash
# Run the tool (activates both Lidl and Kaufland coupons)
uv run promki
uv run promki --diff      # show what changed vs the previous snapshot
uv run promki --login     # open browser, log in to both Lidl and Kaufland, tokens saved automatically

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

Package `promki/` with modules:

- **`config.py`** — `Config` dataclass holding `project_root` and exposing derived paths: `lidl_session_file`, `kaufland_session_file`, `db_file`
- **`api.py`** — `LidlApi` HTTP client wrapping the Lidl Plus coupons API (Bearer token auth)
- **`coupons.py`** — `normalize_coupons()` handles varying API response shapes; `fetch_and_activate_coupons()` activates inactive coupons with rate limiting; `extract_discount_items()` extracts title + discount info
- **`login.py`** — `load_access_token(session_file)` reads the Lidl Bearer token (`authToken` cookie) from `lidl_session.json` without launching a browser; `capture_token(session_file, silent)` uses Playwright to (re)capture it. Persists `storage_state` to `lidl_session.json` so subsequent calls can replay the session headlessly (`silent=True`); falls back to interactive Chromium when no saved session is available. CLI auto-invokes silent refresh on missing token or HTTP 401.
- **`db.py`** — SQLite snapshot store at `config.db_file` (`coupons.db`). Two-table schema (`runs` + `coupon_observations`) versioned via `PRAGMA user_version`; `save_snapshot()` always records a run (even when empty); `diff_latest()` compares the two most recent runs on `(title, discount_title, discount_description, valid_end, is_activated)`. Schema v2 adds `source` column (`"lidl"` or `"kaufland"`). Schema mismatches raise `SchemaVersionError`. All timestamps written via `_utc_now_iso()` so lex-sort matches chronological order.
- **`cli.py`** — `main()` orchestrates the flow: reconfigure stdio to UTF-8 (Windows cp1250 can't render some Polish/bidi chars) → load config → fetch Lidl coupons → activate → fetch Kaufland coupons → activate → save snapshots → optionally show diff. DB failures (`sqlite3.Error`, `SchemaVersionError`) are caught and logged as warnings; they never abort the run.
- **`kaufland/`** — Kaufland Card XTRA subpackage:
  - **`api.py`** — `KauflandApi` HTTP client using `requests.Session` with Bearer token loaded from localStorage in the Playwright storage state and session cookies. Endpoints: `/.klxtracoupons.json` (GET coupons), `/.klcouponactivation.json` (POST form `gcn` + `status=activate`).
  - **`coupons.py`** — `normalize_kaufland_coupons()` handles various API response shapes; `fetch_and_activate_kaufland_coupons()` activates only free coupons (skips points-required); `_is_free_coupon()` filters out premium/points coupons.
  - **`login.py`** — `capture_cookies(session_file, silent)` uses Playwright to log into Kaufland via Google OAuth through Cidaas OIDC. Captures full browser storage state to `kaufland_session.json`.
- **`__init__.py`** — re-exports `main` for the `promki` entrypoint

## Configuration

Auth is stored in Playwright session files (no `.env`):
- `lidl_session.json` — Lidl Plus browser session; the Bearer token is read from the `authToken` cookie by `load_access_token()` and refreshed via `capture_token()` when missing/expired. Gitignored.
- `kaufland_session.json` — Kaufland Card XTRA browser session; the Bearer token is read from localStorage (`oidc.user`) by `KauflandApi`. Managed automatically via `--login`. Gitignored.
- `coupons.db` — SQLite snapshot history, created on first run at `config.db_file` (project root). Gitignored. To reset, delete the file; the schema is recreated automatically.
