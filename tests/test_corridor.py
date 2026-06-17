import pytest
from traffic_speed.corridor import CORRIDOR, STOPS, Segment, resolve_segments


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
