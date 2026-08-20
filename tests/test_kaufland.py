import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from promki.kaufland.api import KauflandApi, _load_access_token
from promki.kaufland.coupons import (
    _get_coupon_id,
    _get_coupon_title,
    _is_expired,
    _is_free_coupon,
    normalize_kaufland_coupon,
    normalize_kaufland_coupons,
)


def _make_coupon(**overrides):
    base = {
        "couponTarget": 4,
        "couponType": 1,
        "gcn": "000001234",
        "name": "Maslo Polskie ekstra",
        "brand": "Mlekovita",
        "startDate": "2026-07-23T00:00:00+02:00",
        "endDate": "2099-12-31T23:59:59+01:00",
        "status": 0,
        "loyaltyPoints": None,
    }
    base.update(overrides)
    return base


# --- normalize_kaufland_coupons ---


def test_normalize_kaufland_list():
    raw = [{"gcn": "1"}, {"gcn": "2"}]
    assert normalize_kaufland_coupons(raw) == raw


def test_normalize_kaufland_xtracoupons():
    raw = {
        "xtraCoupons": {
            "Prioritized": [_make_coupon(gcn="1")],
            "Articles": [_make_coupon(gcn="2"), _make_coupon(gcn="3")],
            "Marketplace": [_make_coupon(gcn="4")],
        }
    }
    result = normalize_kaufland_coupons(raw)
    assert len(result) == 4
    assert [c["gcn"] for c in result] == ["1", "2", "3", "4"]


def test_normalize_kaufland_empty():
    assert normalize_kaufland_coupons({}) == []
    assert normalize_kaufland_coupons(None) == []
    assert normalize_kaufland_coupons("unexpected") == []


# --- _is_free_coupon ---


def test_is_free_coupon_none():
    assert _is_free_coupon(_make_coupon(loyaltyPoints=None)) is True


def test_is_free_coupon_zero():
    assert _is_free_coupon(_make_coupon(loyaltyPoints=0)) is True


def test_is_free_coupon_no_field():
    c = _make_coupon()
    del c["loyaltyPoints"]
    assert _is_free_coupon(c) is True


def test_is_free_coupon_with_points():
    assert _is_free_coupon(_make_coupon(loyaltyPoints=800)) is False


# --- _is_expired ---


def test_is_expired_future():
    assert _is_expired(_make_coupon(endDate="2099-12-31T23:59:59Z")) is False


def test_is_expired_past():
    assert _is_expired(_make_coupon(endDate="2020-01-01T00:00:00Z")) is True


def test_is_expired_no_date():
    c = _make_coupon()
    del c["endDate"]
    assert _is_expired(c) is False


# --- _get_coupon_title / _get_coupon_id ---


def test_get_coupon_title():
    assert _get_coupon_title(_make_coupon()) == "Maslo Polskie ekstra"
    assert _get_coupon_title({"title": "fallback"}) == "fallback"
    assert _get_coupon_title({}) == "Unknown"


def test_get_coupon_id():
    assert _get_coupon_id(_make_coupon()) == "000001234"
    assert _get_coupon_id({"id": "fallback"}) == "fallback"
    assert _get_coupon_id({}) == ""


# --- normalize_kaufland_coupon ---


def test_normalize_kaufland_coupon_maps_common_shape():
    result = normalize_kaufland_coupon(_make_coupon())
    assert result["id"] == "000001234"
    assert result["title"] == "Maslo Polskie ekstra"
    assert result["discount"] == {}
    assert result["validity"] == {
        "start": "2026-07-23T00:00:00+02:00",
        "end": "2099-12-31T23:59:59+01:00",
    }
    assert result["isActivated"] is False


def test_normalize_kaufland_coupon_activated_status():
    result = normalize_kaufland_coupon(_make_coupon(status="ACTIVATED"))
    assert result["isActivated"] is True


def test_normalize_kaufland_coupon_preserves_raw_fields():
    coupon = _make_coupon(brand="Mlekovita")
    result = normalize_kaufland_coupon(coupon)
    assert result["gcn"] == "000001234"
    assert result["name"] == "Maslo Polskie ekstra"
    assert result["brand"] == "Mlekovita"
    assert result["status"] == 0
    assert result["loyaltyPoints"] is None


def test_normalize_kaufland_coupon_fallback_id_title():
    result = normalize_kaufland_coupon({"id": "x", "title": "T", "status": "ACTIVATED"})
    assert result["id"] == "x"
    assert result["title"] == "T"
    assert result["validity"] == {"start": "", "end": ""}


def test_normalize_kaufland_coupon_empty():
    result = normalize_kaufland_coupon({})
    assert result["id"] == ""
    assert result["title"] == "Unknown"
    assert result["isActivated"] is False


# --- _load_access_token ---


def test_load_access_token_from_session(tmp_path):
    session = {
        "origins": [{
            "origin": "https://sklep.kaufland.pl",
            "localStorage": [
                {"name": "oidc.user:https://account.kaufland.com:f5078774-97e2-4bdd-985c-dc8c4095bf0f",
                 "value": json.dumps({"access_token": "test-token-abc"})},
            ]
        }]
    }
    f = tmp_path / "session.json"
    f.write_text(json.dumps(session))
    assert _load_access_token(f) == "test-token-abc"


# --- KauflandApi ---


@patch("promki.kaufland.api.requests.Session.get")
def test_kaufland_api_coupons_with_token(mock_get, tmp_path):
    session = {
        "cookies": [],
        "origins": [{
            "localStorage": [
                {"name": "oidc.user:https://account.kaufland.com:f5078774-97e2-4bdd-985c-dc8c4095bf0f",
                 "value": json.dumps({"access_token": "mytoken"})},
            ]
        }]
    }
    f = tmp_path / "session.json"
    f.write_text(json.dumps(session))

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"xtraCoupons": {"Articles": []}}
    mock_get.return_value = mock_resp

    api = KauflandApi(f)
    result = api.coupons()
    assert result == {"xtraCoupons": {"Articles": []}}
    assert api._session.headers["Authorization"] == "Bearer mytoken"


@patch("promki.kaufland.api.requests.Session.get")
def test_kaufland_api_coupons_error(mock_get, tmp_path):
    f = tmp_path / "session.json"
    f.write_text(json.dumps({"cookies": [], "origins": []}))

    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 401
    mock_resp.raise_for_status.side_effect = requests.HTTPError("401")
    mock_get.return_value = mock_resp

    api = KauflandApi(f)
    with pytest.raises(requests.HTTPError):
        api.coupons()


@patch("promki.kaufland.api.requests.Session.post")
def test_kaufland_api_activate_coupon(mock_post, tmp_path):
    f = tmp_path / "session.json"
    f.write_text(json.dumps({"cookies": [], "origins": []}))

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_post.return_value = mock_resp

    api = KauflandApi(f)
    assert api.activate_coupon("000001234") is True
    assert mock_post.call_args.kwargs["data"]["gcn"] == "000001234"
    assert mock_post.call_args.kwargs["data"]["status"] == "activate"
