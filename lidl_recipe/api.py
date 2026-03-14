import requests

COUPONS_API = "https://coupons.lidlplus.com/app/api"
TIMEOUT = 30


class LidlApi:
    def __init__(self, access_token):
        self._token = access_token

    def _headers(self):
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "Accept-Language": "pl",
            "Country": "PL",
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
        if not resp.ok:
            print(f"Activate coupon failed ({resp.status_code}): {resp.text[:200]}")
        resp.raise_for_status()
