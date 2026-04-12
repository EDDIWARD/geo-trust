from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "mock_data"
WEIGHTS_PATH = DATA_DIR / "analytics_weights.json"
CITY_PROFILES_PATH = DATA_DIR / "analytics_city_profiles.json"


@lru_cache(maxsize=1)
def load_analytics_weights() -> dict:
    with WEIGHTS_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_city_profiles() -> dict[str, dict[str, float]]:
    with CITY_PROFILES_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)
