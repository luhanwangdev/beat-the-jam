from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median

from parser import Record


@dataclass
class Bin:
    bin_start: datetime
    avg_speed_kmh: float | None
    sample_count: int
    status: str


@dataclass
class Summary:
    overall_avg_kmh: float | None
    slowest_bin: datetime | None
    slowest_kmh: float | None


def compute_bins(records: list[Record], start: datetime, end: datetime,
                 bin_minutes: int) -> list[Bin]:
    step = timedelta(minutes=bin_minutes)
    edges: list[datetime] = []
    t = start
    while t < end:
        edges.append(t)
        t += step
    buckets: dict[datetime, list[float]] = {e: [] for e in edges}
    for rec in records:
        if not (start <= rec.ts < end):
            continue
        if rec.speed <= 0:
            continue
        idx = int((rec.ts - start) / step)
        buckets[edges[idx]].append(rec.speed)
    bins: list[Bin] = []
    for e in edges:
        speeds = buckets[e]
        if speeds:
            bins.append(Bin(e, round(median(speeds), 1), len(speeds), "ok"))
        else:
            bins.append(Bin(e, None, 0, "no_data"))
    return bins


def summarize(bins: list[Bin]) -> Summary:
    ok = [b for b in bins if b.status == "ok" and b.avg_speed_kmh is not None]
    if not ok:
        return Summary(None, None, None)
    slowest = min(ok, key=lambda b: b.avg_speed_kmh)
    overall = round(median([b.avg_speed_kmh for b in ok]), 1)
    return Summary(overall, slowest.bin_start, slowest.avg_speed_kmh)
