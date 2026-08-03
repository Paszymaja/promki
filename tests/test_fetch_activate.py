from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

import requests

from promki.coupons import fetch_and_activate_coupons


def _make_api(coupons):
    api = MagicMock()
    api.coupons.return_value = coupons
    return api


def _coupon(id="1", title="Ser Gouda", activated=True, end="2026-12-31T22:59:59Z"):
    return {
        "id": id,
        "title": title,
        "isActivated": activated,
        "validity": {"end": end},
    }


@patch("promki.coupons.time.sleep")
def test_activates_inactive_coupon(mock_sleep):
    api = _make_api([_coupon(activated=False)])
    result = fetch_and_activate_coupons(api)

    api.activate_coupon.assert_called_once_with("1")
    mock_sleep.assert_called_once_with(0.5)
    assert len(result) == 1


@patch("promki.coupons.time.sleep")
def test_skips_already_activated(mock_sleep):
    api = _make_api([_coupon(activated=True)])
    fetch_and_activate_coupons(api)

    api.activate_coupon.assert_not_called()
    mock_sleep.assert_not_called()


@patch("promki.coupons.time.sleep")
def test_skips_expired_coupon(mock_sleep):
    api = _make_api([_coupon(activated=False, end="2020-01-01T00:00:00+00:00")])
    fetch_and_activate_coupons(api)

    api.activate_coupon.assert_not_called()


@patch("promki.coupons.time.sleep")
def test_skips_invalid_date(mock_sleep):
    api = _make_api([_coupon(activated=False, end="bad-date")])
    fetch_and_activate_coupons(api)

    api.activate_coupon.assert_not_called()


@patch("promki.coupons.time.sleep")
def test_skips_no_end_date(mock_sleep):
    coupon = {"id": "1", "title": "Test", "isActivated": False, "validity": {"end": ""}}
    api = _make_api([coupon])
    fetch_and_activate_coupons(api)

    api.activate_coupon.assert_not_called()


@patch("promki.coupons.time.sleep")
def test_skips_coupon_without_id(mock_sleep):
    coupon = {"title": "Test", "isActivated": False, "validity": {"end": "2026-12-31T23:59:59+00:00"}}
    api = _make_api([coupon])
    fetch_and_activate_coupons(api)

    api.activate_coupon.assert_not_called()


@patch("promki.coupons.time.sleep")
def test_handles_409_conflict(mock_sleep):
    api = _make_api([_coupon(activated=False)])
    resp = MagicMock()
    resp.status_code = 409
    api.activate_coupon.side_effect = requests.HTTPError(response=resp)

    result = fetch_and_activate_coupons(api)
    assert len(result) == 1


@patch("promki.coupons.time.sleep")
def test_handles_412_precondition_failed(mock_sleep):
    api = _make_api([_coupon(activated=False)])
    resp = MagicMock()
    resp.status_code = 412
    api.activate_coupon.side_effect = requests.HTTPError(response=resp)

    result = fetch_and_activate_coupons(api)
    assert len(result) == 1


@patch("promki.coupons.time.sleep")
def test_handles_other_http_error(mock_sleep, capsys):
    api = _make_api([_coupon(activated=False)])
    resp = MagicMock()
    resp.status_code = 500
    api.activate_coupon.side_effect = requests.HTTPError(response=resp)

    fetch_and_activate_coupons(api)
    output = capsys.readouterr().out
    assert "Failed to activate" in output


@patch("promki.coupons.time.sleep")
def test_activates_multiple_coupons(mock_sleep):
    api = _make_api([
        _coupon(id="1", title="A", activated=False),
        _coupon(id="2", title="B", activated=True),
        _coupon(id="3", title="C", activated=False),
    ])
    fetch_and_activate_coupons(api)

    assert api.activate_coupon.call_count == 2
    api.activate_coupon.assert_any_call("1")
    api.activate_coupon.assert_any_call("3")
