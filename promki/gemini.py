import json

import requests

from .recipes import RecipeError, build_prompt


def _gemini_request(prompt: str, api_key: str) -> str:
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    resp = requests.post(
        url,
        params={"key": api_key},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=60,
    )
    if not resp.ok:
        raise RecipeError(f"Gemini API failed ({resp.status_code}): {resp.text[:200]}")

    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RecipeError("Unexpected Gemini response:\n" + json.dumps(data, indent=2)[:500])


def suggest_recipes(items: list[dict], api_key: str) -> str:
    return _gemini_request(build_prompt(items), api_key)
