# tests/test_aggregate.py
from datetime import datetime
from parser import Record
from aggregate import compute_bins, summarize


def _rec(minute, speed):
    return Record(datetime(2025, 5, 29, 22, minute), "05F0055S", "05F0287S", speed)


def test_bins_span_whole_window_even_when_empty():
    bins = compute_bins([], datetime(2025, 5, 29, 22, 0),
                        datetime(2025, 5, 29, 23, 0), 30)
    assert [b.bin_start.minute for b in bins] == [0, 30]
    assert all(b.status == "no_data" and b.avg_speed_kmh is None for b in bins)


def test_bin_uses_median_of_valid_speeds():
    recs = [_rec(0, 40), _rec(5, 50), _rec(10, 60)]
    bins = compute_bins(recs, datetime(2025, 5, 29, 22, 0),
                        datetime(2025, 5, 29, 22, 30), 30)
    assert len(bins) == 1
    assert bins[0].avg_speed_kmh == 50.0
    assert bins[0].sample_count == 3
    assert bins[0].status == "ok"


def test_zero_speed_excluded_as_missing():
    recs = [_rec(0, 0), _rec(5, 40)]
    bins = compute_bins(recs, datetime(2025, 5, 29, 22, 0),
                        datetime(2025, 5, 29, 22, 30), 30)
    assert bins[0].avg_speed_kmh == 40.0
    assert bins[0].sample_count == 1


def test_records_outside_window_ignored():
    recs = [_rec(45, 99)]  # 22:45, outside 22:00-22:30
    bins = compute_bins(recs, datetime(2025, 5, 29, 22, 0),
                        datetime(2025, 5, 29, 22, 30), 30)
    assert bins[0].status == "no_data"


def test_summary_picks_slowest_ok_bin():
    recs = [_rec(0, 60), _rec(35, 30)]
    bins = compute_bins(recs, datetime(2025, 5, 29, 22, 0),
                        datetime(2025, 5, 29, 23, 0), 30)
    s = summarize(bins)
    assert s.slowest_kmh == 30.0
    assert s.slowest_bin == datetime(2025, 5, 29, 22, 30)
