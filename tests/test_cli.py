from unittest.mock import MagicMock, patch

import pytest
import requests

from lidl_recipe.cli import _refresh_token, main
from lidl_recipe.config import Config


def _make_coupons():
    return [
        {
            "id": "1",
            "title": "Ser Gouda",
            "isActivated": True,
            "discount": {"title": "2.99 zł", "description": ""},
            "validity": {"end": "2026-03-17T23:59:59+01:00"},
        },
        {
            "id": "2",
            "title": "Mleko UHT",
            "isActivated": True,
            "discount": {"title": "1.49 zł", "description": ""},
            "validity": {},
        },
    ]


@patch("lidl_recipe.cli.fetch_and_activate_coupons")
@patch("lidl_recipe.cli.LidlApi")
@patch("lidl_recipe.cli.Config.from_env")
def test_main_displays_items_with_dates(mock_from_env, mock_api_cls, mock_fetch, capsys, monkeypatch):
    mock_from_env.return_value = Config(access_token="fake-token")
    monkeypatch.setattr("sys.argv", ["lidl-recipe"])
    mock_fetch.return_value = _make_coupons()

    main()

    output = capsys.readouterr().out
    assert "Ser Gouda" in output
    assert "(do 17.03)" in output
    assert "Mleko UHT" in output
    lines = output.split("\n")
    mleko_line = [l for l in lines if "Mleko UHT" in l][0]
    assert "(do" not in mleko_line


@patch("lidl_recipe.cli.fetch_and_activate_coupons")
@patch("lidl_recipe.cli.LidlApi")
@patch("lidl_recipe.cli.Config.from_env")
def test_main_no_token_exits(mock_from_env, mock_api_cls, mock_fetch, monkeypatch):
    mock_from_env.return_value = Config(access_token="")
    monkeypatch.setattr("sys.argv", ["lidl-recipe"])

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    mock_fetch.assert_not_called()


@patch("lidl_recipe.cli.normalize_coupons")
@patch("lidl_recipe.cli.LidlApi")
@patch("lidl_recipe.cli.Config.from_env")
def test_main_debug_mode(mock_from_env, mock_api_cls, mock_normalize, capsys, monkeypatch):
    mock_from_env.return_value = Config(access_token="fake-token")
    monkeypatch.setattr("sys.argv", ["lidl-recipe", "--debug"])
    mock_api_cls.return_value.coupons.return_value = [{"id": "1", "title": "Test"}]
    mock_normalize.return_value = [{"id": "1", "title": "Test"}]

    main()

    output = capsys.readouterr().out
    assert '"title": "Test"' in output


@patch("lidl_recipe.login.capture_token")
def test_refresh_token_silent_success(mock_capture):
    mock_capture.return_value = "new-token"
    config = MagicMock(spec=Config)

    assert _refresh_token(config, allow_interactive=False) is True

    mock_capture.assert_called_once()
    assert mock_capture.call_args.kwargs["silent"] is True
    config.save_token.assert_called_once_with("new-token")
    config.reload.assert_called_once()


@patch("lidl_recipe.login.capture_token")
def test_refresh_token_silent_fails_no_interactive(mock_capture):
    mock_capture.return_value = None
    config = MagicMock(spec=Config)

    assert _refresh_token(config, allow_interactive=False) is False

    assert mock_capture.call_count == 1
    config.save_token.assert_not_called()


@patch("lidl_recipe.login.capture_token")
def test_refresh_token_falls_back_to_interactive(mock_capture):
    mock_capture.side_effect = [None, "interactive-token"]
    config = MagicMock(spec=Config)

    assert _refresh_token(config, allow_interactive=True) is True

    assert mock_capture.call_count == 2
    assert mock_capture.call_args_list[0].kwargs["silent"] is True
    assert mock_capture.call_args_list[1].kwargs["silent"] is False
    config.save_token.assert_called_once_with("interactive-token")


@patch("lidl_recipe.cli._refresh_token")
@patch("lidl_recipe.cli.fetch_and_activate_coupons")
@patch("lidl_recipe.cli.LidlApi")
@patch("lidl_recipe.cli.Config.from_env")
def test_main_retries_on_401(mock_from_env, mock_api_cls, mock_fetch, mock_refresh, monkeypatch):
    config = Config(access_token="stale-token")
    mock_from_env.return_value = config
    monkeypatch.setattr("sys.argv", ["lidl-recipe"])

    response = requests.Response()
    response.status_code = 401
    err = requests.HTTPError(response=response)
    mock_fetch.side_effect = [err, _make_coupons()]

    def refresh_side_effect(cfg, *, allow_interactive):
        cfg.access_token = "refreshed-token"
        return True

    mock_refresh.side_effect = refresh_side_effect

    main()

    assert mock_fetch.call_count == 2
    mock_refresh.assert_called_once()
    assert mock_refresh.call_args.kwargs["allow_interactive"] is False
    assert mock_api_cls.call_args_list[-1].args[0] == "refreshed-token"


@patch("lidl_recipe.cli._refresh_token")
@patch("lidl_recipe.cli.fetch_and_activate_coupons")
@patch("lidl_recipe.cli.LidlApi")
@patch("lidl_recipe.cli.Config.from_env")
def test_main_401_refresh_failure_exits(mock_from_env, mock_api_cls, mock_fetch, mock_refresh, monkeypatch):
    mock_from_env.return_value = Config(access_token="stale-token")
    monkeypatch.setattr("sys.argv", ["lidl-recipe"])

    response = requests.Response()
    response.status_code = 401
    mock_fetch.side_effect = requests.HTTPError(response=response)
    mock_refresh.return_value = False

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert "--login" in str(exc_info.value)


@patch("lidl_recipe.cli._refresh_token")
@patch("lidl_recipe.cli.fetch_and_activate_coupons")
@patch("lidl_recipe.cli.LidlApi")
@patch("lidl_recipe.cli.Config.from_env")
def test_main_non_401_error_propagates(mock_from_env, mock_api_cls, mock_fetch, mock_refresh, monkeypatch):
    mock_from_env.return_value = Config(access_token="ok-token")
    monkeypatch.setattr("sys.argv", ["lidl-recipe"])

    response = requests.Response()
    response.status_code = 500
    mock_fetch.side_effect = requests.HTTPError(response=response)

    with pytest.raises(requests.HTTPError):
        main()

    mock_refresh.assert_not_called()


@patch("lidl_recipe.cli._refresh_token")
@patch("lidl_recipe.cli.fetch_and_activate_coupons")
@patch("lidl_recipe.cli.LidlApi")
@patch("lidl_recipe.cli.Config.from_env")
def test_main_no_token_attempts_silent_refresh_first(mock_from_env, mock_api_cls, mock_fetch, mock_refresh, monkeypatch):
    config = Config(access_token="")
    mock_from_env.return_value = config
    monkeypatch.setattr("sys.argv", ["lidl-recipe"])
    mock_refresh.return_value = False

    with pytest.raises(SystemExit):
        main()

    mock_refresh.assert_called_once()
    assert mock_refresh.call_args.kwargs["allow_interactive"] is False
    mock_fetch.assert_not_called()
