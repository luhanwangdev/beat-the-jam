from dataclasses import dataclass
from datetime import datetime

PASSENGER_CAR = "31"


@dataclass(frozen=True)
class Record:
    ts: datetime
    gantry_from: str
    gantry_to: str
    speed: float


def parse_row(line: str, wanted_pairs: set[tuple[str, str]]) -> Record | None:
    parts = line.strip().split(",")
    if len(parts) != 6:
        return None
    ts_s, gf, gt, vtype, speed_s, _vol = parts
    if vtype != PASSENGER_CAR:
        return None
    if (gf, gt) not in wanted_pairs:
        return None
    try:
        ts = datetime.strptime(ts_s.strip(), "%Y/%m/%d %H:%M")
        speed = float(speed_s)
    except ValueError:
        return None
    return Record(ts, gf, gt, speed)
