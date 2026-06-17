from __future__ import annotations

import re

# Taipei Metro line codes that appear as a suffix on station rows in the
# entries/exits dataset (e.g. 中山R, 中山G, 台北車站BL).
_LINE_SUFFIX_RE = re.compile(r"(BL|BR|[RGOY])$")


def normalize_taipei_name(value: str) -> str:
    return value.replace("台", "臺")


def normalize_station_name(raw: str) -> str:
    name = raw.strip()
    stripped = _LINE_SUFFIX_RE.sub("", name)
    return stripped if stripped else name
