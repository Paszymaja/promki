import argparse
import json
import os
import sys

from dotenv import load_dotenv

from .api import LidlApi
from .coupons import (
    extract_discount_items,
    fetch_and_activate_coupons,
    filter_consumables,
    normalize_coupons,
)
from .gemini import suggest_recipes
from .tasks import create_shopping_list


def main():
    parser = argparse.ArgumentParser(description="Activate Lidl Plus coupons and optionally get recipe suggestions")
    parser.add_argument("--recipes", action="store_true", help="suggest recipes using Gemini based on discounted items")
    parser.add_argument("--tasks", action="store_true", help="create a Google Tasks shopping list with discounted items")
    parser.add_argument("--login", action="store_true", help="open browser to capture Lidl Plus auth token")
    parser.add_argument("--debug", action="store_true", help="dump raw coupon JSON and exit")
    args = parser.parse_args()

    load_dotenv()

    if args.login:
        from .login import capture_token, save_token_to_env

        country = os.getenv("LIDL_COUNTRY", "PL")
        token = capture_token(country=country)
        save_token_to_env(token)
        print("Token saved to .env")
        if not args.recipes and not args.tasks and not args.debug:
            return
        load_dotenv(override=True)

    access_token = os.getenv("LIDL_ACCESS_TOKEN", "")
    if not access_token:
        print("No LIDL_ACCESS_TOKEN found in .env")
        print("Run: uv run lidl-recipe --login")
        sys.exit(1)

    language = os.getenv("LIDL_LANGUAGE", "pl")
    country = os.getenv("LIDL_COUNTRY", "PL")
    api = LidlApi(language, country, access_token)

    print("Fetching coupons...")
    if args.debug:
        raw = api.coupons()
        coupons = normalize_coupons(raw)
        print(json.dumps(coupons[:3], indent=2, ensure_ascii=False))
        return
    coupons = fetch_and_activate_coupons(api)

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
        create_shopping_list(consumables)

    if args.recipes:
        if not items:
            print("No food items found for recipe suggestions.")
            return
        print("\nAsking for recipe suggestions...\n")
        recipes = suggest_recipes(items)
        print(recipes)


if __name__ == "__main__":
    main()
