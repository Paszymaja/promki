import argparse
import json
import sqlite3
import sys

import requests

from .api import LidlApi
from .config import Config
from .coupons import (
    extract_discount_items,
    fetch_and_activate_coupons,
    filter_consumables,
    normalize_coupons,
)
from .db import SchemaVersionError, diff_latest, print_diff, save_snapshot


def _refresh_token(config: Config, *, allow_interactive: bool) -> bool:
    from .login import capture_token

    token = capture_token(session_file=config.lidl_session_file, silent=True)
    if not token and allow_interactive:
        token = capture_token(session_file=config.lidl_session_file, silent=False)
    if not token:
        return False
    config.save_token(token)
    config.reload()
    return True


def _force_utf8_stdio() -> None:
    # Windows defaults stdout to cp1250, which can't encode bidi marks (‎)
    # or some emoji/CJK glyphs that occasionally appear in Lidl coupon titles.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main():
    _force_utf8_stdio()
    parser = argparse.ArgumentParser(description="Activate Lidl Plus coupons and optionally get recipe suggestions")
    parser.add_argument("--recipes", action="store_true", help="suggest recipes using Gemini based on discounted items")
    parser.add_argument("--tasks", action="store_true", help="create a Google Tasks shopping list with discounted items")
    parser.add_argument("--login", action="store_true", help="refresh Lidl Plus auth token (silent if session is saved)")
    parser.add_argument("--diff", action="store_true", help="show what changed vs the previous snapshot")
    parser.add_argument("--debug", action="store_true", help="dump raw coupon JSON and exit")
    args = parser.parse_args()

    config = Config.from_env()

    if args.login:
        if config.lidl_session_file.exists():
            print("Saved session found — refreshing token silently...")
        if not _refresh_token(config, allow_interactive=True):
            sys.exit("Login failed.")
        print("Token saved to .env")
        if not args.recipes and not args.tasks and not args.debug and not args.diff:
            return

    if not config.access_token and not _refresh_token(config, allow_interactive=False):
        config.require_access_token()  # exits with helpful message

    api = LidlApi(config.access_token)

    print("Fetching coupons...")
    if args.debug:
        raw = api.coupons()
        coupons = normalize_coupons(raw)
        print(json.dumps(coupons[:3], indent=2, ensure_ascii=False))
        return

    try:
        coupons = fetch_and_activate_coupons(api)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            print("Token rejected — attempting silent refresh...")
            if not _refresh_token(config, allow_interactive=False):
                sys.exit("Silent refresh failed. Run: uv run lidl-recipe --login")
            api = LidlApi(config.access_token)
            coupons = fetch_and_activate_coupons(api)
        else:
            raise

    try:
        save_snapshot(config.db_file, coupons)
    except (sqlite3.Error, SchemaVersionError) as e:
        print(f"Warning: failed to save coupon snapshot: {e}")

    if args.diff:
        try:
            print_diff(diff_latest(config.db_file))
        except (sqlite3.Error, SchemaVersionError) as e:
            print(f"Warning: failed to compute diff: {e}")

    items = extract_discount_items(coupons)
    if items:
        print(f"\n{len(items)} discounted items:")
        for item in items:
            desc = f" — {item['description'].split(chr(10))[0]}" if item["description"] else ""
            valid = f"  (do {item['valid_until'].strftime('%d.%m')})" if item.get("valid_until") else ""
            print(f"  - {item['title']}{desc}{valid}")

    if args.tasks:
        if not items:
            print("No food items found for shopping list.")
            return
        consumables = filter_consumables(items)
        if not consumables:
            print("No consumable items found.")
            return
        from .tasks import create_shopping_list

        create_shopping_list(consumables, config)

    if args.recipes:
        if not items:
            print("No food items found for recipe suggestions.")
            return
        print("\nAsking for recipe suggestions...\n")
        from .gemini import suggest_recipes

        recipes = suggest_recipes(items, config.require_gemini_key())
        print(recipes)


if __name__ == "__main__":
    main()
