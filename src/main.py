# src/main.py
from datetime import date, datetime, timedelta

from fastapi import FastAPI, HTTPException, Query

from aggregate import compute_bins, summarize
from archive import ArchiveUnavailable, fetch_day_records
from corridor import (
    corridor_direction,
    resolve_segments,
    resolve_segments_by_gantry,
)
from journey import compute_journey_times, index_speeds, summarize_journeys

app = FastAPI(title="Freeway Speed Query")

DATE_FLOOR = date(2021, 6, 22)
ALLOWED_BINS = {5, 10, 15, 30, 60}
MAX_SPAN = timedelta(hours=24)
ARRIVAL_BUFFER = timedelta(hours=2)  # late departures arrive after `end`


@app.get("/speed")
def speed(
    origin: str = Query(...),
    destination: str = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
    bin_minutes: int = Query(30),
):
    if bin_minutes not in ALLOWED_BINS:
        raise HTTPException(400, f"bin_minutes must be one of {sorted(ALLOWED_BINS)}")
    if end <= start:
        raise HTTPException(400, "end must be after start")
    if end - start > MAX_SPAN:
        raise HTTPException(400, "time span must be <= 24 hours")
    today = date.today()
    if start.date() < DATE_FLOOR or end.date() > today:
        raise HTTPException(400, f"dates must be between 2021-06-22 and {today}")

    try:
        segments = resolve_segments(origin, destination)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    wanted = {(s.gantry_from, s.gantry_to) for s in segments}
    # Subtract 1 microsecond so a midnight-aligned end doesn't pull in a wasted
    # extra day whose bins would all be trimmed away by the strict < end filter.
    last_needed = (end - timedelta(microseconds=1)).date()
    days = []
    d = start.date()
    while d <= last_needed:
        days.append(d)
        d += timedelta(days=1)

    records = []
    try:
        for day in days:
            records.extend(fetch_day_records(day, wanted))
    except ArchiveUnavailable as exc:
        raise HTTPException(503, f"upstream archive unavailable: {exc}") from exc

    seg_lengths = {(s.gantry_from, s.gantry_to): s.length_km for s in segments}
    bins = compute_bins(records, start, end, bin_minutes, seg_lengths)
    summary = summarize(bins)
    return {
        "origin": origin,
        "destination": destination,
        "direction": corridor_direction(segments),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "bin_minutes": bin_minutes,
        "bins": [
            {"bin_start": b.bin_start.isoformat(),
             "avg_speed_kmh": b.avg_speed_kmh,
             "sample_count": b.sample_count,
             "status": b.status}
            for b in bins
        ],
        "summary": {
            "overall_avg_kmh": summary.overall_avg_kmh,
            "slowest_bin": summary.slowest_bin.isoformat() if summary.slowest_bin else None,
            "slowest_kmh": summary.slowest_kmh,
        },
    }


@app.get("/journey")
def journey(
    origin: str = Query(...),
    destination: str = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
    bin_minutes: int = Query(30),
):
    if bin_minutes not in ALLOWED_BINS:
        raise HTTPException(400, f"bin_minutes must be one of {sorted(ALLOWED_BINS)}")
    if end <= start:
        raise HTTPException(400, "end must be after start")
    if end - start > MAX_SPAN:
        raise HTTPException(400, "time span must be <= 24 hours")
    today = date.today()
    if start.date() < DATE_FLOOR or end.date() > today:
        raise HTTPException(400, f"dates must be between 2021-06-22 and {today}")

    try:
        segments = resolve_segments_by_gantry(origin, destination)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    wanted = {(s.gantry_from, s.gantry_to) for s in segments}

    step = timedelta(minutes=bin_minutes)
    departures: list[datetime] = []
    t = start
    while t <= end:
        departures.append(t)
        t += step

    # Download through the latest possible arrival, capped at today (no future
    # archive exists). Late departures may arrive after `end`, possibly next day.
    last_needed = min((end + ARRIVAL_BUFFER).date(), today)
    days = []
    d = start.date()
    while d <= last_needed:
        days.append(d)
        d += timedelta(days=1)

    records = []
    try:
        for day in days:
            records.extend(fetch_day_records(day, wanted))
    except ArchiveUnavailable as exc:
        raise HTTPException(503, f"upstream archive unavailable: {exc}") from exc

    idx = index_speeds(records)
    journeys = compute_journey_times(idx, segments, departures)
    summary = summarize_journeys(journeys)
    return {
        "origin": origin,
        "destination": destination,
        "direction": corridor_direction(segments),
        "distance_km": round(sum(s.length_km for s in segments), 1),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "bin_minutes": bin_minutes,
        "journeys": [
            {"depart": j.depart.isoformat(),
             "arrive": j.arrive.isoformat(),
             "journey_minutes": j.journey_minutes,
             "effective_kmh": j.effective_kmh,
             "status": j.status}
            for j in journeys
        ],
        "summary": {
            "fastest_depart": summary.fastest_depart.isoformat() if summary.fastest_depart else None,
            "fastest_minutes": summary.fastest_minutes,
            "slowest_depart": summary.slowest_depart.isoformat() if summary.slowest_depart else None,
            "slowest_minutes": summary.slowest_minutes,
        },
    }
