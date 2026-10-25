"""The three independent checkers."""

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def knowledge() -> dict:
    return json.loads((Path(__file__).with_name("knowledge.json")).read_text())
