import sqlite3
from unittest.mock import MagicMock, patch

import pytest
import requests

from promki.cli import _refresh_token, main
from promki.config import Config


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


def _make_kaufland_coupons():
    return [
        {
            "id": "k1",
            "title": "Kaufland Ser",
            "isActivated": True,
            "discount": {"title": "3.99 zł", "description": ""},
            "validity": {"end": "2026-03-17T23:59:59+01:00"},
        },
    ]


@patch("promki.cli.load_access_token")
@patch("promki.cli.save_snapshot")
@patch("promki.cli.fetch_and_activate_coupons")
@patch("promki.cli.LidlApi")
@patch("promki.cli.Config")
def test_main_displays_items_with_dates(mock_config, mock_api_cls, mock_fetch, mock_save, mock_load, capsys, monkeypatch, tmp_path):
    mock_config.return_value = Config(project_root=tmp_path)
    mock_load.return_value = "fake-token"
    monkeypatch.setattr("sys.argv", ["promki"])
    mock_fetch.return_value = _make_coupons()

    main()

    output = capsys.readouterr().out
    assert "Ser Gouda" in output
    assert "(do 17.03)" in output
    assert "Mleko UHT" in output
    lines = output.split("\n")
    mleko_line = [l for l in lines if "Mleko UHT" in l][0]
    assert "(do" not in mleko_line


@patch("promki.cli._refresh_kaufland_session")
@patch("promki.cli._refresh_token")
@patch("promki.cli.load_access_token")
@patch("promki.cli.fetch_and_activate_coupons")
@patch("promki.cli.LidlApi")
@patch("promki.cli.Config")
def test_main_no_token_exits(mock_config, mock_api_cls, mock_fetch, mock_load, mock_refresh, mock_kaufland_refresh, monkeypatch, tmp_path):
    mock_config.return_value = Config(project_root=tmp_path)
    mock_load.return_value = None
    mock_refresh.return_value = None
    mock_kaufland_refresh.return_value = False
    monkeypatch.setattr("sys.argv", ["promki"])

    main()

    mock_refresh.assert_called_once()
    assert mock_refresh.call_args.kwargs["allow_interactive"] is False
    mock_fetch.assert_not_called()


@patch("promki.cli.normalize_coupons")
@patch("promki.cli.load_access_token")
@patch("promki.cli.LidlApi")
@patch("promki.cli.Config")
def test_main_debug_mode(mock_config, mock_api_cls, mock_load, mock_normalize, capsys, monkeypatch, tmp_path):
    mock_config.return_value = Config(project_root=tmp_path)
    mock_load.return_value = "fake-token"
    monkeypatch.setattr("sys.argv", ["promki", "--debug"])
    mock_api_cls.return_value.coupons.return_value = [{"id": "1", "title": "Test"}]
    mock_normalize.return_value = [{"id": "1", "title": "Test"}]

    main()

    output = capsys.readouterr().out
    assert '"title": "Test"' in output


@patch("promki.cli.capture_token")
def test_refresh_token_silent_success(mock_capture):
    mock_capture.return_value = "new-token"
    config = MagicMock(spec=Config)

    assert _refresh_token(config, allow_interactive=False) == "new-token"

    mock_capture.assert_called_once()
    assert mock_capture.call_args.kwargs["silent"] is True


@patch("promki.cli.capture_token")
def test_refresh_token_silent_fails_no_interactive(mock_capture):
    mock_capture.return_value = None
    config = MagicMock(spec=Config)

    assert _refresh_token(config, allow_interactive=False) is None

    assert mock_capture.call_count == 1


@patch("promki.cli.capture_token")
def test_refresh_token_falls_back_to_interactive(mock_capture):
    mock_capture.side_effect = [None, "interactive-token"]
    config = MagicMock(spec=Config)

    assert _refresh_token(config, allow_interactive=True) == "interactive-token"

    assert mock_capture.call_count == 2
    assert mock_capture.call_args_list[0].kwargs["silent"] is True
    assert mock_capture.call_args_list[1].kwargs["silent"] is False


@patch("promki.cli.save_snapshot")
@patch("promki.cli._refresh_token")
@patch("promki.cli.load_access_token")
@patch("promki.cli.fetch_and_activate_coupons")
@patch("promki.cli.LidlApi")
@patch("promki.cli.Config")
def test_main_retries_on_401(mock_config, mock_api_cls, mock_fetch, mock_load, mock_refresh, mock_save, monkeypatch, tmp_path):
    mock_config.return_value = Config(project_root=tmp_path)
    mock_load.return_value = "stale-token"
    monkeypatch.setattr("sys.argv", ["promki"])

    response = requests.Response()
    response.status_code = 401
    err = requests.HTTPError(response=response)
    mock_fetch.side_effect = [err, _make_coupons()]
    mock_refresh.return_value = "refreshed-token"

    main()

    assert mock_fetch.call_count == 2
    mock_refresh.assert_called_once()
    assert mock_refresh.call_args.kwargs["allow_interactive"] is False
    assert mock_api_cls.call_args_list[-1].args[0] == "refreshed-token"


