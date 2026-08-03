import json

import requests

from .recipes import RecipeError, build_prompt

MODEL = "gemma4-fast"
# Local model load (cold start) + generation can take minutes; allow generous slack.
TIMEOUT_SECONDS = 300


def _ollama_request(prompt: str, url: str) -> str:
    resp = requests.post(
        f"{url.rstrip('/')}/api/generate",
        json={"model": MODEL, "prompt": prompt, "stream": False},
        timeout=TIMEOUT_SECONDS,
    )
    if not resp.ok:
        raise RecipeError(f"Ollama API failed ({resp.status_code}): {resp.text[:200]}")

    data = resp.json()
    try:
        return data["response"]
    except KeyError:
        raise RecipeError("Unexpected Ollama response:\n" + json.dumps(data, indent=2)[:500])


def suggest_recipes(items: list[dict], url: str) -> str:
    return _ollama_request(build_prompt(items), url)
