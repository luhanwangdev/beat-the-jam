from datetime import datetime

from corridor import Segment
from parser import Record
from journey import index_speeds, speed_at, compute_journey_times, Journey


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


# two 10 km same-freeway segments in driving order
SEG1 = Segment("01F", "01F0200N", "01F0100N", "N", "s1")  # 10.0 km
SEG2 = Segment("01F", "01F0100N", "01F0000N", "N", "s2")  # 10.0 km


def test_journey_advances_clock_and_uses_arrival_time_speed():
    # SEG1 fast at depart; SEG2 has a FAST decoy at 20:00 but the REAL slow
    # speed at 20:10 (when the car actually arrives). The model must use 30, not 90.
    recs = [
        Record(datetime(2025, 5, 29, 20, 0), "01F0200N", "01F0100N", 60.0),
        Record(datetime(2025, 5, 29, 20, 0), "01F0100N", "01F0000N", 90.0),  # decoy
        Record(datetime(2025, 5, 29, 20, 10), "01F0100N", "01F0000N", 30.0),  # real
    ]
    idx = index_speeds(recs)
    [j] = compute_journey_times(idx, [SEG1, SEG2], [datetime(2025, 5, 29, 20, 0)])
    # SEG1: 10km / 60 = 10 min -> arrive SEG2 at 20:10
    # SEG2 at 20:10 = 30 km/h -> 10km / 30 = 20 min -> arrive 20:30
    assert j.arrive == datetime(2025, 5, 29, 20, 30)
    assert j.journey_minutes == 30.0
    assert j.effective_kmh == 40.0  # 20 km / 0.5 h
    assert j.status == "ok"


def test_journey_offline_segment_carries_last_speed_and_marks_partial():
    # SEG2 has no data at arrival -> carry SEG1's 60 km/h forward
    recs = [Record(datetime(2025, 5, 29, 20, 0), "01F0200N", "01F0100N", 60.0)]
    idx = index_speeds(recs)
    [j] = compute_journey_times(idx, [SEG1, SEG2], [datetime(2025, 5, 29, 20, 0)])
    # SEG1 60 -> 10 min, SEG2 carried 60 -> 10 min, total 20 min
    assert j.journey_minutes == 20.0
    assert j.status == "partial"


def test_journey_first_segment_offline_uses_free_flow_seed():
    idx = index_speeds([])  # no data at all
    [j] = compute_journey_times(
        idx, [SEG1, SEG2], [datetime(2025, 5, 29, 20, 0)], free_flow_kmh=90.0
    )
    assert j.status == "partial"
    assert j.effective_kmh == 90.0  # both segments at free-flow


def test_journey_skips_zero_length_transfer_segments():
    transfer = Segment("01F", "01F0100N", "03F0116S", "N", "transfer")  # length 0
    recs = [
        Record(datetime(2025, 5, 29, 20, 0), "01F0200N", "01F0100N", 60.0),
        Record(datetime(2025, 5, 29, 20, 10), "01F0100N", "01F0000N", 60.0),
    ]
    idx = index_speeds(recs)
    [j] = compute_journey_times(
        idx, [SEG1, transfer, SEG2], [datetime(2025, 5, 29, 20, 0)]
    )
    # transfer contributes 0 distance and 0 time; only SEG1+SEG2 count (20 km)
    assert j.effective_kmh == 60.0


def test_journey_only_zero_length_transfer_no_crash():
    # Regression test: empty measurable list (only zero-length transfer) should not crash
    transfer = Segment("01F", "01F0100N", "03F0116S", "N", "transfer")  # length 0
    idx = index_speeds([])  # no data
    [j] = compute_journey_times(
        idx, [transfer], [datetime(2025, 5, 29, 20, 0)]
    )
    # No measurable segments: total_hours = 0, effective_kmh should be 0.0, not crash
    assert j.effective_kmh == 0.0
    assert j.journey_minutes == 0.0
    assert j.status == "ok"  # no measurable segments, so no fallback used


from journey import summarize_journeys, JourneySummary


def test_summarize_picks_fastest_and_slowest():
    js = [
        Journey(datetime(2025, 5, 29, 20, 0), datetime(2025, 5, 29, 20, 30),
                30.0, 40.0, "ok"),
        Journey(datetime(2025, 5, 29, 20, 30), datetime(2025, 5, 29, 20, 50),
                20.0, 60.0, "ok"),
    ]
    s = summarize_journeys(js)
    assert s.fastest_depart == datetime(2025, 5, 29, 20, 30)
    assert s.fastest_minutes == 20.0
    assert s.slowest_depart == datetime(2025, 5, 29, 20, 0)
    assert s.slowest_minutes == 30.0


def test_summarize_empty_is_all_none():
    s = summarize_journeys([])
    assert s == JourneySummary(None, None, None, None)
