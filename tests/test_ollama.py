from unittest.mock import MagicMock, patch

import pytest

from promki.ollama import MODEL, suggest_recipes
from promki.recipes import RecipeError


@patch("promki.ollama.requests.post")
def test_suggest_recipes_builds_prompt(mock_post):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"response": "Recipe output"}
    mock_post.return_value = mock_resp

    items = [
        {"title": "Ser Gouda", "description": "2.99 zł"},
        {"title": "Mleko", "description": ""},
    ]
    result = suggest_recipes(items, "http://localhost:11434")

    assert result == "Recipe output"
    assert mock_post.call_args.args[0] == "http://localhost:11434/api/generate"
    body = mock_post.call_args.kwargs["json"]
    assert body["model"] == MODEL
    assert body["stream"] is False
    prompt = body["prompt"]
    assert "Ser Gouda (2.99 zł)" in prompt
    assert "Mleko" in prompt
    assert "Polish" in prompt or "polsku" in prompt.lower()


@patch("promki.ollama.requests.post")
def test_suggest_recipes_strips_trailing_slash_in_url(mock_post):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"response": "ok"}
    mock_post.return_value = mock_resp

    suggest_recipes([{"title": "Ser", "description": ""}], "http://localhost:11434/")

    assert mock_post.call_args.args[0] == "http://localhost:11434/api/generate"


@patch("promki.ollama.requests.post")
def test_suggest_recipes_api_error_exits(mock_post):
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    mock_post.return_value = mock_resp

    with pytest.raises(RecipeError):
        suggest_recipes([{"title": "Ser", "description": ""}], "http://localhost:11434")


@patch("promki.ollama.requests.post")
def test_suggest_recipes_unexpected_response_exits(mock_post):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"unexpected": "structure"}
    mock_post.return_value = mock_resp

    with pytest.raises(RecipeError):
        suggest_recipes([{"title": "Ser", "description": ""}], "http://localhost:11434")