@patch("promki.cli._refresh_token")
@patch("promki.cli.load_access_token")
@patch("promki.cli.fetch_and_activate_coupons")
@patch("promki.cli.LidlApi")
@patch("promki.cli.Config")
def test_main_401_refresh_failure_exits(mock_config, mock_api_cls, mock_fetch, mock_load, mock_refresh, monkeypatch, tmp_path):
    mock_config.return_value = Config(project_root=tmp_path)
    mock_load.return_value = "stale-token"
    monkeypatch.setattr("sys.argv", ["promki"])

    response = requests.Response()
    response.status_code = 401
    mock_fetch.side_effect = requests.HTTPError(response=response)
    mock_refresh.return_value = None

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert "--login" in str(exc_info.value)


@patch("promki.cli._refresh_token")
@patch("promki.cli.load_access_token")
@patch("promki.cli.fetch_and_activate_coupons")
@patch("promki.cli.LidlApi")
@patch("promki.cli.Config")
def test_main_non_401_error_propagates(mock_config, mock_api_cls, mock_fetch, mock_load, mock_refresh, monkeypatch, tmp_path):
    mock_config.return_value = Config(project_root=tmp_path)
    mock_load.return_value = "ok-token"
    monkeypatch.setattr("sys.argv", ["promki"])

    response = requests.Response()
    response.status_code = 500
    mock_fetch.side_effect = requests.HTTPError(response=response)

    with pytest.raises(requests.HTTPError):
        main()

    mock_refresh.assert_not_called()


@patch("promki.cli._refresh_kaufland_session")
@patch("promki.cli._refresh_token")
@patch("promki.cli.load_access_token")
@patch("promki.cli.fetch_and_activate_coupons")
@patch("promki.cli.LidlApi")
@patch("promki.cli.Config")
def test_main_no_token_attempts_silent_refresh_first(mock_config, mock_api_cls, mock_fetch, mock_load, mock_refresh, mock_kaufland_refresh, monkeypatch, tmp_path):
    mock_config.return_value = Config(project_root=tmp_path)
    mock_load.return_value = None
    monkeypatch.setattr("sys.argv", ["promki"])
    mock_refresh.return_value = None
    mock_kaufland_refresh.return_value = False

    main()

    mock_refresh.assert_called_once()
    assert mock_refresh.call_args.kwargs["allow_interactive"] is False
    mock_fetch.assert_not_called()


@patch("promki.cli.diff_latest")
@patch("promki.cli.save_snapshot")
@patch("promki.cli.load_access_token")
@patch("promki.cli.fetch_and_activate_coupons")
@patch("promki.cli.LidlApi")
@patch("promki.cli.Config")
def test_main_diff_flag_invokes_diff(mock_config, mock_api_cls, mock_fetch, mock_load, mock_save, mock_diff, capsys, monkeypatch, tmp_path):
    mock_config.return_value = Config(project_root=tmp_path)
    mock_load.return_value = "fake-token"
    monkeypatch.setattr("sys.argv", ["promki", "--diff"])
    mock_fetch.return_value = _make_coupons()
    mock_diff.return_value = {
        "latest": "t2",
        "previous": "t1",
        "added": [{"title": "Brand New Coupon"}],
        "removed": [],
        "changed": [],
    }

    main()

    mock_save.assert_called_once()
    assert mock_diff.call_count == 2  # called once per source
    mock_diff.assert_any_call(tmp_path / "coupons.db", source="lidl")
    mock_diff.assert_any_call(tmp_path / "coupons.db", source="kaufland")
    assert "Brand New Coupon" in capsys.readouterr().out


@patch("promki.cli.diff_latest")
@patch("promki.cli.save_snapshot")
@patch("promki.cli.load_access_token")
@patch("promki.cli.fetch_and_activate_coupons")
@patch("promki.cli.LidlApi")
@patch("promki.cli.Config")
def test_main_continues_when_save_snapshot_fails(mock_config, mock_api_cls, mock_fetch, mock_load, mock_save, mock_diff, capsys, monkeypatch, tmp_path):
    mock_config.return_value = Config(project_root=tmp_path)
    mock_load.return_value = "fake-token"
    monkeypatch.setattr("sys.argv", ["promki"])
    mock_fetch.return_value = _make_coupons()
    mock_save.side_effect = sqlite3.OperationalError("disk full")

    main()  # must not raise

    output = capsys.readouterr().out
    assert "Warning" in output and "disk full" in output
    assert "Ser Gouda" in output  # downstream display still happens
    mock_diff.assert_not_called()


