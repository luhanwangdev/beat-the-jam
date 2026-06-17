from datetime import datetime
from parser import parse_row, Record

WANTED = {("05F0055S", "05F0287S")}


def test_parses_passenger_car_row_in_corridor():
    line = "2025/05/29 22:00,05F0055S,05F0287S,31,52,168"
    rec = parse_row(line, WANTED)
    assert rec == Record(datetime(2025, 5, 29, 22, 0), "05F0055S", "05F0287S", 52.0)


def test_skips_non_passenger_car():
    line = "2025/05/29 22:00,05F0055S,05F0287S,41,52,168"
    assert parse_row(line, WANTED) is None


def test_skips_pair_not_in_corridor():
    line = "2025/05/29 22:00,01F0017N,01F0005N,31,86,66"
    assert parse_row(line, WANTED) is None


def test_keeps_zero_speed_for_aggregate_to_handle():
    line = "2025/05/29 22:00,05F0055S,05F0287S,31,0,0"
    rec = parse_row(line, WANTED)
    assert rec is not None and rec.speed == 0.0


def test_returns_none_on_malformed_row():
    assert parse_row("garbage,too,few", WANTED) is None
