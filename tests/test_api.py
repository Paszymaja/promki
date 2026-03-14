from unittest.mock import MagicMock, patch

import requests

from lidl_recipe.api import LidlApi


def test_headers():
    api = LidlApi("pl", "PL", "test-token-123")
    headers = api._headers()
    assert headers["Authorization"] == "Bearer test-token-123"
    assert headers["Accept-Language"] == "pl"
    assert headers["Country"] == "PL"
    assert headers["Accept"] == "application/json"


@patch("lidl_recipe.api.requests.get")
def test_coupons_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = [{"id": "1"}]
    mock_get.return_value = mock_resp

    api = LidlApi("pl", "PL", "token")
    result = api.coupons()

    assert result == [{"id": "1"}]
    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert "promotionsList" in args[0]
    assert kwargs["headers"]["Authorization"] == "Bearer token"


@patch("lidl_recipe.api.requests.get")
def test_coupons_error_raises(mock_get):
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized"
    mock_resp.raise_for_status.side_effect = requests.HTTPError("401")
    mock_get.return_value = mock_resp

    api = LidlApi("pl", "PL", "bad-token")
    try:
        api.coupons()
        assert False, "Should raise"
    except requests.HTTPError:
        pass


@patch("lidl_recipe.api.requests.post")
def test_activate_coupon_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_post.return_value = mock_resp

    api = LidlApi("pl", "PL", "token")
    api.activate_coupon("abc-123")

    args, kwargs = mock_post.call_args
    assert "abc-123" in args[0]
    assert "activation" in args[0]


@patch("lidl_recipe.api.requests.post")
def test_activate_coupon_error_raises(mock_post):
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 409
    mock_resp.text = "Conflict"
    mock_resp.raise_for_status.side_effect = requests.HTTPError("409")
    mock_post.return_value = mock_resp

    api = LidlApi("pl", "PL", "token")
    try:
        api.activate_coupon("abc-123")
        assert False, "Should raise"
    except requests.HTTPError:
        pass
