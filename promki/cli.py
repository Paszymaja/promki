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
from .recipes import RecipeError


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


def _refresh_kaufland_session(config: Config, *, allow_interactive: bool) -> bool:
    from .kaufland.login import capture_cookies

    storage = capture_cookies(session_file=config.kaufland_session_file, silent=True)
    if not storage and allow_interactive:
        storage = capture_cookies(session_file=config.kaufland_session_file, silent=False)
    return storage is not None


def _force_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main():
    _force_utf8_stdio()
    parser = argparse.ArgumentParser(description="Activate Lidl Plus and Kaufland XTRA coupons and optionally get recipe suggestions")
    parser.add_argument("--recipes", action="store_true", help="suggest recipes using Gemini based on discounted items")
    parser.add_argument("--tasks", action="store_true", help="create a Google Tasks shopping list with discounted items")
    parser.add_argument("--login", action="store_true", help="refresh Lidl Plus and Kaufland auth tokens (silent if session is saved)")
    parser.add_argument("--diff", action="store_true", help="show what changed vs the previous snapshot")
    parser.add_argument("--debug", action="store_true", help="dump raw coupon JSON and exit")
    args = parser.parse_args()

    config = Config.from_env()

    if args.login:
        print("--- Lidl login ---")
        if config.lidl_session_file.exists():
            print("Saved session found — refreshing token silently...")
        if _refresh_token(config, allow_interactive=True):
            print("Lidl token saved to .env")
        else:
            sys.exit("Lidl login failed.")

        print("\n--- Kaufland login ---")
        if config.kaufland_session_file.exists():
            print("Saved session found — refreshing silently...")
        if not _refresh_kaufland_session(config, allow_interactive=True):
            sys.exit("Kaufland login failed.")
        print("Kaufland session saved.")

        if not args.recipes and not args.tasks and not args.debug and not args.diff:
            return

    # --- Lidl flow ---
    lidl_coupons: list[dict] = []
    if config.access_token or _refresh_token(config, allow_interactive=False):
        config.require_access_token()
        api = LidlApi(config.access_token)

        print("\nFetching Lidl coupons...")
        if args.debug:
            raw = api.coupons()
            coupons = normalize_coupons(raw)
            print(json.dumps(coupons[:3], indent=2, ensure_ascii=False))
        else:
            try:
                lidl_coupons = fetch_and_activate_coupons(api)
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 401:
                    print("Token rejected — attempting silent refresh...")
                    if not _refresh_token(config, allow_interactive=False):
                        sys.exit("Silent refresh failed. Run: uv run promki --login")
                    api = LidlApi(config.access_token)
                    lidl_coupons = fetch_and_activate_coupons(api)
                else:
                    raise

            try:
                save_snapshot(config.db_file, lidl_coupons, source="lidl")
            except (sqlite3.Error, SchemaVersionError) as e:
                print(f"Warning: failed to save Lidl coupon snapshot: {e}")
    else:
        print("No Lidl token available — skipping Lidl coupons.")

    # --- Kaufland flow ---
    kaufland_coupons: list[dict] = []
    if config.kaufland_session_file.exists():
        from .kaufland import fetch_and_activate_kaufland_coupons, KauflandApi

        print("\nFetching Kaufland coupons...")
        try:
            kaufland_api = KauflandApi(config.kaufland_session_file)
            kaufland_coupons = fetch_and_activate_kaufland_coupons(kaufland_api)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code in (401, 403):
                print("Kaufland session expired — attempting silent refresh...")
                if _refresh_kaufland_session(config, allow_interactive=False):
                    kaufland_api = KauflandApi(config.kaufland_session_file)
                    kaufland_coupons = fetch_and_activate_kaufland_coupons(kaufland_api)
                else:
                    print("Silent refresh failed — skipping Kaufland coupons.")
            else:
                raise

        try:
            save_snapshot(config.db_file, kaufland_coupons, source="kaufland")
        except (sqlite3.Error, SchemaVersionError) as e:
            print(f"Warning: failed to save Kaufland coupon snapshot: {e}")
    else:
        print("No Kaufland session found — skipping Kaufland coupons. Run --login first.")

    if args.debug:
        return

    # --- Diff ---
    if args.diff:
        try:
            print_diff(diff_latest(config.db_file, source="lidl"))
            print_diff(diff_latest(config.db_file, source="kaufland"))
        except (sqlite3.Error, SchemaVersionError) as e:
            print(f"Warning: failed to compute diff: {e}")

    # --- Display items from both stores ---
    all_items = extract_discount_items(lidl_coupons) + extract_discount_items(kaufland_coupons)
    if all_items:
        print(f"\n{len(all_items)} discounted items:")
        for item in all_items:
            desc = f" — {item['description'].split(chr(10))[0]}" if item["description"] else ""
            valid = f"  (do {item['valid_until'].strftime('%d.%m')})" if item.get("valid_until") else ""
            print(f"  - {item['title']}{desc}{valid}")

    # --- Tasks ---
    if args.tasks:
        if not all_items:
            print("No food items found for shopping list.")
            return
        consumables = filter_consumables(all_items)
        if not consumables:
            print("No consumable items found.")
            return
        from .tasks import create_shopping_list

        create_shopping_list(consumables, config)

    # --- Recipes ---
    if args.recipes:
        if not all_items:
            print("No food items found for recipe suggestions.")
            return
        provider = config.require_recipe_provider()
        try:
            if provider == "ollama":
                from .ollama import suggest_recipes

                print("\nAsking Ollama for recipe suggestions...\n")
                recipes = suggest_recipes(all_items, config.ollama_url)
            else:
                from .gemini import suggest_recipes

                print("\nAsking Gemini for recipe suggestions...\n")
                recipes = suggest_recipes(all_items, config.require_gemini_key())
        except RecipeError as e:
            sys.exit(str(e))
        print(recipes)


if __name__ == "__main__":
    main()
