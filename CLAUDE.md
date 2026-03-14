# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLI tool that fetches Lidl Plus coupons, auto-activates inactive ones, extracts discounted food items, and uses Google Gemini to suggest recipes in Polish.

## Commands

```bash
# Run the tool
uv run lidl-recipe
# or
uv run python main.py

# Install dependencies
uv sync
```

No tests or linter configured.

## Architecture

Single-file app (`main.py`) with four sections:

- **LidlApi** — HTTP client wrapping the Lidl Plus coupons API (Bearer token auth)
- **Coupon processing** — `normalize_coupons()` handles varying API response shapes; `fetch_and_activate_coupons()` activates inactive coupons with rate limiting; `extract_discount_items()` filters to food-only items
- **Recipe generation** — `suggest_recipes()` sends item list to Google Gemini free API, responses are in Polish
- **main()** — orchestrates the flow: load env → fetch coupons → activate → extract items → suggest recipes

## Configuration

All config via `.env` (see `.env.example`):
- `LIDL_ACCESS_TOKEN` — Bearer token from Lidl Plus (expires frequently, must be refreshed from browser dev tools)
- `GEMINI_API_KEY` — Free key from Google AI Studio
- `LIDL_LANGUAGE` / `LIDL_COUNTRY` — defaults to `pl` / `PL`
