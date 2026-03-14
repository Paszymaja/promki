import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

COUPONS_API = "https://coupons.lidlplus.com/app/api"
TIMEOUT = 30


# --- Lidl API ---


class LidlApi:
    def __init__(self, language, country, access_token):
        self._language = language
        self._country = country
        self._token = access_token

    def _headers(self):
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "Accept-Language": self._language,
            "Country": self._country,
        }

    def coupons(self):
        resp = requests.get(
            f"{COUPONS_API}/v2/promotionsList",
            headers=self._headers(),
            timeout=TIMEOUT,
        )
        if not resp.ok:
            print(f"Coupons API failed ({resp.status_code}): {resp.text[:200]}")
            resp.raise_for_status()
        return resp.json()

    def activate_coupon(self, coupon_id):
        resp = requests.post(
            f"{COUPONS_API}/v1/promotions/{coupon_id}/activation",
            headers=self._headers(),
            timeout=TIMEOUT,
        )
        resp.raise_for_status()


# --- Coupons ---


def normalize_coupons(raw) -> list[dict]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        coupons = []
        for section in raw.get("sections", []):
            coupons.extend(section.get("coupons", section.get("promotions", [])))
        if not coupons:
            coupons = raw.get("coupons", raw.get("promotions", []))
        return coupons
    return []


def fetch_and_activate_coupons(api: LidlApi) -> list[dict]:
    raw = api.coupons()
    coupons = normalize_coupons(raw)

    print(f"Found {len(coupons)} coupons")

    for coupon in coupons:
        title = coupon.get("title", "Unknown")
        is_activated = coupon.get("isActivated", True)
        validity = coupon.get("validity", {})
        end = validity.get("end", "")

        if not is_activated and end:
            try:
                end_dt = datetime.fromisoformat(end)
            except ValueError:
                continue
            if end_dt < datetime.now(timezone.utc):
                continue
            coupon_id = coupon.get("id", "")
            if coupon_id:
                try:
                    api.activate_coupon(coupon_id)
                    print(f"  Activated: {title}")
                except requests.HTTPError as e:
                    if e.response is not None and e.response.status_code in (409, 412):
                        print(f"  Skipped: {title}")
                    else:
                        print(f"  Failed to activate '{title}': {e}")
                time.sleep(0.5)
        else:
            print(f"  Already active: {title}")

    return coupons


def extract_discount_items(coupons: list[dict]) -> list[str]:
    seen = set()
    items = []
    for coupon in coupons:
        title = coupon.get("title", "").strip()
        if not title or title in seen:
            continue
        # Skip non-food items and generic percentage-off promos
        if title.startswith("*") or re.match(r"^-?\d+%", title):
            continue
        seen.add(title)
        items.append(title)
    return items


# --- Google Tasks ---


TASKS_SCOPES = ["https://www.googleapis.com/auth/tasks"]
TASKS_TOKEN_FILE = "tasks_token.json"
TASKS_CREDENTIALS_FILE = "credentials.json"


def get_tasks_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(TASKS_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TASKS_TOKEN_FILE, TASKS_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(TASKS_CREDENTIALS_FILE):
                print(f"Missing {TASKS_CREDENTIALS_FILE}")
                print("Download OAuth client credentials from https://console.cloud.google.com/apis/credentials")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(TASKS_CREDENTIALS_FILE, TASKS_SCOPES)
            creds = flow.run_local_server(port=8085)
        with open(TASKS_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("tasks", "v1", credentials=creds)


def create_shopping_list(items: list[str]):
    service = get_tasks_service()

    today = datetime.now().strftime("%d.%m.%Y")
    list_title = f"Lidl promocje {today}"

    tasklist = service.tasklists().insert(body={"title": list_title}).execute()
    tasklist_id = tasklist["id"]
    print(f"\nCreated task list: {list_title}")

    for item in items:
        service.tasks().insert(tasklist=tasklist_id, body={"title": item}).execute()
        print(f"  + {item}")

    print(f"\n{len(items)} items added to Google Tasks")


# --- Recipes ---


def suggest_recipes(items: list[str]) -> str:
    item_list = "\n".join(f"- {item}" for item in items)
    prompt = (
        "I have the following discounted items available at Lidl this week:\n\n"
        f"{item_list}\n\n"
        "Please suggest 3 creative and practical recipes I can make using "
        "some of these discounted items. Ignore items that are clearly not "
        "food ingredients (e.g. cleaning products, cosmetics, household items). "
        "For each recipe, list the ingredients (marking which ones are from "
        "the discount list) and brief cooking instructions. Answer in Polish."
    )

    # Use Google Gemini free API
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        print("No GEMINI_API_KEY found in .env")
        print("Get a free key at https://aistudio.google.com/apikey")
        sys.exit(1)

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    resp = requests.post(
        url,
        params={"key": api_key},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=60,
    )
    if not resp.ok:
        print(f"Gemini API failed ({resp.status_code}): {resp.text[:200]}")
        sys.exit(1)

    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        print("Unexpected Gemini response:")
        print(json.dumps(data, indent=2)[:500])
        sys.exit(1)


# --- Main ---


def main():
    parser = argparse.ArgumentParser(description="Activate Lidl Plus coupons and optionally get recipe suggestions")
    parser.add_argument("--recipes", action="store_true", help="suggest recipes using Gemini based on discounted items")
    parser.add_argument("--tasks", action="store_true", help="create a Google Tasks shopping list with discounted items")
    args = parser.parse_args()

    load_dotenv()

    access_token = os.getenv("LIDL_ACCESS_TOKEN", "")
    if not access_token:
        print("No LIDL_ACCESS_TOKEN found in .env")
        print("Get it from https://www.lidl.pl/prm/promotions-list (browser dev tools → Network → Authorization header)")
        sys.exit(1)

    language = os.getenv("LIDL_LANGUAGE", "pl")
    country = os.getenv("LIDL_COUNTRY", "PL")
    api = LidlApi(language, country, access_token)

    print("Fetching coupons...")
    coupons = fetch_and_activate_coupons(api)

    items = extract_discount_items(coupons)
    if items:
        print(f"\n{len(items)} discounted items:")
        for item in items:
            print(f"  - {item}")

    if args.tasks:
        if not items:
            print("No food items found for shopping list.")
            return
        create_shopping_list(items)

    if args.recipes:
        if not items:
            print("No food items found for recipe suggestions.")
            return
        print("\nAsking for recipe suggestions...\n")
        recipes = suggest_recipes(items)
        print(recipes)


if __name__ == "__main__":
    main()
