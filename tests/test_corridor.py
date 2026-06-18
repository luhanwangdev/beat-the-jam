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
