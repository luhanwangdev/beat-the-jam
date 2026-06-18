from dataclasses import dataclass
from datetime import datetime, timedelta

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


def compute_bins(
    records: list[Record],
    start: datetime,
    end: datetime,
    bin_minutes: int,
    seg_lengths: dict[tuple[str, str], float],
) -> list[Bin]:
    """Aggregate records into time bins using distance-weighted harmonic mean.

    Effective speed = Σlength / Σ(length/speed), which gives the true
    journey speed over the entire corridor and correctly weights long congested
    segments over short free-flowing ones.

    Records are excluded if:
    - outside [start, end)
    - speed <= 0
    - the segment's length is 0 (cross-freeway transfers) or unknown
    """
    step = timedelta(minutes=bin_minutes)
    edges: list[datetime] = []
    t = start
    while t < end:
        edges.append(t)
        t += step

    # Each bucket holds (length, speed) pairs for the harmonic mean
    buckets: dict[datetime, list[tuple[float, float]]] = {e: [] for e in edges}

    for rec in records:
        if not (start <= rec.ts < end):
            continue
        if rec.speed <= 0:
            continue
        length = seg_lengths.get((rec.gantry_from, rec.gantry_to), 0.0)
        if length <= 0:
            continue
        idx = int((rec.ts - start) / step)
        buckets[edges[idx]].append((length, rec.speed))

    bins: list[Bin] = []
    for e in edges:
        obs = buckets[e]
        if obs:
            total_dist = sum(length for length, _ in obs)
            total_time = sum(length / speed for length, speed in obs)
            # Non-empty obs have speed>0 and length>0, so total_time is always >0.
            avg = round(total_dist / total_time, 1)
            bins.append(Bin(e, avg, len(obs), "ok"))
        else:
            bins.append(Bin(e, None, 0, "no_data"))
    return bins


def summarize(bins: list[Bin]) -> Summary:
    ok = [b for b in bins if b.status == "ok" and b.avg_speed_kmh is not None]
    if not ok:
        return Summary(None, None, None)
    slowest = min(ok, key=lambda b: b.avg_speed_kmh)
    # Use a sample-count-weighted harmonic mean so slow, well-sampled bins pull
    # the headline figure down — consistent with per-bin distance/time logic and
    # avoids the median's tendency to hide the congestion trough.
    overall = round(
        sum(b.sample_count for b in ok)
        / sum(b.sample_count / b.avg_speed_kmh for b in ok),
        1,
    )
    return Summary(overall, slowest.bin_start, slowest.avg_speed_kmh)
