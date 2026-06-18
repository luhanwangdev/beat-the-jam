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
