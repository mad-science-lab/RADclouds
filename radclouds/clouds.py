# Version: V26.284.1723
"""The cloud walk: pure logic, no I/O.

Every channel (and the profile's End intensity) has its own Min/Max set by the
user. Each minute every one of them rolls a die, 1..5, on its own:

    1 -> -4    2 -> -2    3 -> no change    4 -> +2    5 -> +4

Edge rules:
  * Already at Max (or Min) and the move would go past it: the move is reversed.
  * Not at the edge but the move would go past it: stop at the edge.
"""
from __future__ import annotations

import random
from typing import Callable

# (config key, label shown to the user). The profile's Overall Intensity "End"
# value is stored as `max` in the Apex profile; it is the only overall value
# that is walked (Start, `min`, is left alone).
CHANNELS: list[tuple[str, str]] = [
    ("white", "White"),
    ("blue", "Blue"),
    ("rBlue", "Royal Blue"),
    ("green", "Green"),
    ("red", "Red"),
    ("UV", "UV"),
    ("wWhite", "Warm White"),
    ("violet", "Violet"),
    ("end", "End intensity"),
]
KEYS = [k for k, _ in CHANNELS]
LABELS = dict(CHANNELS)

# Config key -> key inside the Apex profile's `data` (only End differs).
DATA_KEY = {"end": "max"}

MOVES = {1: -4, 2: -2, 3: 0, 4: 2, 5: 4}
MIN_DELTA = 15  # Max - Min must be MORE than this

# Speed scales the size of every move (1x = the table above). In 0.5 steps every
# result is a whole number, and the biggest move (4 x 3 = 12) is still smaller
# than the narrowest allowed range (16), so a reversed move stays inside it.
MIN_SPEED, MAX_SPEED, SPEED_STEP = 1.0, 3.0, 0.5
# Seconds between steps.
MIN_INTERVAL, MAX_INTERVAL = 15, 120


def data_key(key: str) -> str:
    return DATA_KEY.get(key, key)


def median(lo: int, hi: int) -> int:
    return (lo + hi + 1) // 2  # halves round up, same as the web page


def move_for(roll: int, scale: float = 1.0) -> int:
    return int(round(MOVES[roll] * scale))


def next_value(cur: int, lo: int, hi: int, roll: int, scale: float = 1.0) -> int:
    cur = max(lo, min(hi, cur))  # a range that was narrowed pulls the value in first
    move = move_for(roll, scale)
    if move == 0:
        return cur
    if (cur >= hi and move > 0) or (cur <= lo and move < 0):
        move = -move  # at the edge and heading out: reverse
    return max(lo, min(hi, cur + move))


def step(values: dict[str, int], ranges: dict[str, dict[str, int]], scale: float = 1.0,
         roll: Callable[[], int] | None = None) -> dict[str, int]:
    """New values for every channel; each channel rolls its own die."""
    roll = roll or (lambda: random.randint(1, 5))
    return {k: next_value(values[k], ranges[k]["min"], ranges[k]["max"], roll(), scale) for k in KEYS}


def validate_speed(value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError("Speed must be a number") from None
    if not (MIN_SPEED <= v <= MAX_SPEED) or (v - MIN_SPEED) % SPEED_STEP:
        raise ValueError(f"Speed must be {MIN_SPEED:g} to {MAX_SPEED:g} in steps of {SPEED_STEP:g}")
    return v


def validate_interval(value) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise ValueError("Seconds between steps must be a whole number") from None
    if not (MIN_INTERVAL <= v <= MAX_INTERVAL):
        raise ValueError(f"Seconds between steps must be {MIN_INTERVAL} to {MAX_INTERVAL}")
    return v


def medians(ranges: dict[str, dict[str, int]]) -> dict[str, int]:
    return {k: median(ranges[k]["min"], ranges[k]["max"]) for k in KEYS}


def validate_ranges(ranges: dict) -> dict[str, dict[str, int]]:
    """Clean user input. Raises ValueError naming the first bad channel."""
    out: dict[str, dict[str, int]] = {}
    for k, label in CHANNELS:
        r = ranges.get(k) or {}
        try:
            lo, hi = int(r["min"]), int(r["max"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"{label}: enter a whole-number Min and Max") from None
        if not (0 <= lo <= 100 and 0 <= hi <= 100):
            raise ValueError(f"{label}: Min and Max must be between 0 and 100")
        # Min == Max is allowed: that color is held at that value and never moves.
        if hi != lo and hi - lo <= MIN_DELTA:
            raise ValueError(f"{label}: Max minus Min must be more than {MIN_DELTA} "
                             f"(it is {hi - lo}), or set Min and Max the same to hold one value")
        out[k] = {"min": lo, "max": hi}
    return out
