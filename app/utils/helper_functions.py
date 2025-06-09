from datetime import datetime
from typing import Any
import json



def remove_null_values(d: dict) -> dict:
    return {key: value for key, value in d.items() if value is not None}


def parse_datetime(dt_str: Any) -> datetime | Any:
    """Parse a datetime string, handling timezone information.

    Args:
        dt_str: Datetime string to parse

    Returns:
        Parsed datetime object
    """
    if not dt_str:
        return datetime.now()

    if "Z" in dt_str:
        dt_str = dt_str.replace("Z", "+00:00")

    try:
        return datetime.fromisoformat(dt_str)
    except ValueError:
        return datetime.now()


def deduplicate_dict_list(data):
    seen = set()
    deduplicated = []
    for d in data:
        key = json.dumps(d, sort_keys=True)
        if key not in seen:
            seen.add(key)
            deduplicated.append(d.copy())
    return deduplicated
