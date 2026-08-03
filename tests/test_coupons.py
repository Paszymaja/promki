from datetime import date

import pytest

from promki.coupons import (
    extract_discount_items,
    filter_consumables,
    normalize_coupons,
)


# --- normalize_coupons ---


def test_normalize_coupons_list():
    raw = [{"id": "1"}, {"id": "2"}]
    assert normalize_coupons(raw) == raw


def test_normalize_coupons_dict_with_sections():
    raw = {
        "sections": [
            {"coupons": [{"id": "1"}]},
            {"coupons": [{"id": "2"}]},
        ]
    }
    assert normalize_coupons(raw) == [{"id": "1"}, {"id": "2"}]


def test_normalize_coupons_dict_with_promotions_in_sections():
    raw = {
        "sections": [
            {"promotions": [{"id": "1"}]},
        ]
    }
    assert normalize_coupons(raw) == [{"id": "1"}]


def test_normalize_coupons_dict_flat_coupons():
    raw = {"coupons": [{"id": "1"}]}
    assert normalize_coupons(raw) == [{"id": "1"}]


def test_normalize_coupons_dict_flat_promotions():
    raw = {"promotions": [{"id": "1"}]}
    assert normalize_coupons(raw) == [{"id": "1"}]


def test_normalize_coupons_empty_dict():
    assert normalize_coupons({}) == []


def test_normalize_coupons_non_list_non_dict():
    assert normalize_coupons("unexpected") == []
    assert normalize_coupons(None) == []


# --- extract_discount_items ---


def test_extract_discount_items_basic():
    coupons = [
        {
            "title": "Ser Gouda",
            "discount": {"title": "2.99 zł", "description": ""},
            "validity": {"end": "2026-03-17T23:59:59+01:00"},
        }
    ]
    items = extract_discount_items(coupons)
    assert len(items) == 1
    assert items[0]["title"] == "Ser Gouda"
    assert items[0]["description"] == "2.99 zł"
    assert items[0]["valid_until"] == date(2026, 3, 17)


def test_extract_discount_items_utc_z_date():
    coupons = [
        {
            "title": "Masło",
            "validity": {"end": "2026-03-21T22:59:59Z"},
        }
    ]
    items = extract_discount_items(coupons)
    assert items[0]["valid_until"] == date(2026, 3, 21)


def test_extract_discount_items_no_validity():
    coupons = [{"title": "Mleko", "discount": {}, "validity": {}}]
    items = extract_discount_items(coupons)
    assert items[0]["valid_until"] is None


def test_extract_discount_items_missing_validity_key():
    coupons = [{"title": "Mleko"}]
    items = extract_discount_items(coupons)
    assert items[0]["valid_until"] is None


def test_extract_discount_items_invalid_date():
    coupons = [{"title": "Masło", "validity": {"end": "not-a-date"}}]
    items = extract_discount_items(coupons)
    assert items[0]["valid_until"] is None


def test_extract_discount_items_deduplicates():
    coupons = [
        {"title": "Ser Gouda"},
        {"title": "Ser Gouda"},
    ]
    items = extract_discount_items(coupons)
    assert len(items) == 1


def test_extract_discount_items_skips_empty_title():
    coupons = [{"title": ""}, {"title": "  "}]
    assert extract_discount_items(coupons) == []


def test_extract_discount_items_skips_percentage_titles():
    coupons = [
        {"title": "-20% na wszystko"},
        {"title": "50% taniej"},
    ]
    assert extract_discount_items(coupons) == []


def test_extract_discount_items_keeps_percentage_in_middle():
    coupons = [{"title": "Ser 20% mniej tłuszczu"}]
    items = extract_discount_items(coupons)
    assert len(items) == 1
    assert items[0]["title"] == "Ser 20% mniej tłuszczu"


def test_extract_discount_items_skips_star_titles():
    coupons = [{"title": "*Regulamin w sklepie"}]
    assert extract_discount_items(coupons) == []


def test_extract_discount_items_discount_fields():
    coupons = [
        {
            "title": "Jogurt",
            "discount": {
                "title": "1.99 zł",
                "description": "Cena regularna 3.49 zł",
            },
        }
    ]
    items = extract_discount_items(coupons)
    assert items[0]["description"] == "1.99 zł\nCena regularna 3.49 zł"


