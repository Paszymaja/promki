from unittest.mock import MagicMock, patch

import pytest

from lidl_recipe.gemini import suggest_recipes


@patch("lidl_recipe.gemini.requests.post")
def test_suggest_recipes_builds_prompt(mock_post):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Recipe output"}]}}]
    }
    mock_post.return_value = mock_resp

    items = [
        {"title": "Ser Gouda", "description": "2.99 zł"},
        {"title": "Mleko", "description": ""},
    ]
    result = suggest_recipes(items, "fake-key")

    assert result == "Recipe output"
    prompt = mock_post.call_args.kwargs["json"]["contents"][0]["parts"][0]["text"]
    assert "Ser Gouda (2.99 zł)" in prompt
    assert "Mleko" in prompt
    assert "Polish" in prompt or "polsku" in prompt.lower() or "Polish" in prompt


@patch("lidl_recipe.gemini.requests.post")
def test_suggest_recipes_api_error_exits(mock_post):
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    mock_post.return_value = mock_resp

    with pytest.raises(SystemExit):
        suggest_recipes([{"title": "Ser", "description": ""}], "fake-key")


@patch("lidl_recipe.gemini.requests.post")
def test_suggest_recipes_unexpected_response_exits(mock_post):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"unexpected": "structure"}
    mock_post.return_value = mock_resp

    with pytest.raises(SystemExit):
        suggest_recipes([{"title": "Ser", "description": ""}], "fake-key")
