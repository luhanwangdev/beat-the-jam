import os
import pytest
from fastapi.testclient import TestClient
from main import app

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="set RUN_E2E=1 to run the network-dependent e2e test",
)

client = TestClient(app)


def test_holiday_eve_xueshan_has_congestion_trough():
    """2025 Dragon Boat holiday eve, southbound, 20:00-00:00.

    With distance-weighted harmonic mean the 23.2-km 雪山隧道 segment dominates
    its bin, making the congestion trough clearly visible:
    - slowest_kmh < 65 (genuine slowdown, not normal cruise speed)
    - slowest_kmh < 0.85 * fastest_kmh (real spread, not a minor dip)
    """
    r = client.get("/speed", params={
        "origin": "國1-25k", "destination": "頭城",
        "start": "2025-05-29T20:00", "end": "2025-05-30T00:00",
        "bin_minutes": 30})
    assert r.status_code == 200
    body = r.json()
    ok_bins = [b for b in body["bins"] if b["status"] == "ok"]
    assert ok_bins, "expected real speed data for the corridor"

    speeds = [b["avg_speed_kmh"] for b in ok_bins]
    slowest = min(speeds)
    fastest = max(speeds)

    # Congestion signature: trough is meaningfully slower than peak,
    # AND absolute slow enough to indicate real congestion
    assert slowest < 65, (
        f"slowest bin {slowest} km/h should be < 65 (congested); bins: {speeds}"
    )
    assert slowest < 0.85 * fastest, (
        f"slowest {slowest} km/h should be < 85% of fastest {fastest} km/h; bins: {speeds}"
    )
