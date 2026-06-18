# src/journey.py
#
# Time-dependent journey model: departure time -> ACTUAL travel time.
# Unlike aggregate.compute_bins (a wall-clock SNAPSHOT of the whole corridor at
# one instant), this walks a single car through the corridor segment by segment,
# advancing the clock as the car spends time on each segment, so each later
# segment is read at the wall-clock time the car actually reaches it.
from dataclasses import dataclass
from datetime import datetime, timedelta

from corridor import Segment
from parser import Record

FREE_FLOW_KMH = 90.0

SpeedIndex = dict[tuple[str, str], dict[datetime, float]]


def index_speeds(records: list[Record]) -> SpeedIndex:
    """Flatten records into index[(gf, gt)][snapshot_ts] = speed."""
    index: SpeedIndex = {}
    for r in records:
        index.setdefault((r.gantry_from, r.gantry_to), {})[r.ts] = r.speed
    return index


def speed_at(
    index: SpeedIndex,
    seg_key: tuple[str, str],
    clock: datetime,
    window_min: int = 15,
) -> float | None:
    """Speed (km/h) on a segment at wall-clock `clock`.

    M05A snapshots land on 5-min marks. Floor `clock` to the 5-min mark and look
    it up; widen to +/-5, +/-10, ... up to +/-window_min. A snapshot of <=0 is an
    offline detector and is skipped. Returns None if nothing usable is found.
    """
    table = index.get(seg_key)
    if not table:
        return None
    floored = clock.replace(
        minute=clock.minute - clock.minute % 5, second=0, microsecond=0
    )
    deltas = [0]
    step = 5
    while step <= window_min:
        deltas.extend([-step, step])
        step += 5
    for delta in deltas:
        spd = table.get(floored + timedelta(minutes=delta))
        if spd and spd > 0:
            return spd
    return None
