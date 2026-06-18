# src/main.py
from datetime import date, datetime, timedelta

from fastapi import FastAPI, HTTPException, Query

from aggregate import compute_bins, summarize
from archive import ArchiveUnavailable, fetch_day_records
from corridor import (
    CORRIDOR,
    corridor_direction,
    corridor_gantries,
    resolve_segments,
    resolve_segments_by_gantry,
)
from journey import compute_journey_times, index_speeds, summarize_journeys

TAG_QUERY = "車速查詢 / Speed Queries"
TAG_REFERENCE = "走廊資料 / Corridor Data"

tags_metadata = [
    {
        "name": TAG_QUERY,
        "description": (
            "對固定回家走廊(國1 北向 → 國3 → 國5 南向 → 頭城)做歷史車速查詢。"
            "資料來源為高公局 TDCS M05A 公開歸檔(小客車中位數車速),"
            "每次即時下載當日檔、不快取。\n\n"
            "Historical speed queries over the fixed homebound corridor "
            "(Hwy-1 N → Hwy-3 → Hwy-5 S → Toucheng). Data comes from the "
            "Freeway Bureau's public TDCS M05A archive (passenger-car median "
            "speed); each request downloads that day's archive live, no cache."
        ),
    },
    {
        "name": TAG_REFERENCE,
        "description": (
            "走廊本身的靜態資料,不下載歸檔、不需參數,用來得知查詢端點可填的門架/站點。\n\n"
            "Static corridor data — no archive download, no parameters. Use it "
            "to discover which gantries/stops the query endpoints accept."
        ),
    },
]

app = FastAPI(
    title="國道車速查詢服務 / Freeway Speed Query",
    description=(
        "輸入起點/終點與時間窗,回傳該路段逐時段的小客車平均車速或實際行車時間曲線,"
        "用來判斷「幾點出發進雪隧最不塞」。走廊與方向由系統寫死(回家路線),非使用者輸入。\n\n"
        "Given an origin/destination and a time window, returns the per-bin "
        "passenger-car average-speed curve or the actual travel-time curve for "
        "that corridor segment — to find the least-congested time to enter the "
        "Xueshan Tunnel. The corridor and direction are hardcoded (the homebound "
        "route), not user input."
    ),
    openapi_tags=tags_metadata,
)

DATE_FLOOR = date(2021, 6, 22)
ALLOWED_BINS = {5, 10, 15, 30, 60}
MAX_SPAN = timedelta(hours=24)
ARRIVAL_BUFFER = timedelta(hours=2)  # late departures arrive after `end`


@app.get(
    "/speed",
    tags=[TAG_QUERY],
    summary="逐時段瞬時車速曲線(named stops)/ Per-bin instantaneous speed curve",
    description=(
        "給定走廊上的起訖**交流道名稱**(如「南港系統」「頭城」)與時間窗,"
        "回傳每個 bin 的小客車平均車速。每個 bin 含 `avg_speed_kmh`、`sample_count`、"
        "`status`(缺值=偵測器離線,非塞到 0);`summary` 另給整體平均與最慢時段。"
        "可填的站點名稱見 `STOPS`。時間窗可跨午夜,跨度需 ≤ 24h。\n\n"
        "Given start/end **interchange names** (e.g. 南港系統, 頭城) and a time "
        "window, returns each bin's passenger-car average speed. Every bin has "
        "`avg_speed_kmh`, `sample_count`, and `status` (missing = detector "
        "offline, not jammed-to-zero); `summary` adds the overall average and "
        "slowest bin. Valid stop names are in `STOPS`. The window may cross "
        "midnight and must span ≤ 24h."
    ),
)
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


@app.get(
    "/journey",
    tags=[TAG_QUERY],
    summary="出發時間 → 實際行車時間曲線(gantry id)/ Departure → travel-time curve",
    description=(
        "給定走廊上的起訖**門架 id**(如 `01F0256N`、`05F0287S`)與時間窗,"
        "對每個出發時間做**時間相依**行車模擬:車子沿走廊前進時,每段套用「當下時刻」"
        "的車速(偵測器離線則沿用上一段車速)。回傳每筆 `depart`/`arrive`/"
        "`journey_minutes`/`effective_kmh`/`status`;`summary` 給最快與最慢的出發時段。"
        "因晚出發可能在 `end` 之後、甚至跨日抵達,下載會多抓 2 小時緩衝。"
        "合法門架 id 見 `GET /gantries`。\n\n"
        "Given start/end **gantry ids** (e.g. `01F0256N`, `05F0287S`) and a time "
        "window, runs a **time-dependent** simulation for each departure: as the "
        "car advances along the corridor, each segment uses the speed at the "
        "current clock time (carrying the previous segment's speed when a "
        "detector is offline). Returns `depart`/`arrive`/`journey_minutes`/"
        "`effective_kmh`/`status` per departure; `summary` gives the fastest and "
        "slowest departures. Since late departures may arrive after `end` or even "
        "the next day, the fetch pulls a 2-hour buffer. Valid gantry ids: "
        "`GET /gantries`."
    ),
)
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
        # Transfer segments are 0 km, so summing all segments equals the
        # measurable-only distance compute_journey_times uses as the
        # effective_kmh numerator — keep them consistent per the spec.
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


@app.get(
    "/gantries",
    tags=[TAG_REFERENCE],
    summary="列出走廊上所有可填的門架點 / List corridor gantry points",
    description=(
        "回傳走廊上 11 個有序門架點,供呼叫者得知 `GET /journey` 的 `origin`/`destination` "
        "能填哪些 id。每個門架點含 `id`、`freeway`、`milepost_km`、`direction`(由 id 推導),"
        "以及 `can_origin`/`can_destination`(編碼「origin 必須是某段起點、destination 必須是"
        "某段迄點」的規則:首點只能當 origin、末點只能當 destination)。"
        "純靜態資料:不下載歸檔、不需參數,因此不會回 400/503。\n\n"
        "Returns the 11 ordered gantry points along the corridor so callers know "
        "which ids `GET /journey` accepts for `origin`/`destination`. Each point "
        "has `id`, `freeway`, `milepost_km`, `direction` (all derived from the "
        "id), plus `can_origin`/`can_destination` (encoding the rule that an "
        "origin must be a segment start and a destination a segment end: the "
        "first point is origin-only, the last is destination-only). Pure static "
        "data — no download, no parameters, so it never returns 400/503."
    ),
)
def gantries():
    return {
        "direction": corridor_direction(CORRIDOR),
        "gantries": [
            {"id": g.id,
             "freeway": g.freeway,
             "milepost_km": g.milepost_km,
             "direction": g.direction,
             "can_origin": g.can_origin,
             "can_destination": g.can_destination}
            for g in corridor_gantries()
        ],
    }
