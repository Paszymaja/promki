import json
import sys

import requests


def _gemini_request(prompt: str, api_key: str) -> str:
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    resp = requests.post(
        url,
        params={"key": api_key},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=60,
    )
    if not resp.ok:
        print(f"Gemini API failed ({resp.status_code}): {resp.text[:200]}")
        sys.exit(1)

    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        print("Unexpected Gemini response:")
        print(json.dumps(data, indent=2)[:500])
        sys.exit(1)


def suggest_recipes(items: list[dict], api_key: str) -> str:
    item_list = "\n".join(
        f"- {item['title']}" + (f" ({item['description']})" if item["description"] else "")
        for item in items
    )
    prompt = (
        "I have the following discounted items available at Lidl this week:\n\n"
        f"{item_list}\n\n"
        "Please suggest 3 creative and practical recipes I can make using "
        "some of these discounted items. Ignore items that are clearly not "
        "food ingredients (e.g. cleaning products, cosmetics, household items). "
        "For each recipe, list the ingredients (marking which ones are from "
        "the discount list) and brief cooking instructions. Answer in Polish."
    )
    return _gemini_request(prompt, api_key)
