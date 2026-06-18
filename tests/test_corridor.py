import pytest
from corridor import CORRIDOR, STOPS, Segment, resolve_segments


def test_chain_is_contiguous_within_each_freeway():
    # consecutive segments on the same freeway must connect end->start
    for a, b in zip(CORRIDOR, CORRIDOR[1:]):
        if a.freeway == b.freeway:
            assert a.gantry_to == b.gantry_from


def test_only_corridor_freeways_present():
    assert {s.freeway for s in CORRIDOR} <= {"01F", "03F", "05F"}


def test_xueshan_segment_present():
    pairs = {(s.gantry_from, s.gantry_to) for s in CORRIDOR}
    assert ("05F0055S", "05F0287S") in pairs


def test_stops_endpoints():
    assert STOPS["國1-25k"] == 0
    assert STOPS["頭城"] == len(CORRIDOR)


def test_resolve_returns_subrange():
    segs = resolve_segments("國1-25k", "頭城")
    assert segs == CORRIDOR


def test_resolve_rejects_reversed_order():
    with pytest.raises(ValueError):
        resolve_segments("頭城", "國1-25k")


def test_resolve_rejects_unknown_stop():
    with pytest.raises(ValueError):
        resolve_segments("火星", "頭城")


def test_segment_length_km():
    from corridor import Segment
    # Same-freeway, southbound 國5: 05F0055S → 05F0287S → 23.2 km
    s1 = Segment("05F", "05F0055S", "05F0287S", "S", "雪隧段")
    assert s1.length_km == 23.2

    # Same-freeway, northbound 國1: 01F0256N → 01F0233N → 2.3 km
    s2 = Segment("01F", "01F0256N", "01F0233N", "N", "三重→臺北")
    assert s2.length_km == 2.3

    # Cross-freeway transfer: 01F → 03F → 0.0 km
    s3 = Segment("01F", "01F0147N", "03F0116S", "N", "東湖→汐止系統(轉國3)")
    assert s3.length_km == 0.0


def test_resolve_by_gantry_slices_corridor():
    from corridor import resolve_segments_by_gantry
    segs = resolve_segments_by_gantry("01F0213N", "05F0287S")
    assert segs[0].gantry_from == "01F0213N"
    assert segs[-1].gantry_to == "05F0287S"


def test_resolve_by_gantry_unknown_origin_raises():
    from corridor import resolve_segments_by_gantry
    with pytest.raises(ValueError):
        resolve_segments_by_gantry("ZZZ9999N", "05F0287S")


def test_resolve_by_gantry_unknown_destination_raises():
    from corridor import resolve_segments_by_gantry
    with pytest.raises(ValueError):
        resolve_segments_by_gantry("01F0213N", "ZZZ9999S")


def test_resolve_by_gantry_wrong_order_raises():
    from corridor import resolve_segments_by_gantry
    # 05F0055S is gantry_from of the last segment; 01F0153N is gantry_to of an early one
    with pytest.raises(ValueError):
        resolve_segments_by_gantry("05F0055S", "01F0153N")


def test_corridor_gantries_count_and_order():
    from corridor import corridor_gantries
    pts = corridor_gantries()
    assert len(pts) == 11
    assert pts[0].id == "01F0256N"
    assert pts[-1].id == "05F0287S"
    # ids unique
    assert len({p.id for p in pts}) == 11


def test_corridor_gantries_endpoint_flags():
    from corridor import corridor_gantries
    pts = corridor_gantries()
    # first point: only an origin; last point: only a destination
    assert pts[0].can_origin is True
    assert pts[0].can_destination is False
    assert pts[-1].can_origin is False
    assert pts[-1].can_destination is True
    # an interior point is both
    assert pts[1].can_origin is True
    assert pts[1].can_destination is True


def test_corridor_gantries_field_derivation():
    from corridor import corridor_gantries
    last = corridor_gantries()[-1]
    assert last.id == "05F0287S"
    assert last.freeway == "05F"
    assert last.milepost_km == 28.7
    assert last.direction == "S"
