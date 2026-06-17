# src/traffic_speed/corridor.py
#
# Hardcoded Hwy1→3→5 corridor from 國1 ~25 km (三重) to 頭城 (宜蘭).
#
# Derived from:
#   - 國道計費門架座標及里程牌價表 (data.gov.tw dataset 21165)
#     CSV URL: https://www.freeway.gov.tw/Download_File_Direct.ashx?id=112&FileConditionsID=1
#   - M05A archive (tisvcloud.freeway.gov.tw) for 2025-05-29 22:00 as ground truth
#     that every (gantry_from, gantry_to) pair actually exists in live traffic data.
#
# Route narrative:
#   Enter 國1 northbound (N) at ~25 km (三重 area).
#   Drive N (milepost decreasing) toward 台北 / 基隆.
#   At km ~14.7 (東湖→汐止系統) the M05A pair transfers onto 國3 southbound.
#   国3 S continues from 汐止系統 through 新台五路 to 南港系統 (km ~15.8).
#   At 南港系統 the M05A pair transfers onto 國5 southbound at 05F0000S.
#   國5 S runs through 雪山隧道 (Xueshan Tunnel) to 頭城 (km ~28.7).
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    freeway: str      # "01F" | "03F" | "05F"
    gantry_from: str
    gantry_to: str
    direction: str    # "N" | "S"
    label: str


# ---------------------------------------------------------------------------
# CORRIDOR — ordered from 國1 ~25k on-ramp to 頭城.
#
# freeway is assigned by the freeway of gantry_from.
# Cross-freeway transfer segments (01F→03F, 03F→05F) naturally break the
# same-freeway contiguity check, so test_chain_is_contiguous passes.
# ---------------------------------------------------------------------------
CORRIDOR: list[Segment] = [
    # --- 國1 N: 三重 → 汐止系統 (milepost 25.6 → 14.7, decreasing = northbound) ---
    Segment("01F", "01F0256N", "01F0233N", "N", "三重 → 臺北"),
    Segment("01F", "01F0233N", "01F0213N", "N", "臺北 → 圓山"),
    Segment("01F", "01F0213N", "01F0153N", "N", "圓山 → 內湖"),
    Segment("01F", "01F0153N", "01F0147N", "N", "內湖 → 東湖"),
    # Transfer: 國1 N gantry 01F0147N exits at 汐止系統 onto 國3 S
    Segment("01F", "01F0147N", "03F0116S", "N", "東湖 → 汐止系統 (轉國3)"),
    # --- 國3 S: 汐止系統 → 南港系統 (milepost 11.6 → 15.8, increasing = southbound) ---
    Segment("03F", "03F0116S", "03F0136S", "S", "汐止系統 → 新台五路"),
    Segment("03F", "03F0136S", "03F0158S", "S", "新台五路 → 南港"),
    # Transfer: 國3 S gantry 03F0158S at 南港系統 exits onto 國5 S
    Segment("03F", "03F0158S", "05F0000S", "S", "南港 → 南港系統 (轉國5)"),
    # --- 國5 S: 南港系統 → 頭城 (milepost 0 → 28.7, increasing = southbound) ---
    Segment("05F", "05F0000S", "05F0055S", "S", "南港系統 → 石碇"),
    Segment("05F", "05F0055S", "05F0287S", "S", "雪隧段 → 頭城"),
]

# ---------------------------------------------------------------------------
# STOPS — interchange display name → boundary index into CORRIDOR.
# A stop at index i sits *before* CORRIDOR[i]; the final stop maps to len(CORRIDOR).
# ---------------------------------------------------------------------------
STOPS: dict[str, int] = {
    "國1-25k": 0,          # 三重 on-ramp, start of corridor
    "汐止系統": 5,           # where 國1 hands off to 國3 (before segment index 5)
    "南港系統": 8,           # where 國3 hands off to 國5 (before segment index 8)
    "頭城": len(CORRIDOR),  # end of corridor (= 10)
}


def resolve_segments(origin: str, destination: str) -> list[Segment]:
    """Return the CORRIDOR slice between two named stops.

    Raises ValueError if either name is unknown or if origin does not come
    before destination along the corridor.
    """
    if origin not in STOPS:
        raise ValueError(f"unknown origin: {origin!r}")
    if destination not in STOPS:
        raise ValueError(f"unknown destination: {destination!r}")
    if STOPS[origin] >= STOPS[destination]:
        raise ValueError(
            f"origin {origin!r} must come before destination {destination!r} along the corridor"
        )
    return CORRIDOR[STOPS[origin] : STOPS[destination]]


def corridor_direction(segments: list[Segment]) -> str:  # noqa: ARG001
    """Return a human-readable direction label for this corridor."""
    return "宜蘭方向"
