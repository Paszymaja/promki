import json
from pathlib import Path

import requests

BASE_URL = "https://sklep.kaufland.pl"
COUPONS_PATH = "/.klxtracoupons.json"
COUPON_ACTIVATION_PATH = "/.klcouponactivation.json"
TIMEOUT = 30


def _load_access_token(session_file: Path) -> str | None:
    try:
        with open(session_file) as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    best_token = None
    best_expiry = -1

    for origin in state.get("origins", []):
        for item in origin.get("localStorage", []):
            if "oidc.user" in item.get("name", ""):
                try:
                    user_data = json.loads(item["value"])
                    token = user_data.get("access_token")
                    if not token:
                        continue
                    expires_at = user_data.get("expires_at", 0)
                    if isinstance(expires_at, (int, float)) and expires_at > best_expiry:
                        best_expiry = expires_at
                        best_token = token
                except (json.JSONDecodeError, KeyError):
                    pass

    return best_token


class KauflandApi:
    def __init__(self, session_file: Path):
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "Accept-Language": "pl",
            "X-Requested-With": "XMLHttpRequest",
        })

        access_token = _load_access_token(session_file)
        if access_token:
            self._session.headers["Authorization"] = f"Bearer {access_token}"

        with open(session_file) as f:
            state = json.load(f)
        for c in state.get("cookies", []):
            self._session.cookies.set(
                c["name"], c["value"],
                domain=c.get("domain", ""),
                path=c.get("path", "/"),
            )

    def coupons(self) -> dict:
        resp = self._session.get(
            f"{BASE_URL}{COUPONS_PATH}",
            timeout=TIMEOUT,
        )
        if not resp.ok:
            print(f"Kaufland coupons API failed ({resp.status_code}): {resp.text[:200]}")
            resp.raise_for_status()
        return resp.json()

    def activate_coupon(self, coupon_id: str) -> bool:
        resp = self._session.post(
            f"{BASE_URL}{COUPON_ACTIVATION_PATH}",
            data={"gcn": coupon_id, "status": "activate"},
            timeout=TIMEOUT,
        )
        if not resp.ok:
            print(f"  Kaufland activation failed ({resp.status_code}): {resp.text[:200]}")
        resp.raise_for_status()
        return True