def test_extract_discount_items_real_api_shape():
    """Test with a coupon shaped exactly like the real Lidl API response."""
    coupons = [
        {
            "id": "019cd174-a9f0-7794-b8c6-5cb22190f7b2",
            "promotionId": "b458afe0-7722-4ab6-9376-cc8801939907",
            "type": "Standard",
            "discount": {
                "title": "900 zł taniej",
                "description": "Rabat na maks. 10 szt.",
                "hasAsterisk": False,
                "scope": "OnlyDiscount",
            },
            "title": "Termorobot MC Smart z Wi-Fi",
            "validity": {
                "start": "2026-03-08T23:00:01Z",
                "end": "2026-03-21T22:59:59Z",
            },
            "isActivated": True,
            "isHappyHour": False,
            "isSpecial": False,
            "channel": "Store",
        }
    ]
    items = extract_discount_items(coupons)
    assert len(items) == 1
    assert items[0]["title"] == "Termorobot MC Smart z Wi-Fi"
    assert items[0]["description"] == "900 zł taniej\nRabat na maks. 10 szt."
    assert items[0]["valid_until"] == date(2026, 3, 21)


def test_extract_discount_items_discount_same_as_title_excluded():
    coupons = [
        {
            "title": "Jogurt",
            "discount": {"title": "Jogurt", "description": "Jogurt"},
        }
    ]
    items = extract_discount_items(coupons)
    assert items[0]["description"] == ""


# --- filter_consumables ---


def test_filter_consumables_keeps_food():
    items = [
        {"title": "Ser Gouda"},
        {"title": "Mleko UHT"},
        {"title": "Masło Extra"},
    ]
    assert filter_consumables(items) == items


def test_filter_consumables_removes_non_consumables():
    items = [
        {"title": "Robot kuchenny"},
        {"title": "Spodnie męskie"},
        {"title": "Telewizor 55 cali"},
        {"title": "Laptop Lenovo"},
        {"title": "Kettlebell 12kg"},
    ]
    assert filter_consumables(items) == []


def test_filter_consumables_mixed():
    items = [
        {"title": "Ser Gouda"},
        {"title": "Robot kuchenny"},
        {"title": "Mleko UHT"},
    ]
    result = filter_consumables(items)
    assert len(result) == 2
    assert result[0]["title"] == "Ser Gouda"
    assert result[1]["title"] == "Mleko UHT"


def test_filter_consumables_case_insensitive():
    items = [{"title": "ROBOT KUCHENNY"}]
    assert filter_consumables(items) == []


@pytest.mark.parametrize("title", [
    "Robot kuchenny",                                # electronics
    "Spodnie męskie",                                # clothing
    "Kettlebell 12kg",                               # fitness
    "Plecak turystyczny",                            # bags
    "Szklanki komplet",                              # kitchenware
    "Zabawki dla dzieci",                            # toys
    "Telewizor 55 cali",                             # electronics
    "Meble ogrodowe",                                # furniture
    "Narzędzia warsztatowe",                         # tools
    "Akcesoria łazienkowe",                          # accessories
    "Saturator Sodastream Gaia",                     # appliance
    "Saturator do wody gazowanej Gaia",              # appliance
    "Gąbki Scrub Daddy lub Mommy",                   # cleaning
    "Regał łazienkowy z bambusa",                    # furniture
    "Frytkownica beztłuszczowa Air Fryer 3,6 L",     # appliance
    "Kuchnia drewniana dla dzieci",                  # toy
    "Dmuchany zamek z koszem do koszykówki",         # toy
    "Huśtawka prostokątna XL",                       # toy
    "Legowisko dla psa, grzejące i chłodzące",       # pet
    "Wyrzutnia piłek tenisowych lub piłki tenisowe", # sports
    "Basen dla psa",                                 # pet
    "Legowisko lub składany leżak dla psa",          # pet
    "Ekspres kolbowy, 1100 W",                       # appliance
    "Blender ręczny",                                # appliance
    "Krajalnica elektryczna",                        # appliance
    "Deska SUP jednokomorowa Aquaview",              # sports
    "Deska SUP dwukomorowa",                         # sports
    "Wybrana pościel muślinowa",                     # bedding
])
def test_filter_consumables_keyword_categories(title):
    assert filter_consumables([{"title": title}]) == []


@pytest.mark.parametrize("title", [
    "Frytki belgijskie",      # frytka != frytkownica
    "Kawa ekspresowa Jacobs", # ekspresowa != ekspres kolb
    "Deska serów francuskich",# deska != deska sup
    "Wino leżakowane",        # leżakowane != leżak (substring guard)
])
def test_filter_consumables_does_not_overmatch_food(title):
    """Sanity check: substrings of food words must not trigger non-consumable filter."""
    assert filter_consumables([{"title": title}]) == [{"title": title}]
