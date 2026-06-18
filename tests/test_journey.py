from datetime import datetime

from parser import Record
from journey import index_speeds, speed_at


def test_index_speeds_nests_by_segment_then_time():
    recs = [
        Record(datetime(2025, 5, 29, 20, 0), "A", "B", 80.0),
        Record(datetime(2025, 5, 29, 20, 5), "A", "B", 60.0),
        Record(datetime(2025, 5, 29, 20, 0), "B", "C", 50.0),
    ]
    idx = index_speeds(recs)
    assert idx[("A", "B")][datetime(2025, 5, 29, 20, 0)] == 80.0
    assert idx[("A", "B")][datetime(2025, 5, 29, 20, 5)] == 60.0
    assert idx[("B", "C")][datetime(2025, 5, 29, 20, 0)] == 50.0


def test_speed_at_exact_hit_after_flooring():
    idx = index_speeds([Record(datetime(2025, 5, 29, 20, 0), "A", "B", 80.0)])
    # 20:02 floors to 20:00 -> exact hit
    assert speed_at(idx, ("A", "B"), datetime(2025, 5, 29, 20, 2)) == 80.0


def test_speed_at_tolerance_window():
    idx = index_speeds([Record(datetime(2025, 5, 29, 20, 0), "A", "B", 80.0)])
    # 20:07 floors to 20:05 (miss), widens to 20:00 within +/-5
    assert speed_at(idx, ("A", "B"), datetime(2025, 5, 29, 20, 7)) == 80.0


def test_speed_at_out_of_window_returns_none():
    idx = index_speeds([Record(datetime(2025, 5, 29, 20, 0), "A", "B", 80.0)])
    # 20:20 floors to 20:20; nearest data 20:00 is 20 min away -> None
    assert speed_at(idx, ("A", "B"), datetime(2025, 5, 29, 20, 20)) is None


def test_speed_at_unknown_segment_returns_none():
    idx = index_speeds([Record(datetime(2025, 5, 29, 20, 0), "A", "B", 80.0)])
    assert speed_at(idx, ("X", "Y"), datetime(2025, 5, 29, 20, 0)) is None


def test_speed_at_treats_zero_speed_as_offline():
    idx = index_speeds([Record(datetime(2025, 5, 29, 20, 0), "A", "B", 0.0)])
    assert speed_at(idx, ("A", "B"), datetime(2025, 5, 29, 20, 0)) is None
