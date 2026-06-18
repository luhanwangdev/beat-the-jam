# tests/test_api.py
from datetime import date, datetime
import pytest
from fastapi.testclient import TestClient
from main import app
from parser import Record

client = TestClient(app)


def test_rejects_date_before_floor():
    r = client.get("/speed", params={
        "origin": "國1-25k", "destination": "頭城",
        "start": "2020-01-01T20:00", "end": "2020-01-01T22:00"})
    assert r.status_code == 400
    assert "2021-06-22" in r.json()["detail"]


def test_rejects_reversed_stops():
    r = client.get("/speed", params={
        "origin": "頭城", "destination": "國1-25k",
        "start": "2025-05-29T20:00", "end": "2025-05-29T22:00"})
    assert r.status_code == 400


def test_rejects_span_over_24h():
    r = client.get("/speed", params={
        "origin": "國1-25k", "destination": "頭城",
        "start": "2025-05-29T00:00", "end": "2025-05-30T01:00"})
    assert r.status_code == 400


def test_happy_path_returns_curve(monkeypatch):
    def fake_fetch(d, pairs):
        return [Record(datetime(2025, 5, 29, 21, 0), "05F0055S", "05F0287S", 33.0)]
    monkeypatch.setattr("main.fetch_day_records", fake_fetch)
    r = client.get("/speed", params={
        "origin": "國1-25k", "destination": "頭城",
        "start": "2025-05-29T20:00", "end": "2025-05-29T22:00",
        "bin_minutes": 30})
    assert r.status_code == 200
    body = r.json()
    assert body["direction"] == "宜蘭方向"
    assert len(body["bins"]) == 4
    assert body["summary"]["slowest_kmh"] == 33.0


def test_rejects_end_equal_to_start():
    r = client.get("/speed", params={
        "origin": "國1-25k", "destination": "頭城",
        "start": "2025-05-29T20:00", "end": "2025-05-29T20:00"})
    assert r.status_code == 400


def test_rejects_invalid_bin_minutes():
    r = client.get("/speed", params={
        "origin": "國1-25k", "destination": "頭城",
        "start": "2025-05-29T20:00", "end": "2025-05-29T22:00",
        "bin_minutes": 7})
    assert r.status_code == 400


def test_day_fetch_midnight_end_fetches_only_start_day(monkeypatch):
    """Window ending exactly at midnight must NOT download the next day's archive."""
    fetched_dates: list[date] = []

    def fake_fetch(d, pairs):
        fetched_dates.append(d)
        return []

    monkeypatch.setattr("main.fetch_day_records", fake_fetch)
    r = client.get("/speed", params={
        "origin": "國1-25k", "destination": "頭城",
        "start": "2025-05-29T20:00", "end": "2025-05-30T00:00",
        "bin_minutes": 30})
    # Request itself may succeed (empty data) or 400-range; what matters is dates.
    assert fetched_dates == [date(2025, 5, 29)]


def test_day_fetch_past_midnight_end_fetches_both_days(monkeypatch):
    """Window ending after midnight must include the next day's archive."""
    fetched_dates: list[date] = []

    def fake_fetch(d, pairs):
        fetched_dates.append(d)
        return []

    monkeypatch.setattr("main.fetch_day_records", fake_fetch)
    r = client.get("/speed", params={
        "origin": "國1-25k", "destination": "頭城",
        "start": "2025-05-29T20:00", "end": "2025-05-30T05:00",
        "bin_minutes": 30})
    assert fetched_dates == [date(2025, 5, 29), date(2025, 5, 30)]


def test_journey_endpoint_shape(monkeypatch):
    import main
    monkeypatch.setattr(main, "fetch_day_records", lambda day, wanted: [])
    from fastapi.testclient import TestClient
    client = TestClient(main.app)
    resp = client.get("/journey", params={
        "origin": "01F0213N", "destination": "05F0287S",
        "start": "2025-05-29T20:00:00", "end": "2025-05-29T22:00:00",
        "bin_minutes": 30,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["origin"] == "01F0213N"
    assert body["distance_km"] > 0
    assert isinstance(body["journeys"], list) and body["journeys"]
    assert {"depart", "arrive", "journey_minutes", "effective_kmh", "status"} <= body["journeys"][0].keys()
    assert "fastest_depart" in body["summary"]


def test_journey_unknown_gantry_returns_400(monkeypatch):
    import main
    monkeypatch.setattr(main, "fetch_day_records", lambda day, wanted: [])
    from fastapi.testclient import TestClient
    client = TestClient(main.app)
    resp = client.get("/journey", params={
        "origin": "ZZZ9999N", "destination": "05F0287S",
        "start": "2025-05-29T20:00:00", "end": "2025-05-29T22:00:00",
    })
    assert resp.status_code == 400


def test_journey_fetches_arrival_buffer_day(monkeypatch):
    import main
    called_days = []
    monkeypatch.setattr(
        main, "fetch_day_records",
        lambda day, wanted: called_days.append(day) or [],
    )
    from fastapi.testclient import TestClient
    client = TestClient(main.app)
    resp = client.get("/journey", params={
        "origin": "01F0213N", "destination": "05F0287S",
        "start": "2025-05-29T23:30:00", "end": "2025-05-29T23:45:00",
        "bin_minutes": 15,
    })
    assert resp.status_code == 200
    # end + 2h buffer = 2025-05-30 01:45 -> must fetch both days
    assert date(2025, 5, 29) in called_days
    assert date(2025, 5, 30) in called_days


def test_gantries_endpoint_lists_corridor_points():
    from fastapi.testclient import TestClient
    from main import app
    resp = TestClient(app).get("/gantries")
    assert resp.status_code == 200
    body = resp.json()
    assert body["direction"] == "宜蘭方向"
    pts = body["gantries"]
    assert len(pts) == 11
    assert {"id", "freeway", "milepost_km", "direction",
            "can_origin", "can_destination"} == set(pts[0].keys())
    # first point only origin, last point only destination
    assert pts[0]["id"] == "01F0256N"
    assert pts[0]["can_origin"] is True and pts[0]["can_destination"] is False
    assert pts[-1]["id"] == "05F0287S"
    assert pts[-1]["can_origin"] is False and pts[-1]["can_destination"] is True
