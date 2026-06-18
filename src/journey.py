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


@dataclass
class Journey:
    depart: datetime
    arrive: datetime
    journey_minutes: float
    effective_kmh: float
    status: str  # "ok" | "partial"


def compute_journey_times(
    index: SpeedIndex,
    segments: list[Segment],
    departures: list[datetime],
    *,
    free_flow_kmh: float = FREE_FLOW_KMH,
) -> list[Journey]:
    """Forward-simulate one car per departure time through `segments`.

    For each segment, look up the speed at the CURRENT clock; advance the clock
    by length/speed. Offline (speed_at -> None) carries the last-known speed
    forward (free_flow_kmh seeds the first segment) and marks the journey
    "partial". Zero-length transfer segments are skipped.
    """
    measurable = [s for s in segments if s.length_km > 0]
    journeys: list[Journey] = []
    for depart in departures:
        clock = depart
        total_dist = 0.0
        last_speed = free_flow_kmh
        used_fallback = False
        for s in measurable:
            spd = speed_at(index, (s.gantry_from, s.gantry_to), clock)
            if spd is None:
                spd = last_speed
                used_fallback = True
            else:
                last_speed = spd
            clock += timedelta(hours=s.length_km / spd)
            total_dist += s.length_km
        total_hours = (clock - depart).total_seconds() / 3600
        effective_kmh = round(total_dist / total_hours, 1) if total_hours > 0 else 0.0
        journeys.append(
            Journey(
                depart=depart,
                arrive=clock,
                journey_minutes=round(total_hours * 60, 1),
                effective_kmh=effective_kmh,
                status="partial" if used_fallback else "ok",
            )
        )
    return journeys


@dataclass
class JourneySummary:
    fastest_depart: datetime | None
    fastest_minutes: float | None
    slowest_depart: datetime | None
    slowest_minutes: float | None


def summarize_journeys(journeys: list[Journey]) -> JourneySummary:
    if not journeys:
        return JourneySummary(None, None, None, None)
    fastest = min(journeys, key=lambda j: j.journey_minutes)
    slowest = max(journeys, key=lambda j: j.journey_minutes)
    return JourneySummary(
        fastest.depart, fastest.journey_minutes,
        slowest.depart, slowest.journey_minutes,
    )
