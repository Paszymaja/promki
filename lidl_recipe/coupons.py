import re
import time
from datetime import datetime, timezone

import requests

from .api import LidlApi


_NON_CONSUMABLE_KEYWORDS = [
    "robot", "termorobot", "laser", "akumulat",
    "spodnie", "bluza", "kurtka", "buty", "skarpet", "odzie",
    "kettlebell", "hantle", "hantel", "stojak", "ćwicze",
    "plecak", "torba", "walizk",
    "szklan", "garnek", "patelni", "nóż", "noże",
    "zabawk", "klock",
    "telewiz", "laptop", "tablet", "słuchaw", "głośnik",
    "mebl", "fotel", "krzesł", "stół", "biurk", "szafk",
    "narzędzi", "wiertark", "wkrętak", "klucz",
    "akcesori", "zestaw", "koszula"
]


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
                    time.sleep(0.5)
                except requests.HTTPError as e:
                    if e.response is not None and e.response.status_code in (409, 412):
                        print(f"  Skipped: {title}")
                    else:
                        print(f"  Failed to activate '{title}': {e}")
        else:
            print(f"  Already active: {title}")

    return coupons


def extract_discount_items(coupons: list[dict]) -> list[dict]:
    seen = set()
    items = []
    for coupon in coupons:
        title = coupon.get("title", "").strip()
        if not title or title in seen:
            continue
        if title.startswith("*") or re.match(r"^-?\d+%", title):
            continue
        seen.add(title)

        details = []
        discount = coupon.get("discount", {})
        if isinstance(discount, dict):
            disc_title = discount.get("title", "")
            if disc_title and disc_title != title:
                details.append(disc_title)
            disc_desc = discount.get("description", "")
            if disc_desc and disc_desc != title:
                details.append(disc_desc)

        items.append({"title": title, "description": "\n".join(details)})
    return items


def filter_consumables(items: list[dict]) -> list[dict]:
    result = []
    for item in items:
        title_lower = item["title"].lower()
        if any(kw in title_lower for kw in _NON_CONSUMABLE_KEYWORDS):
            continue
        result.append(item)
    return result
