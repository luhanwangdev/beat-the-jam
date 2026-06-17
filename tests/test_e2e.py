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
    # 2025 Dragon Boat holiday eve, southbound, 20:00-00:00
    r = client.get("/speed", params={
        "origin": "國1-25k", "destination": "頭城",
        "start": "2025-05-29T20:00", "end": "2025-05-30T00:00",
        "bin_minutes": 30})
    assert r.status_code == 200
    body = r.json()
    ok_bins = [b for b in body["bins"] if b["status"] == "ok"]
    assert ok_bins, "expected real speed data for the corridor"
    # the slowest bin around 21:00 should be clearly congested (< 45 km/h)
    assert body["summary"]["slowest_kmh"] < 45
