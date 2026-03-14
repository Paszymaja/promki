from unittest.mock import patch

import pytest

from lidl_recipe.cli import main


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
@patch("lidl_recipe.cli.load_dotenv")
def test_main_displays_items_with_dates(mock_dotenv, mock_api_cls, mock_fetch, capsys, monkeypatch):
    monkeypatch.setenv("LIDL_ACCESS_TOKEN", "fake-token")
    monkeypatch.setattr("sys.argv", ["lidl-recipe"])
    mock_fetch.return_value = _make_coupons()

    main()

    output = capsys.readouterr().out
    assert "Ser Gouda" in output
    assert "(do 17.03)" in output
    assert "Mleko UHT" in output
    # Mleko has no validity end, so no date
    lines = output.split("\n")
    mleko_line = [l for l in lines if "Mleko UHT" in l][0]
    assert "(do" not in mleko_line


@patch("lidl_recipe.cli.fetch_and_activate_coupons")
@patch("lidl_recipe.cli.LidlApi")
@patch("lidl_recipe.cli.load_dotenv")
def test_main_no_token_exits(mock_dotenv, mock_api_cls, mock_fetch, monkeypatch):
    monkeypatch.delenv("LIDL_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr("sys.argv", ["lidl-recipe"])

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    mock_fetch.assert_not_called()


@patch("lidl_recipe.cli.normalize_coupons")
@patch("lidl_recipe.cli.LidlApi")
@patch("lidl_recipe.cli.load_dotenv")
def test_main_debug_mode(mock_dotenv, mock_api_cls, mock_normalize, capsys, monkeypatch):
    monkeypatch.setenv("LIDL_ACCESS_TOKEN", "fake-token")
    monkeypatch.setattr("sys.argv", ["lidl-recipe", "--debug"])
    mock_api_cls.return_value.coupons.return_value = [{"id": "1", "title": "Test"}]
    mock_normalize.return_value = [{"id": "1", "title": "Test"}]

    main()

    output = capsys.readouterr().out
    assert '"title": "Test"' in output
