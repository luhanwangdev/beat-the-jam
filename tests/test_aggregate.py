# tests/test_aggregate.py
from datetime import datetime
from parser import Record
from aggregate import compute_bins, summarize


def _rec(minute, gantry_from, gantry_to, speed):
    return Record(datetime(2025, 5, 29, 22, minute), gantry_from, gantry_to, speed)


# seg_lengths dict for the 雪隧 segment only (23.2 km)
XUESHAN = {("05F0055S", "05F0287S"): 23.2}

# seg_lengths dict for a synthetic single segment of length 10
SEG10 = {("A0000001", "A0000002"): 10.0}

# seg_lengths for two-segment scenario: 20 km slow + 2 km fast
SEG_TWO = {
    ("B0000001", "B0000002"): 20.0,  # slow lane, 20 km
    ("B0000003", "B0000004"): 2.0,   # fast lane, 2 km
}


def test_bins_span_whole_window_even_when_empty():
    bins = compute_bins([], datetime(2025, 5, 29, 22, 0),
                        datetime(2025, 5, 29, 23, 0), 30, seg_lengths={})
    assert [b.bin_start.minute for b in bins] == [0, 30]
    assert all(b.status == "no_data" and b.avg_speed_kmh is None for b in bins)


def test_single_segment_harmonic_mean_three_obs():
    # One 10-km segment observed at 40, 50, 60 km/h in the same bin.
    # Effective speed = (10+10+10) / (10/40 + 10/50 + 10/60) = 30 / 0.6167 = 48.6
    recs = [
        _rec(0,  "A0000001", "A0000002", 40),
        _rec(5,  "A0000001", "A0000002", 50),
        _rec(10, "A0000001", "A0000002", 60),
    ]
    bins = compute_bins(recs, datetime(2025, 5, 29, 22, 0),
                        datetime(2025, 5, 29, 22, 30), 30, SEG10)
    assert len(bins) == 1
    assert bins[0].avg_speed_kmh == 48.6
    assert bins[0].sample_count == 3
    assert bins[0].status == "ok"


def test_two_segments_long_slow_dominates():
    # 20 km at 30 km/h + 2 km at 90 km/h in same bin.
    # Effective speed = 22 / (20/30 + 2/90) = 22 / 0.6889 = 31.9
    # Median would give 60.0 — harmonic mean correctly surfaces the bottleneck.
    recs = [
        _rec(0, "B0000001", "B0000002", 30),   # 20 km segment, slow
        _rec(0, "B0000003", "B0000004", 90),   # 2 km segment, fast
    ]
    bins = compute_bins(recs, datetime(2025, 5, 29, 22, 0),
                        datetime(2025, 5, 29, 22, 30), 30, SEG_TWO)
    assert len(bins) == 1
    assert bins[0].avg_speed_kmh == 31.9
    assert bins[0].avg_speed_kmh < 0.85 * 60.0  # confirm bottleneck pull-down


def test_zero_speed_excluded():
    recs = [
        _rec(0, "A0000001", "A0000002", 0),   # excluded
        _rec(5, "A0000001", "A0000002", 40),
    ]
    bins = compute_bins(recs, datetime(2025, 5, 29, 22, 0),
                        datetime(2025, 5, 29, 22, 30), 30, SEG10)
    # Only the speed=40 obs counts; single obs → effective speed = 40
    assert bins[0].avg_speed_kmh == 40.0
    assert bins[0].sample_count == 1


def test_records_outside_window_ignored():
    recs = [_rec(45, "A0000001", "A0000002", 99)]  # 22:45, outside 22:00-22:30
    bins = compute_bins(recs, datetime(2025, 5, 29, 22, 0),
                        datetime(2025, 5, 29, 22, 30), 30, SEG10)
    assert bins[0].status == "no_data"


def test_transfer_segment_length_zero_excluded():
    # A transfer segment (length=0) must be excluded from computation.
    # Even with a valid speed, it contributes nothing to total_dist or total_time.
    seg_lengths_with_zero = {
        ("X0000001", "Y0000001"): 0.0,  # cross-freeway transfer → excluded
        ("A0000001", "A0000002"): 10.0,
    }
    recs = [
        _rec(0, "X0000001", "Y0000001", 80),   # transfer, excluded
        _rec(0, "A0000001", "A0000002", 40),   # normal, included
    ]
    bins = compute_bins(recs, datetime(2025, 5, 29, 22, 0),
                        datetime(2025, 5, 29, 22, 30), 30, seg_lengths_with_zero)
    # Only the 10-km@40 obs counts → effective speed = 40
    assert bins[0].avg_speed_kmh == 40.0
    assert bins[0].sample_count == 1


def test_summary_picks_slowest_ok_bin():
    # Two bins: first bin 60 km/h (on 10-km segment), second bin 30 km/h.
    recs = [
        _rec(0,  "A0000001", "A0000002", 60),  # bin 0 (22:00-22:30)
        _rec(35, "A0000001", "A0000002", 30),  # bin 1 (22:30-23:00)
    ]
    bins = compute_bins(recs, datetime(2025, 5, 29, 22, 0),
                        datetime(2025, 5, 29, 23, 0), 30, SEG10)
    s = summarize(bins)
    assert s.slowest_kmh == 30.0
    assert s.slowest_bin == datetime(2025, 5, 29, 22, 30)
    # overall_avg_kmh is a sample-count-weighted harmonic mean (not median):
    # (1+1) / (1/60 + 1/30) = 2 / 0.05 = 40.0
    assert s.overall_avg_kmh == 40.0
