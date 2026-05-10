class RecipeError(Exception):
    """Raised when a recipe-suggestion backend fails."""


def build_prompt(items: list[dict]) -> str:
    item_list = "\n".join(
        f"- {item['title']}" + (f" ({item['description']})" if item["description"] else "")
        for item in items
    )
    return (
        "I have the following discounted items available at Lidl this week:\n\n"
        f"{item_list}\n\n"
        "Please suggest 3 creative and practical recipes I can make using "
        "some of these discounted items. Ignore items that are clearly not "
        "food ingredients (e.g. cleaning products, cosmetics, household items). "
        "For each recipe, list the ingredients (marking which ones are from "
        "the discount list) and brief cooking instructions. Answer in Polish."
    )