@patch("promki.cli.diff_latest")
@patch("promki.cli.save_snapshot")
@patch("promki.cli.load_access_token")
@patch("promki.cli.fetch_and_activate_coupons")
@patch("promki.cli.LidlApi")
@patch("promki.cli.Config")
def test_main_continues_when_diff_fails(mock_config, mock_api_cls, mock_fetch, mock_load, mock_save, mock_diff, capsys, monkeypatch, tmp_path):
    mock_config.return_value = Config(project_root=tmp_path)
    mock_load.return_value = "fake-token"
    monkeypatch.setattr("sys.argv", ["promki", "--diff"])
    mock_fetch.return_value = _make_coupons()
    mock_diff.side_effect = sqlite3.DatabaseError("corrupt")

    main()

    output = capsys.readouterr().out
    assert "Warning" in output and "corrupt" in output


@patch("promki.cli.diff_latest")
@patch("promki.cli.save_snapshot")
@patch("promki.cli.load_access_token")
@patch("promki.cli.fetch_and_activate_coupons")
@patch("promki.cli.LidlApi")
@patch("promki.cli.Config")
def test_main_continues_when_save_raises_schema_version_error(mock_config, mock_api_cls, mock_fetch, mock_load, mock_save, mock_diff, capsys, monkeypatch, tmp_path):
    from promki.db import SchemaVersionError

    mock_config.return_value = Config(project_root=tmp_path)
    mock_load.return_value = "fake-token"
    monkeypatch.setattr("sys.argv", ["promki"])
    mock_fetch.return_value = _make_coupons()
    mock_save.side_effect = SchemaVersionError("schema mismatch — delete coupons.db")

    main()  # must not raise

    output = capsys.readouterr().out
    assert "Warning" in output and "schema mismatch" in output
    assert "Ser Gouda" in output


@patch("promki.cli._refresh_kaufland_session")
@patch("promki.cli.diff_latest")
@patch("promki.cli.save_snapshot")
@patch("promki.cli.fetch_and_activate_coupons")
@patch("promki.cli.LidlApi")
@patch("promki.cli._refresh_token")
@patch("promki.cli.load_access_token")
@patch("promki.cli.Config")
def test_login_with_diff_falls_through_to_fetch(mock_config, mock_load, mock_refresh, mock_api_cls, mock_fetch, mock_save, mock_diff, mock_kaufland_refresh, monkeypatch, tmp_path):
    mock_config.return_value = Config(project_root=tmp_path)
    mock_load.return_value = "fake-token"
    mock_refresh.return_value = "fake-token"
    mock_kaufland_refresh.return_value = True
    monkeypatch.setattr("sys.argv", ["promki", "--login", "--diff"])
    mock_fetch.return_value = _make_coupons()
    mock_diff.return_value = None

    with patch("promki.kaufland.fetch_and_activate_kaufland_coupons") as mock_kfetch, \
         patch("promki.kaufland.KauflandApi"):
        mock_kfetch.return_value = _make_kaufland_coupons()
        main()

    mock_fetch.assert_called_once()
    mock_save.assert_called()
    assert mock_diff.call_count == 2  # called once per source


@patch("promki.cli.save_snapshot")
@patch("promki.cli._refresh_token")
@patch("promki.cli.load_access_token")
@patch("promki.cli.fetch_and_activate_coupons")
@patch("promki.cli.LidlApi")
@patch("promki.cli.Config")
def test_main_saves_kaufland_snapshot_with_source(mock_config, mock_api_cls, mock_fetch, mock_load, mock_refresh, mock_save, capsys, monkeypatch, tmp_path):
    mock_config.return_value = Config(project_root=tmp_path)
    mock_load.return_value = "fake-token"
    mock_fetch.return_value = _make_coupons()
    monkeypatch.setattr("sys.argv", ["promki"])
    (tmp_path / "kaufland_session.json").write_text("{}")

    with patch("promki.kaufland.fetch_and_activate_kaufland_coupons") as mock_kfetch, \
         patch("promki.kaufland.KauflandApi"):
        mock_kfetch.return_value = _make_kaufland_coupons()
        main()

    mock_save.assert_any_call(tmp_path / "coupons.db", mock_kfetch.return_value, source="kaufland")
    assert "Kaufland Ser" in capsys.readouterr().out  # normalized title in display
