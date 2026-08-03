from datetime import datetime, timezone

import requests

from .api import KauflandApi

ACTIVATION_DELAY = 0.5  # seconds between activations


def normalize_kaufland_coupons(raw) -> list[dict]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        xtra = raw.get("xtraCoupons")
        if isinstance(xtra, dict):
            coupons = []
            for category_data in xtra.values():
                if isinstance(category_data, list):
                    coupons.extend(category_data)
            return coupons
        for key in ("coupons", "data", "storeCoupons", "couponList"):
            if key in raw and isinstance(raw[key], list):
                return raw[key]
        return []
    return []


def _is_free_coupon(coupon: dict) -> bool:
    loyalty_points = coupon.get("loyaltyPoints")
    if isinstance(loyalty_points, (int, float)) and loyalty_points > 0:
        return False
    return True


def _is_expired(coupon: dict) -> bool:
    end_str = coupon.get("endDate", "")
    if not end_str:
        return False
    try:
        end_dt = datetime.fromisoformat(end_str)
    except (ValueError, TypeError):
        return False
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)
    return end_dt < datetime.now(timezone.utc)


def _get_coupon_title(coupon: dict) -> str:
    return coupon.get("name", coupon.get("title", "Unknown"))


def _get_coupon_id(coupon: dict) -> str:
    return coupon.get("gcn", coupon.get("id", ""))


def fetch_and_activate_kaufland_coupons(api: KauflandApi) -> list[dict]:
    import time as _time

    raw = api.coupons()
    coupons = normalize_kaufland_coupons(raw)

    print(f"Found {len(coupons)} Kaufland coupons")

    for coupon in coupons:
        coupon_id = _get_coupon_id(coupon)
        title = _get_coupon_title(coupon)
        status = coupon.get("status", "")
        is_activated = status == "ACTIVATED"

        if is_activated:
            print(f"  Already active: {title}")
            continue

        if not _is_free_coupon(coupon):
            print(f"  Skipped (requires points): {title}")
            continue

        if _is_expired(coupon):
            print(f"  Skipped (expired): {title}")
            continue

        if coupon_id:
            try:
                api.activate_coupon(coupon_id)
                print(f"  Activated: {title}")
                _time.sleep(ACTIVATION_DELAY)
            except requests.HTTPError as e:
                status_code = e.response.status_code if e.response is not None else 0
                if status_code in (400, 409, 412):
                    print(f"  Skipped: {title}")
                else:
                    print(f"  Failed to activate '{title}': {e}")
                continue
        else:
            print(f"  Skipped (no id): {title}")

    return coupons
