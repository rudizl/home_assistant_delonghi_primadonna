"""Beverages the ECAM protocol knows (EcamBeverageId in the app).

Pure data, no Home Assistant imports. The keys are used for entity
unique ids, translation keys and the make_beverage service, so the
eight keys that existed before 2026.11.5 keep their old spelling.
"""
from __future__ import annotations

# Beverage id -> key
BEVERAGES: dict[int, str] = {
    1: 'espresso',
    2: 'coffee',
    3: 'long',
    4: 'espresso2',
    5: 'dopio',
    6: 'americano',
    7: 'cappuccino',
    8: 'latte_macchiato',
    9: 'caffe_latte',
    10: 'flat_white',
    11: 'espresso_macchiato',
    12: 'hot_milk',
    13: 'cappuccino_doppio',
    14: 'cold_milk',
    15: 'cappuccino_reverse',
    16: 'hot_water',
    17: 'steam',
    18: 'ciocco',
    19: 'ristretto',
    20: 'long_espresso',
    21: 'coffee_cream',
    22: 'tea',
    23: 'coffee_pot',
    24: 'cortado',
    25: 'long_black',
    26: 'travel_mug',
    27: 'brew_over_ice',
}

BEVERAGE_IDS: dict[str, int] = {key: bid for bid, key in BEVERAGES.items()}

# Offered when the machine model is unknown (the set before 2026.11.5)
DEFAULT_BEVERAGES: tuple[str, ...] = (
    'espresso', 'coffee', 'long', 'espresso2', 'dopio', 'americano',
    'hot_water', 'steam',
)


def beverages_for_recipe_ids(recipe_ids) -> list[str]:
    """Return the beverage keys for a model's recipe ids, in id order.

    Ids that are not standard beverages (custom recipes 230+) and
    unparsable ids are skipped.
    """
    keys = []
    for raw in recipe_ids:
        try:
            bid = int(raw)
        except (TypeError, ValueError):
            continue
        if bid in BEVERAGES and BEVERAGES[bid] not in keys:
            keys.append(BEVERAGES[bid])
    return sorted(keys, key=BEVERAGE_IDS.__getitem__)
